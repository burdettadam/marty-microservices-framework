"""
Unified Configuration and Secret Management System for Marty Microservices Framework

This module provides a cloud-agnostic configuration and secret management solution that works
across different hosting environments:

**Hosting Environments Supported:**
- Self-hosted (bare metal, VMs, Docker)
- AWS (ECS, EKS, Lambda, EC2)
- Google Cloud (GKE, Cloud Run, Compute Engine)
- Microsoft Azure (AKS, Container Instances, VMs)
- Kubernetes (any distribution)
- Local development

**Secret Backends Supported:**
- HashiCorp Vault (self-hosted or cloud)
- AWS Secrets Manager
- Google Cloud Secret Manager
- Azure Key Vault
- Kubernetes Secrets
- Environment Variables
- File-based secrets
- In-memory (dev/testing)

**Features:**
- Environment-specific configuration loading
- Type-safe configuration with validation
- Automatic secret rotation and lifecycle management
- Configuration hot-reloading
- Audit logging and compliance
- Fallback strategies for high availability
- Runtime environment detection
"""

import builtins
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar, Union

import yaml
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import existing security module components with fallbacks
try:
    from marty_msf.security.secrets import VaultClient, VaultConfig
    VAULT_INTEGRATION_AVAILABLE = True
except ImportError:
    VAULT_INTEGRATION_AVAILABLE = False

# Only import the Environment enum from existing manager
from marty_msf.framework.config.manager import Environment

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ==================== Enums and Configuration ==================== #

class HostingEnvironment(Enum):
    """Supported hosting environments."""
    LOCAL = "local"
    SELF_HOSTED = "self_hosted"
    AWS = "aws"
    GOOGLE_CLOUD = "google_cloud"
    AZURE = "azure"
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    UNKNOWN = "unknown"


class SecretBackend(Enum):
    """Available secret management backends."""
    VAULT = "vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    AZURE_KEY_VAULT = "azure_key_vault"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    KUBERNETES = "kubernetes"
    ENVIRONMENT = "environment"
    FILE = "file"
    MEMORY = "memory"


class ConfigurationStrategy(Enum):
    """Configuration loading strategies."""
    HIERARCHICAL = "hierarchical"  # base -> env -> secrets
    EXPLICIT = "explicit"  # only specified sources
    FALLBACK = "fallback"  # try backends in order until success
    AUTO_DETECT = "auto_detect"  # automatically detect best backends for environment


@dataclass
class SecretMetadata:
    """Metadata for secrets."""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    rotation_interval: timedelta | None = None
    last_rotated: datetime | None = None
    tags: dict[str, str] = field(default_factory=dict)
    backend: SecretBackend = SecretBackend.VAULT
    encrypted: bool = True


@dataclass
class ConfigurationContext:
    """Context for configuration loading."""
    service_name: str
    environment: Environment
    config_dir: Path | None = None
    plugins_dir: Path | None = None
    enable_secrets: bool = True
    enable_hot_reload: bool = False
    enable_plugins: bool = True
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=15))
    strategy: ConfigurationStrategy = ConfigurationStrategy.HIERARCHICAL


# ==================== Backend Interfaces ==================== #

class SecretBackendInterface(ABC):
    """Abstract interface for secret backends."""

    @abstractmethod
    async def get_secret(self, key: str) -> str | None:
        """Retrieve a secret value."""
        pass

    @abstractmethod
    async def set_secret(self, key: str, value: str, metadata: SecretMetadata | None = None) -> bool:
        """Store a secret value."""
        pass

    @abstractmethod
    async def delete_secret(self, key: str) -> bool:
        """Delete a secret."""
        pass

    @abstractmethod
    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List available secrets."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check backend health."""
        pass


class ConfigurationBackendInterface(ABC):
    """Abstract interface for configuration backends."""

    @abstractmethod
    async def load_config(self, name: str) -> dict[str, Any]:
        """Load configuration from backend."""
        pass

    @abstractmethod
    async def save_config(self, name: str, config: dict[str, Any]) -> bool:
        """Save configuration to backend."""
        pass


# ==================== Backend Implementations ==================== #

