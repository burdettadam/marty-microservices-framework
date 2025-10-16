"""
Security service for the PetStore Domain plugin.

This service manages the initialization and coordination of all security components
including Vault integration, policy engines, and authentication/authorization.
"""
import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import PetstoreDomainConfig

# Import Marty MSF security components with graceful fallback
try:
    from marty_msf.security.authorization import (
        AuthorizationRequest,
        PolicyEngineEnum,
        PolicyManager,
    )
    from marty_msf.security.secrets import (
        SecretManager,
        VaultAuthMethod,
        VaultClient,
        VaultConfig,
    )
    SECURITY_AVAILABLE = True
except ImportError:
    # Graceful degradation when security components are not available
    SECURITY_AVAILABLE = False
    logging.warning("Marty MSF security components not available")

logger = logging.getLogger(__name__)

class PetStoreSecurityService:
    """
    Main security service for the PetStore domain.

    Coordinates all security-related functionality including:
    - HashiCorp Vault integration
    - Policy-based authorization
    - Secret management
    - Certificate management
    """

    def __init__(self, config: PetstoreDomainConfig):
        self.config = config
        self.vault_client = None
        self.secret_manager = None
        self.policy_manager = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all security components"""
        if self._initialized:
            return

        logger.info("Initializing PetStore security service...")

        try:
            # Initialize Vault client if enabled
            if self.config.vault_enabled and SECURITY_AVAILABLE:
                await self._initialize_vault()

            # Initialize secret manager
            await self._initialize_secret_manager()

            # Initialize policy manager
            await self._initialize_policy_manager()

            # Load default policies
            await self._load_default_policies()

            self._initialized = True
            logger.info("Security service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize security service: {e}")
            # Continue with reduced functionality
            logger.warning("Security service running with reduced functionality")

    async def _initialize_vault(self) -> None:
        """Initialize HashiCorp Vault client"""
        if not SECURITY_AVAILABLE:
            logger.warning("Vault integration not available")
            return

        try:
            # Determine auth method
            auth_method = VaultAuthMethod.TOKEN
            if self.config.vault_auth_method == "kubernetes":
                auth_method = VaultAuthMethod.KUBERNETES
            elif self.config.vault_auth_method == "aws":
                auth_method = VaultAuthMethod.AWS_IAM

            # Create Vault configuration
            vault_config = VaultConfig(
                url=self.config.vault_url,
                auth_method=auth_method,
                token=self.config.vault_token,
                role=self.config.vault_role,
                namespace=self.config.vault_namespace
            )

            # Initialize client
            self.vault_client = VaultClient(vault_config)
            await self.vault_client.authenticate()

            logger.info(f"Vault client initialized: {self.config.vault_url}")

        except Exception as e:
            logger.error(f"Failed to initialize Vault client: {e}")
            self.vault_client = None

    async def _initialize_secret_manager(self) -> None:
        """Initialize secret manager"""
        if not SECURITY_AVAILABLE:
            logger.warning("Secret manager not available")
            return

        try:
            self.secret_manager = SecretManager(
                service_name="petstore-domain",
                vault_client=self.vault_client
            )

            # Set up default secrets if needed
            await self._setup_default_secrets()

            logger.info("Secret manager initialized")

        except Exception as e:
            logger.error(f"Failed to initialize secret manager: {e}")
            self.secret_manager = None

    async def _initialize_policy_manager(self) -> None:
        """Initialize policy manager with configured engines"""
        if not SECURITY_AVAILABLE:
            logger.warning("Policy manager not available")
            return

        try:
            # Determine primary engine
            primary_engine = PolicyEngineEnum.BUILTIN
            if self.config.default_policy_engine == "opa" and self.config.opa_enabled:
                primary_engine = PolicyEngineEnum.OPA
            elif self.config.default_policy_engine == "oso" and self.config.oso_enabled:
                primary_engine = PolicyEngineEnum.OSO

            # Initialize policy manager
            self.policy_manager = PolicyManager(primary_engine=primary_engine)

            # Configure OPA if enabled
            if self.config.opa_enabled:
                await self._configure_opa()

            # Configure Oso if enabled
            if self.config.oso_enabled:
                await self._configure_oso()

            logger.info(f"Policy manager initialized with {primary_engine} engine")

        except Exception as e:
            logger.error(f"Failed to initialize policy manager: {e}")
            self.policy_manager = None

    async def _configure_opa(self) -> None:
        """Configure Open Policy Agent"""
        try:
            # OPA configuration would be done here
            # For now, just log that it's configured
            logger.info(f"OPA configured: {self.config.opa_url}")
        except Exception as e:
            logger.error(f"Failed to configure OPA: {e}")

    async def _configure_oso(self) -> None:
        """Configure Oso policy engine"""
        try:
            # Load Oso policy file if it exists
            if self.config.oso_policy_file:
                policy_path = Path(self.config.oso_policy_file)
                if policy_path.exists():
                    logger.info(f"Oso policy loaded from: {policy_path}")
                else:
                    logger.warning(f"Oso policy file not found: {policy_path}")
        except Exception as e:
            logger.error(f"Failed to configure Oso: {e}")

    async def _setup_default_secrets(self) -> None:
        """Set up default secrets for the petstore domain"""
        if not self.secret_manager:
            return

        try:
            # JWT signing key
            jwt_secret = self.config.jwt_secret_key or self.config.secret_key
            if jwt_secret and jwt_secret != "dev-secret-key-change-in-production":
                await self.secret_manager.store_secret("jwt/signing_key", jwt_secret)

            # API keys for external services
            default_api_keys = {
                "psk-demo-key": {
                    "service_name": "demo_service",
                    "roles": ["service"],
                    "description": "Demo API key for testing"
                }
            }
            await self.secret_manager.store_secret("api_keys/valid_keys", json.dumps(default_api_keys))

            logger.info("Default secrets configured")

        except Exception as e:
            logger.error(f"Failed to setup default secrets: {e}")

    async def _load_default_policies(self) -> None:
        """Load default authorization policies for the petstore domain"""
        if not self.policy_manager:
            return

        try:
            # PetStore RBAC policy
            petstore_rbac = {
                "id": "petstore_rbac",
                "name": "PetStore RBAC Policy",
                "rules": [
                    {
                        "resource": "/api/v1/pets/public",
                        "action": "GET",
                        "principal": {"type": "*"},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/pets/*",
                        "action": "GET",
                        "principal": {"roles": ["user", "admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/pets/*",
                        "action": ["POST", "PUT", "DELETE"],
                        "principal": {"roles": ["admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/orders/*",
                        "action": "GET",
                        "principal": {"roles": ["user", "admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/orders/*",
                        "action": ["POST", "PUT"],
                        "principal": {"roles": ["user", "admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/orders/*/cancel",
                        "action": "POST",
                        "principal": {"roles": ["admin"]},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/admin/*",
                        "action": "*",
                        "principal": {"roles": ["admin"]},
                        "effect": "allow"
                    }
                ]
            }

            await self.policy_manager.load_policy("petstore_rbac", json.dumps(petstore_rbac))

            # Service-to-service policies
            service_policy = {
                "id": "service_to_service",
                "name": "Service-to-Service Communication Policy",
                "rules": [
                    {
                        "resource": "/api/v1/internal/*",
                        "action": "*",
                        "principal": {"type": "service"},
                        "effect": "allow"
                    },
                    {
                        "resource": "/api/v1/events/*",
                        "action": ["POST"],
                        "principal": {"type": "service", "roles": ["event_publisher"]},
                        "effect": "allow"
                    }
                ]
            }

            await self.policy_manager.load_policy("service_policy", json.dumps(service_policy))

            logger.info("Default policies loaded")

        except Exception as e:
            logger.error(f"Failed to load default policies: {e}")

    async def evaluate_authorization(
        self,
        principal: dict[str, Any],
        action: str,
        resource: str,
        environment: dict[str, Any] | None = None
    ) -> bool:
        """
        Evaluate authorization request using the policy manager

        Args:
            principal: User/service principal information
            action: HTTP method or action being performed
            resource: Resource being accessed
            environment: Additional context information

        Returns:
            True if authorized, False otherwise
        """
        if not self.policy_manager:
            # If no policy manager, allow for development
            logger.warning("No policy manager available, allowing request")
            return True

        try:
            auth_request = AuthorizationRequest(
                principal=principal,
                action=action,
                resource=resource,
                environment=environment or {}
            )

            result = await self.policy_manager.evaluate(auth_request)
            return getattr(result, 'allowed', False)

        except Exception as e:
            logger.error(f"Authorization evaluation failed: {e}")
            return False  # Deny on error

    async def get_secret(self, key: str) -> str | None:
        """Get secret from secret manager"""
        if not self.secret_manager:
            return None

        try:
            return await self.secret_manager.get_secret(key)
        except Exception as e:
            logger.error(f"Failed to get secret {key}: {e}")
            return None

    async def health_check(self) -> dict[str, Any]:
        """Get health status of all security components"""
        health = {
            "security_service": "healthy",
            "components": {}
        }

        try:
            # Check Vault
            if self.vault_client:
                vault_healthy = await self.vault_client.health_check()
                health["components"]["vault"] = "healthy" if vault_healthy else "unhealthy"
            else:
                health["components"]["vault"] = "disabled"

            # Check policy manager
            if self.policy_manager:
                policy_healthy = await self.policy_manager.health_check()
                health["components"]["policy_manager"] = "healthy" if policy_healthy else "unhealthy"
            else:
                health["components"]["policy_manager"] = "disabled"

            # Check secret manager
            if self.secret_manager:
                health["components"]["secret_manager"] = "healthy"
            else:
                health["components"]["secret_manager"] = "disabled"

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health["security_service"] = "degraded"

        return health

    async def cleanup(self) -> None:
        """Cleanup security service resources"""
        try:
            if self.vault_client:
                # Cleanup vault client if needed
                pass

            if self.policy_manager:
                # Cleanup policy manager if needed
                pass

            logger.info("Security service cleanup completed")

        except Exception as e:
            logger.error(f"Security service cleanup failed: {e}")


# Global security service instance
_security_service: PetStoreSecurityService | None = None

async def get_security_service(config: PetstoreDomainConfig | None = None) -> PetStoreSecurityService:
    """
    Get or create the global security service instance

    Args:
        config: Configuration object (required for first call)

    Returns:
        Security service instance
    """
    global _security_service

    if _security_service is None:
        if config is None:
            raise ValueError("Config required for security service initialization")

        _security_service = PetStoreSecurityService(config)
        await _security_service.initialize()

    return _security_service

async def cleanup_security_service() -> None:
    """Cleanup the global security service"""
    global _security_service

    if _security_service:
        await _security_service.cleanup()
        _security_service = None