class VaultSecretBackend(SecretBackendInterface):
    """HashiCorp Vault backend for secrets."""

    def __init__(self, vault_client: VaultClient):
        self.vault_client = vault_client

    async def get_secret(self, key: str) -> str | None:
        """Get secret from Vault."""
        try:
            secret = await self.vault_client.read_secret(key)
            if secret and 'value' in secret.data:
                return secret.data['value']
        except Exception as e:
            logger.error(f"Failed to get secret from Vault: {e}")
        return None

    async def set_secret(self, key: str, value: str, metadata: SecretMetadata | None = None) -> bool:
        """Set secret in Vault."""
        try:
            data = {"value": value}
            vault_metadata = {}

            if metadata:
                vault_metadata.update(metadata.tags)
                if metadata.expires_at:
                    vault_metadata["expires_at"] = metadata.expires_at.isoformat()

            return await self.vault_client.write_secret(key, data, vault_metadata)
        except Exception as e:
            logger.error(f"Failed to set secret in Vault: {e}")
            return False

    async def delete_secret(self, key: str) -> bool:
        """Delete secret from Vault."""
        try:
            return await self.vault_client.delete_secret(key)
        except Exception as e:
            logger.error(f"Failed to delete secret from Vault: {e}")
            return False

    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List secrets from Vault."""
        try:
            return await self.vault_client.list_secrets(prefix)
        except Exception as e:
            logger.error(f"Failed to list secrets from Vault: {e}")
            return []

    async def health_check(self) -> bool:
        """Check Vault health."""
        try:
            # Use a simple secret read to test connectivity
            await self.vault_client.read_secret("health_check")
            return True
        except Exception:
            return False


class AWSSecretsManagerBackend(SecretBackendInterface):
    """AWS Secrets Manager backend with optional boto3 dependency."""

    def __init__(self, region_name: str = "us-east-1", profile_name: str | None = None):
        self.region_name = region_name
        self.profile_name = profile_name
        self._client = None
        self._available = None

    def _check_availability(self) -> bool:
        """Check if AWS SDK is available."""
        if self._available is None:
            try:
                import boto3
                self._available = True
            except ImportError:
                self._available = False
                logger.warning("boto3 not available - AWS Secrets Manager backend disabled")
        return self._available

    @property
    def client(self):
        """Lazy initialization of AWS client."""
        if not self._check_availability():
            raise RuntimeError("boto3 is required for AWS Secrets Manager backend")

        if self._client is None:
            import boto3
            session = boto3.Session(profile_name=self.profile_name)
            self._client = session.client('secretsmanager', region_name=self.region_name)
        return self._client

    async def get_secret(self, key: str) -> str | None:
        """Get secret from AWS Secrets Manager."""
        if not self._check_availability():
            return None

        try:
            response = self.client.get_secret_value(SecretId=key)
            return response.get('SecretString')
        except Exception as e:
            logger.error(f"Failed to get secret from AWS Secrets Manager: {e}")
            return None

    async def set_secret(self, key: str, value: str, metadata: SecretMetadata | None = None) -> bool:
        """Set secret in AWS Secrets Manager."""
        if not self._check_availability():
            return False

        try:
            # Try to update existing secret
            try:
                self.client.update_secret(
                    SecretId=key,
                    SecretString=value
                )
            except self.client.exceptions.ResourceNotFoundException:
                # Create new secret
                create_params = {
                    'Name': key,
                    'SecretString': value
                }

                if metadata and metadata.tags:
                    # Convert tags to AWS format
                    aws_tags = [{'Key': k, 'Value': v} for k, v in metadata.tags.items()]
                    create_params.update({'Tags': aws_tags})

                self.client.create_secret(**create_params)

            return True
        except Exception as e:
            logger.error(f"Failed to set secret in AWS Secrets Manager: {e}")
            return False

    async def delete_secret(self, key: str) -> bool:
        """Delete secret from AWS Secrets Manager."""
        if not self._check_availability():
            return False

        try:
            self.client.delete_secret(
                SecretId=key,
                ForceDeleteWithoutRecovery=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from AWS Secrets Manager: {e}")
            return False

    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List secrets from AWS Secrets Manager."""
        if not self._check_availability():
            return []

        try:
            paginator = self.client.get_paginator('list_secrets')
            secrets = []

            for page in paginator.paginate():
                for secret in page['SecretList']:
                    name = secret['Name']
                    if not prefix or name.startswith(prefix):
                        secrets.append(name)

            return secrets
        except Exception as e:
            logger.error(f"Failed to list secrets from AWS Secrets Manager: {e}")
            return []

    async def health_check(self) -> bool:
        """Check AWS Secrets Manager health."""
        if not self._check_availability():
            return False

        try:
            # Simple operation to test connectivity
            self.client.list_secrets(MaxResults=1)
            return True
        except Exception:
            return False


class GCPSecretManagerBackend(SecretBackendInterface):
    """Google Cloud Secret Manager backend with optional google-cloud-secret-manager dependency."""

    def __init__(self, project_id: str | None = None):
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
        self._client = None
        self._available = None

    def _check_availability(self) -> bool:
        """Check if GCP SDK is available."""
        if self._available is None:
            try:
                from google.cloud import secretmanager
                self._available = True
            except ImportError:
                self._available = False
                logger.warning("google-cloud-secret-manager not available - GCP Secret Manager backend disabled")
        return self._available

    @property
    def client(self):
        """Lazy initialization of GCP client."""
        if not self._check_availability():
            raise RuntimeError("google-cloud-secret-manager is required for GCP Secret Manager backend")

        if self._client is None:
            from google.cloud import secretmanager
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    async def get_secret(self, key: str) -> str | None:
        """Get secret from GCP Secret Manager."""
        if not self._check_availability() or not self.project_id:
            return None

        try:
            name = f"projects/{self.project_id}/secrets/{key}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.error(f"Failed to get secret from GCP Secret Manager: {e}")
            return None

    async def set_secret(self, key: str, value: str, metadata: SecretMetadata | None = None) -> bool:
        """Set secret in GCP Secret Manager."""
        if not self._check_availability() or not self.project_id:
            return False

        try:
            parent = f"projects/{self.project_id}"

            # Try to create secret first
            try:
                secret = {"replication": {"automatic": {}}}
                if metadata and metadata.tags:
                    secret["labels"] = metadata.tags

                self.client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": key,
                        "secret": secret
                    }
                )
            except Exception:
                # Secret might already exist
                pass

            # Add version
            secret_name = f"{parent}/secrets/{key}"
            self.client.add_secret_version(
                request={
                    "parent": secret_name,
                    "payload": {"data": value.encode("UTF-8")}
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set secret in GCP Secret Manager: {e}")
            return False

    async def delete_secret(self, key: str) -> bool:
        """Delete secret from GCP Secret Manager."""
        if not self._check_availability() or not self.project_id:
            return False

        try:
            name = f"projects/{self.project_id}/secrets/{key}"
            self.client.delete_secret(request={"name": name})
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from GCP Secret Manager: {e}")
            return False

    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List secrets from GCP Secret Manager."""
        if not self._check_availability() or not self.project_id:
            return []

        try:
            parent = f"projects/{self.project_id}"
            secrets = []

            for secret in self.client.list_secrets(request={"parent": parent}):
                secret_id = secret.name.split('/')[-1]
                if not prefix or secret_id.startswith(prefix):
                    secrets.append(secret_id)

            return secrets
        except Exception as e:
            logger.error(f"Failed to list secrets from GCP Secret Manager: {e}")
            return []

    async def health_check(self) -> bool:
        """Check GCP Secret Manager health."""
        if not self._check_availability() or not self.project_id:
            return False

        try:
            parent = f"projects/{self.project_id}"
            # Simple operation to test connectivity
            list(self.client.list_secrets(request={"parent": parent, "page_size": 1}))
            return True
        except Exception:
            return False


class AzureKeyVaultBackend(SecretBackendInterface):
    """Azure Key Vault backend with optional azure-keyvault-secrets dependency."""

    def __init__(self, vault_url: str | None = None):
        self.vault_url = vault_url or os.getenv('AZURE_KEY_VAULT_URL')
        self._client = None
        self._available = None

    def _check_availability(self) -> bool:
        """Check if Azure SDK is available."""
        if self._available is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient
                self._available = True
            except ImportError:
                self._available = False
                logger.warning("azure-keyvault-secrets not available - Azure Key Vault backend disabled")
        return self._available

    @property
    def client(self):
        """Lazy initialization of Azure client."""
        if not self._check_availability():
            raise RuntimeError("azure-keyvault-secrets is required for Azure Key Vault backend")

        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self.vault_url, credential=credential)
        return self._client

    async def get_secret(self, key: str) -> str | None:
        """Get secret from Azure Key Vault."""
        if not self._check_availability() or not self.vault_url:
            return None

        try:
            secret = self.client.get_secret(key)
            return secret.value
        except Exception as e:
            logger.error(f"Failed to get secret from Azure Key Vault: {e}")
            return None

    async def set_secret(self, key: str, value: str, metadata: SecretMetadata | None = None) -> bool:
        """Set secret in Azure Key Vault."""
        if not self._check_availability() or not self.vault_url:
            return False

        try:
            tags = metadata.tags if metadata else None
            self.client.set_secret(key, value, tags=tags)
            return True
        except Exception as e:
            logger.error(f"Failed to set secret in Azure Key Vault: {e}")
            return False

    async def delete_secret(self, key: str) -> bool:
        """Delete secret from Azure Key Vault."""
        if not self._check_availability() or not self.vault_url:
            return False

        try:
            self.client.begin_delete_secret(key).wait()
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from Azure Key Vault: {e}")
            return False

    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List secrets from Azure Key Vault."""
        if not self._check_availability() or not self.vault_url:
            return []

        try:
            secrets = []
            for secret_properties in self.client.list_properties_of_secrets():
                name = secret_properties.name
                if not prefix or name.startswith(prefix):
                    secrets.append(name)
            return secrets
        except Exception as e:
            logger.error(f"Failed to list secrets from Azure Key Vault: {e}")
            return []

    async def health_check(self) -> bool:
        """Check Azure Key Vault health."""
        if not self._check_availability() or not self.vault_url:
            return False

        try:
            # Simple operation to test connectivity
            list(self.client.list_properties_of_secrets(max_page_size=1))
            return True
        except Exception:
            return False


# ==================== Environment Detection ==================== #

class EnvironmentDetector:
    """Automatically detect the hosting environment and suggest appropriate backends."""

    @staticmethod
    def detect_hosting_environment() -> HostingEnvironment:
        """Detect the current hosting environment."""
        # Check for AWS
        if any(var in os.environ for var in ['AWS_EXECUTION_ENV', 'AWS_LAMBDA_FUNCTION_NAME', 'AWS_REGION']):
            return HostingEnvironment.AWS

        # Check for Google Cloud
        if any(var in os.environ for var in ['GOOGLE_CLOUD_PROJECT', 'GCLOUD_PROJECT', 'GCP_PROJECT']):
            return HostingEnvironment.GOOGLE_CLOUD

        # Check for Azure
        if any(var in os.environ for var in ['AZURE_CLIENT_ID', 'AZURE_SUBSCRIPTION_ID']):
            return HostingEnvironment.AZURE

        # Check for Kubernetes
        if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount'):
            return HostingEnvironment.KUBERNETES

        # Check for Docker
        if os.path.exists('/.dockerenv') or os.path.exists('/proc/1/cgroup'):
            try:
                with open('/proc/1/cgroup') as f:
                    if 'docker' in f.read():
                        return HostingEnvironment.DOCKER
            except (FileNotFoundError, PermissionError):
                pass

        # Check if running locally
        if os.getenv('ENVIRONMENT', '').lower() in ['local', 'development', 'dev']:
            return HostingEnvironment.LOCAL

        # Default to self-hosted
        return HostingEnvironment.SELF_HOSTED

    @staticmethod
    def get_recommended_backends(hosting_env: HostingEnvironment) -> list[SecretBackend]:
        """Get recommended secret backends for the hosting environment."""
        recommendations = {
            HostingEnvironment.AWS: [
                SecretBackend.AWS_SECRETS_MANAGER,
                SecretBackend.ENVIRONMENT,
                SecretBackend.FILE
            ],
            HostingEnvironment.GOOGLE_CLOUD: [
                SecretBackend.GCP_SECRET_MANAGER,
                SecretBackend.ENVIRONMENT,
                SecretBackend.FILE
            ],
            HostingEnvironment.AZURE: [
                SecretBackend.AZURE_KEY_VAULT,
                SecretBackend.ENVIRONMENT,
                SecretBackend.FILE
            ],
            HostingEnvironment.KUBERNETES: [
                SecretBackend.KUBERNETES,
                SecretBackend.VAULT,
                SecretBackend.ENVIRONMENT
            ],
            HostingEnvironment.DOCKER: [
                SecretBackend.ENVIRONMENT,
                SecretBackend.FILE,
                SecretBackend.VAULT
            ],
            HostingEnvironment.LOCAL: [
                SecretBackend.FILE,
                SecretBackend.ENVIRONMENT,
                SecretBackend.MEMORY
            ],
            HostingEnvironment.SELF_HOSTED: [
                SecretBackend.VAULT,
                SecretBackend.FILE,
                SecretBackend.ENVIRONMENT
            ]
        }

        return recommendations.get(hosting_env, [SecretBackend.ENVIRONMENT, SecretBackend.FILE])

    @staticmethod
    def detect_available_backends() -> list[SecretBackend]:
        """Detect which secret backends are available in the current environment."""
        available = [SecretBackend.ENVIRONMENT, SecretBackend.MEMORY, SecretBackend.FILE]

        # Check Vault availability
        if VAULT_INTEGRATION_AVAILABLE:
            available.append(SecretBackend.VAULT)

        # Check AWS
        try:
            import boto3
            available.append(SecretBackend.AWS_SECRETS_MANAGER)
        except ImportError:
            pass

        # Check GCP
        try:
            from google.cloud import secretmanager  # type: ignore
            available.append(SecretBackend.GCP_SECRET_MANAGER)
        except ImportError:
            pass

        # Check Azure
        try:
            from azure.keyvault.secrets import SecretClient  # type: ignore
            available.append(SecretBackend.AZURE_KEY_VAULT)
        except ImportError:
            pass

        # Check Kubernetes
        if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount'):
            available.append(SecretBackend.KUBERNETES)

        return available


class EnvironmentSecretBackend(SecretBackendInterface):
    """Environment variables backend for secrets."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    async def get_secret(self, key: str) -> str | None:
        """Get secret from environment variables."""
        env_key = f"{self.prefix}{key}" if self.prefix else key
        return os.getenv(env_key.upper().replace('/', '_'))

    async def set_secret(self, key: str, value: str, metadata: SecretMetadata | None = None) -> bool:
        """Set secret in environment (not persistent)."""
        env_key = f"{self.prefix}{key}" if self.prefix else key
        os.environ[env_key.upper().replace('/', '_')] = value
        return True

    async def delete_secret(self, key: str) -> bool:
        """Delete secret from environment."""
        env_key = f"{self.prefix}{key}" if self.prefix else key
        env_var = env_key.upper().replace('/', '_')
        if env_var in os.environ:
            del os.environ[env_var]
            return True
        return False

    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List environment variables matching pattern."""
        full_prefix = f"{self.prefix}{prefix}" if self.prefix else prefix
        full_prefix = full_prefix.upper().replace('/', '_')

        return [
            key for key in os.environ.keys()
            if key.startswith(full_prefix)
        ]

    async def health_check(self) -> bool:
        """Environment variables are always available."""
        return True


class FileSecretBackend(SecretBackendInterface):
    """File-based secret backend."""

    def __init__(self, secrets_dir: Path = Path("secrets")):
        self.secrets_dir = secrets_dir
        self.secrets_dir.mkdir(exist_ok=True, mode=0o700)

    async def get_secret(self, key: str) -> str | None:
        """Get secret from file."""
        secret_file = self.secrets_dir / key.replace('/', '_')
        try:
            if secret_file.exists():
                return secret_file.read_text().strip()
        except Exception as e:
            logger.error(f"Failed to read secret file {secret_file}: {e}")
        return None

    async def set_secret(self, key: str, value: str, metadata: SecretMetadata | None = None) -> bool:
        """Set secret in file."""
        secret_file = self.secrets_dir / key.replace('/', '_')
        try:
            secret_file.write_text(value)
            secret_file.chmod(0o600)  # Restrict permissions
            return True
        except Exception as e:
            logger.error(f"Failed to write secret file {secret_file}: {e}")
            return False

    async def delete_secret(self, key: str) -> bool:
        """Delete secret file."""
        secret_file = self.secrets_dir / key.replace('/', '_')
        try:
            if secret_file.exists():
                secret_file.unlink()
                return True
        except Exception as e:
            logger.error(f"Failed to delete secret file {secret_file}: {e}")
        return False

    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List secret files."""
        try:
            pattern = f"{prefix.replace('/', '_')}*" if prefix else "*"
            return [f.name for f in self.secrets_dir.glob(pattern) if f.is_file()]
        except Exception as e:
            logger.error(f"Failed to list secret files: {e}")
            return []

    async def health_check(self) -> bool:
        """Check if secrets directory is accessible."""
        return self.secrets_dir.exists() and self.secrets_dir.is_dir()


# ==================== Main Unified Configuration Manager ==================== #

class UnifiedConfigurationManager(Generic[T]):
    """
    Unified configuration and secret management system.

    Consolidates all configuration loading patterns and provides a single interface
    for managing application configuration and secrets across multiple backends.
    """

    def __init__(
        self,
        context: ConfigurationContext,
        config_class: builtins.type[T] = BaseSettings,
        secret_backends: list[SecretBackendInterface] | None = None,
    ):
        """Initialize the unified configuration manager."""
        self.context = context
        self.config_class = config_class

        # Secret management
        self.secret_backends = secret_backends or []
        self.secret_cache: dict[str, tuple[str, datetime]] = {}
        self.secret_metadata: dict[str, SecretMetadata] = {}

        # Configuration cache
        self.config_cache: dict[str, tuple[Any, datetime]] = {}

        # Internal state
        self._initialized = False
        self._config_instance: T | None = None

    async def initialize(self) -> None:
        """Initialize the configuration manager."""
        if self._initialized:
            return

        logger.info(f"Initializing unified configuration manager for {self.context.service_name}")

        # Validate secret backends
        for backend in self.secret_backends:
            try:
                health = await backend.health_check()
                backend_name = backend.__class__.__name__
                if health:
                    logger.info(f"✓ Secret backend {backend_name} is healthy")
                else:
                    logger.warning(f"⚠ Secret backend {backend_name} failed health check")
            except Exception as e:
                logger.error(f"Error checking backend health: {e}")

        self._initialized = True

    async def get_configuration(self, reload: bool = False) -> T:
        """
        Get the complete configuration object.

        Args:
            reload: Force reload from sources

        Returns:
            Configured and validated configuration object
        """
        if not reload and self._config_instance:
            return self._config_instance

        # Load base configuration
        config_data = await self._load_hierarchical_config()

        # Resolve secrets
        await self._resolve_secret_references(config_data)

        # Create and validate configuration object
        try:
            self._config_instance = self.config_class(**config_data)
            logger.info(f"Configuration loaded successfully for {self.context.service_name}")
            return self._config_instance
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

    async def _load_hierarchical_config(self) -> dict[str, Any]:
        """Load configuration using hierarchical strategy."""
        config_data = {}

        # 1. Load base configuration
        if self.context.config_dir:
            base_path = self.context.config_dir / "base.yaml"
            if base_path.exists():
                config_data.update(self._load_yaml_file(base_path))

        # 2. Load environment-specific configuration
        if self.context.config_dir:
            env_path = self.context.config_dir / f"{self.context.environment.value}.yaml"
            if env_path.exists():
                config_data.update(self._load_yaml_file(env_path))

        # 3. Load plugin configurations
        if self.context.enable_plugins and self.context.plugins_dir:
            plugin_configs = await self._load_plugin_configurations()
            if plugin_configs:
                if 'plugins' not in config_data:
                    config_data['plugins'] = {}
                config_data['plugins'].update(plugin_configs)

        # 4. Load environment variables
        env_config = self._load_environment_variables()
        config_data.update(env_config)

        return config_data

        # 1. Load base configuration
        if self.context.config_dir:
            base_path = self.context.config_dir / "base.yaml"
            if base_path.exists():
                config_data.update(self._load_yaml_file(base_path))

        # 2. Load environment-specific configuration
        if self.context.config_dir:
            env_path = self.context.config_dir / f"{self.context.environment.value}.yaml"
            if env_path.exists():
                config_data.update(self._load_yaml_file(env_path))

        # 3. Load environment variables
        env_config = self._load_environment_variables()
        config_data.update(env_config)

        return config_data

    def _load_yaml_file(self, file_path: Path) -> dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(file_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
            return {}

    def _load_environment_variables(self) -> dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        prefix = f"{self.context.service_name.upper()}_"

        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                # Handle nested keys (e.g., DATABASE_HOST -> database.host)
                if '_' in config_key:
                    parts = config_key.split('_')
                    current = config
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[parts[-1]] = value
                else:
                    config[config_key] = value

        return config

    async def _load_plugin_configurations(self) -> dict[str, Any]:
        """Load plugin configurations from the plugins directory."""
        plugin_configs = {}

        if not self.context.plugins_dir or not self.context.plugins_dir.exists():
            logger.debug(f"Plugin directory not found: {self.context.plugins_dir}")
            return plugin_configs

        try:
            for plugin_file in self.context.plugins_dir.glob("*.yaml"):
                plugin_name = plugin_file.stem
                logger.debug(f"Loading plugin configuration: {plugin_name}")

                plugin_config = self._load_yaml_file(plugin_file)
                if plugin_config:
                    # Add metadata about the plugin source
                    plugin_config['_metadata'] = {
                        'source_file': str(plugin_file),
                        'plugin_name': plugin_name,
                        'loaded_at': datetime.now().isoformat()
                    }
                    plugin_configs[plugin_name] = plugin_config
                    logger.info(f"✓ Loaded plugin configuration: {plugin_name}")
                else:
                    logger.warning(f"Empty or invalid plugin configuration: {plugin_name}")

        except Exception as e:
            logger.error(f"Error loading plugin configurations: {e}")

        logger.info(f"Loaded {len(plugin_configs)} plugin configurations")
        return plugin_configs

    async def _resolve_secret_references(self, config_data: dict[str, Any]) -> None:
        """Resolve secret references in configuration data."""
        if not self.context.enable_secrets:
            return

        await self._resolve_secrets_recursive(config_data)

    async def _resolve_secrets_recursive(self, data: dict | list | str | Any) -> None:
        """Recursively resolve secret references."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and value.startswith("${SECRET:") and value.endswith("}"):
                    # Extract secret key
                    secret_key = value[9:-1]  # Remove ${SECRET: and }
                    secret_value = await self.get_secret(secret_key)
                    if secret_value:
                        data[key] = secret_value
                    else:
                        logger.warning(f"Secret not found: {secret_key}")
                elif isinstance(value, dict | list):
                    await self._resolve_secrets_recursive(value)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict | list):
                    await self._resolve_secrets_recursive(item)

    async def get_secret(
        self,
        key: str,
        use_cache: bool = True,
        backend_preference: list[SecretBackend] | None = None
    ) -> str | None:
        """
        Get secret value from configured backends.

        Args:
            key: Secret key
            use_cache: Whether to use cached values
            backend_preference: Ordered list of backends to try

        Returns:
            Secret value or None if not found
        """
        # Check cache first
        if use_cache and key in self.secret_cache:
            value, cached_at = self.secret_cache[key]
            if datetime.now(timezone.utc) - cached_at < self.context.cache_ttl:
                return value

        # Try backends in order
        backends_to_try = self.secret_backends
        if backend_preference:
            # Reorder backends based on preference
            preferred_backends = []
            for backend_type in backend_preference:
                for backend in self.secret_backends:
                    if self._get_backend_type(backend) == backend_type:
                        preferred_backends.append(backend)
            # Add remaining backends
            for backend in self.secret_backends:
                if backend not in preferred_backends:
                    preferred_backends.append(backend)
            backends_to_try = preferred_backends

        for backend in backends_to_try:
            try:
                value = await backend.get_secret(key)
                if value is not None:
                    # Cache the value
                    self.secret_cache[key] = (value, datetime.now(timezone.utc))
                    logger.debug(f"Secret '{key}' retrieved from {backend.__class__.__name__}")
                    return value
            except Exception as e:
                logger.error(f"Error getting secret from {backend.__class__.__name__}: {e}")

        logger.warning(f"Secret '{key}' not found in any backend")
        return None

    async def set_secret(
        self,
        key: str,
        value: str,
        backend: SecretBackend = SecretBackend.VAULT,
        metadata: SecretMetadata | None = None
    ) -> bool:
        """
        Set secret value in specified backend.

        Args:
            key: Secret key
            value: Secret value
            backend: Target backend
            metadata: Secret metadata

        Returns:
            True if successfully stored
        """
        for backend_instance in self.secret_backends:
            if self._get_backend_type(backend_instance) == backend:
                try:
                    success = await backend_instance.set_secret(key, value, metadata)
                    if success:
                        # Update cache and metadata
                        self.secret_cache[key] = (value, datetime.now(timezone.utc))
                        if metadata:
                            self.secret_metadata[key] = metadata
                        logger.info(f"Secret '{key}' stored in {backend.value}")
                        return True
                except Exception as e:
                    logger.error(f"Error setting secret in {backend.value}: {e}")

        logger.error(f"Backend {backend.value} not available for setting secret '{key}'")
        return False

    def _get_backend_type(self, backend: SecretBackendInterface) -> SecretBackend:
        """Get the backend type from backend instance."""
        class_name = backend.__class__.__name__
        if "Vault" in class_name:
            return SecretBackend.VAULT
        elif "AWS" in class_name or "SecretsManager" in class_name:
            return SecretBackend.AWS_SECRETS_MANAGER
        elif "Environment" in class_name:
            return SecretBackend.ENVIRONMENT
        elif "File" in class_name:
            return SecretBackend.FILE
        else:
            return SecretBackend.MEMORY

    async def rotate_secrets(self, keys: list[str] | None = None) -> dict[str, bool]:
        """
        Rotate secrets that need rotation.

        Args:
            keys: Specific keys to rotate, or None for all eligible

        Returns:
            Dictionary of key -> success status
        """
        if keys is None:
            # Find secrets that need rotation
            keys = []
            for key, metadata in self.secret_metadata.items():
                if self._needs_rotation(metadata):
                    keys.append(key)

        results = {}
        for key in keys:
            try:
                # Get current metadata
                metadata = self.secret_metadata.get(key)
                if not metadata:
                    results[key] = False
                    continue

                # Generate new value (would need to be implemented per secret type)
                new_value = self._generate_secret_value(key, metadata)

                # Update secret
                success = await self.set_secret(key, new_value, metadata.backend, metadata)
                results[key] = success

                if success:
                    metadata.last_rotated = datetime.now(timezone.utc)
                    logger.info(f"Successfully rotated secret '{key}'")

            except Exception as e:
                logger.error(f"Failed to rotate secret '{key}': {e}")
                results[key] = False

        return results

    def _needs_rotation(self, metadata: SecretMetadata) -> bool:
        """Check if a secret needs rotation."""
        if not metadata.rotation_interval:
            return False

        if not metadata.last_rotated:
            # Never rotated, check creation time
            next_rotation = metadata.created_at + metadata.rotation_interval
        else:
            next_rotation = metadata.last_rotated + metadata.rotation_interval

        return datetime.now(timezone.utc) >= next_rotation

    def _generate_secret_value(self, key: str, metadata: SecretMetadata) -> str:
        """Generate new secret value (placeholder - implement per type)."""
        import secrets
        return secrets.token_urlsafe(32)

    async def health_check(self) -> dict[str, bool]:
        """Check health of all configured backends."""
        health_status = {}

        for backend in self.secret_backends:
            backend_name = backend.__class__.__name__
            try:
                health_status[backend_name] = await backend.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {backend_name}: {e}")
                health_status[backend_name] = False

        return health_status


# ==================== Factory Functions ==================== #

def create_unified_config_manager(
    service_name: str,
    environment: Environment = Environment.DEVELOPMENT,
    config_class: builtins.type[T] = BaseSettings,
    config_dir: str | None = None,
    plugins_dir: str | None = None,
    enable_plugins: bool = True,
    strategy: ConfigurationStrategy = ConfigurationStrategy.AUTO_DETECT,
    hosting_environment: HostingEnvironment | None = None,
    # Explicit backend configuration
    enable_vault: bool = False,
    vault_config: dict[str, Any] | None = None,
    enable_aws_secrets: bool = False,
    aws_region: str = "us-east-1",
    enable_gcp_secrets: bool = False,
    gcp_project_id: str | None = None,
    enable_azure_keyvault: bool = False,
    azure_vault_url: str | None = None,
    enable_kubernetes_secrets: bool = False,
    enable_file_secrets: bool = True,
    secrets_dir: str | None = None
) -> UnifiedConfigurationManager[T]:
    """
    Factory function to create a cloud-agnostic unified configuration manager.

    Args:
        service_name: Name of the service
        environment: Deployment environment
        config_class: Pydantic model class for configuration
        config_dir: Path to configuration directory
        strategy: Configuration loading strategy
        hosting_environment: Override auto-detected hosting environment
        enable_vault: Whether to enable Vault backend
        vault_config: Vault configuration parameters
        enable_aws_secrets: Whether to enable AWS Secrets Manager
        aws_region: AWS region for Secrets Manager
        enable_gcp_secrets: Whether to enable GCP Secret Manager
        gcp_project_id: GCP project ID
        enable_azure_keyvault: Whether to enable Azure Key Vault
        azure_vault_url: Azure Key Vault URL
        enable_kubernetes_secrets: Whether to enable Kubernetes secrets
        enable_file_secrets: Whether to enable file-based secrets
        secrets_dir: Directory for secret files

    Returns:
        Configured UnifiedConfigurationManager instance
    """
    # Detect hosting environment
    detected_env = hosting_environment or EnvironmentDetector.detect_hosting_environment()
    available_backends = EnvironmentDetector.detect_available_backends()

    logger.info(f"Detected hosting environment: {detected_env.value}")
    logger.info(f"Available secret backends: {[b.value for b in available_backends]}")

    # Create context
    context = ConfigurationContext(
        service_name=service_name,
        environment=environment,
        config_dir=Path(config_dir) if config_dir else None,
        plugins_dir=Path(plugins_dir) if plugins_dir else None,
        enable_plugins=enable_plugins,
        strategy=strategy
    )

    # Setup secret backends based on strategy
    secret_backends = []

    if strategy == ConfigurationStrategy.AUTO_DETECT:
        # Use recommended backends for the hosting environment
        recommended = EnvironmentDetector.get_recommended_backends(detected_env)

        for backend_type in recommended:
            if backend_type not in available_backends:
                continue

            try:
                if backend_type == SecretBackend.ENVIRONMENT:
                    secret_backends.append(EnvironmentSecretBackend(prefix=f"{service_name.upper()}_"))

                elif backend_type == SecretBackend.AWS_SECRETS_MANAGER and detected_env == HostingEnvironment.AWS:
                    secret_backends.append(AWSSecretsManagerBackend(region_name=aws_region))

                elif backend_type == SecretBackend.GCP_SECRET_MANAGER and detected_env == HostingEnvironment.GOOGLE_CLOUD:
                    project_id = gcp_project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
                    if project_id:
                        secret_backends.append(GCPSecretManagerBackend(project_id=project_id))

                elif backend_type == SecretBackend.AZURE_KEY_VAULT and detected_env == HostingEnvironment.AZURE:
                    vault_url = azure_vault_url or os.getenv('AZURE_KEY_VAULT_URL')
                    if vault_url:
                        secret_backends.append(AzureKeyVaultBackend(vault_url=vault_url))

                elif backend_type == SecretBackend.KUBERNETES and detected_env == HostingEnvironment.KUBERNETES:
                    # Kubernetes backend would be implemented here
                    logger.info("Kubernetes secrets backend would be enabled")

                elif backend_type == SecretBackend.VAULT:
                    if VAULT_INTEGRATION_AVAILABLE and vault_config:
                        vault_client_config = VaultConfig(**vault_config)
                        vault_client = VaultClient(vault_client_config)
                        secret_backends.append(VaultSecretBackend(vault_client))

                elif backend_type == SecretBackend.FILE:
                    secrets_path = Path(secrets_dir) if secrets_dir else Path("secrets")
                    secret_backends.append(FileSecretBackend(secrets_dir=secrets_path))

                elif backend_type == SecretBackend.MEMORY:
                    # Memory backend for development
                    logger.info("Memory backend would be enabled for development")

            except Exception as e:
                logger.error(f"Failed to setup {backend_type.value} backend: {e}")

    else:
        # Manual backend configuration
        secret_backends.append(EnvironmentSecretBackend(prefix=f"{service_name.upper()}_"))

        if enable_vault and vault_config and VAULT_INTEGRATION_AVAILABLE:
            try:
                vault_client_config = VaultConfig(**vault_config)
                vault_client = VaultClient(vault_client_config)
                secret_backends.append(VaultSecretBackend(vault_client))
                logger.info("Vault secret backend enabled")
            except Exception as e:
                logger.error(f"Failed to setup Vault backend: {e}")

        if enable_aws_secrets:
            try:
                secret_backends.append(AWSSecretsManagerBackend(region_name=aws_region))
                logger.info("AWS Secrets Manager backend enabled")
            except Exception as e:
                logger.error(f"Failed to setup AWS Secrets Manager backend: {e}")

        if enable_gcp_secrets:
            try:
                project_id = gcp_project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
                if project_id:
                    secret_backends.append(GCPSecretManagerBackend(project_id=project_id))
                    logger.info("GCP Secret Manager backend enabled")
            except Exception as e:
                logger.error(f"Failed to setup GCP Secret Manager backend: {e}")

        if enable_azure_keyvault:
            try:
                vault_url = azure_vault_url or os.getenv('AZURE_KEY_VAULT_URL')
                if vault_url:
                    secret_backends.append(AzureKeyVaultBackend(vault_url=vault_url))
                    logger.info("Azure Key Vault backend enabled")
            except Exception as e:
                logger.error(f"Failed to setup Azure Key Vault backend: {e}")

        if enable_file_secrets:
            secrets_path = Path(secrets_dir) if secrets_dir else Path("secrets")
            secret_backends.append(FileSecretBackend(secrets_dir=secrets_path))
            logger.info("File secret backend enabled")

    logger.info(f"Configured {len(secret_backends)} secret backends for {service_name}")

    return UnifiedConfigurationManager(
        context=context,
        config_class=config_class,
        secret_backends=secret_backends
    )


async def get_unified_config(
    service_name: str,
    config_class: builtins.type[T] = BaseSettings,
    **kwargs
) -> T:
    """
    Convenience function to get configuration using unified manager.

    Args:
        service_name: Name of the service
        config_class: Configuration class
        **kwargs: Additional arguments for create_unified_config_manager

    Returns:
        Configured configuration object
    """
    manager = create_unified_config_manager(
        service_name=service_name,
        config_class=config_class,
        **kwargs
    )

    await manager.initialize()
    return await manager.get_configuration()


# ==================== Global Manager Registry ==================== #

_global_managers: dict[str, UnifiedConfigurationManager] = {}


def register_config_manager(service_name: str, manager: UnifiedConfigurationManager) -> None:
    """Register a global configuration manager."""
    _global_managers[service_name] = manager


def get_config_manager(service_name: str) -> UnifiedConfigurationManager | None:
    """Get a registered configuration manager."""
    return _global_managers.get(service_name)


async def cleanup_all_managers() -> None:
    """Cleanup all registered managers."""
    for _manager in _global_managers.values():
        # Add cleanup logic if needed
        pass
    _global_managers.clear()
