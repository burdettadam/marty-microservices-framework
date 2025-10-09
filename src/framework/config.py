"""
Configuration system for the enterprise microservices framework.

This module provides:
- Environment-based configuration management
- Service-specific configuration validation
- Configuration inheritance and merging
- Environment variable expansion
- Validation and error handling
"""

import builtins
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
    dict,
    list,
    type,
)

import yaml

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Environment(Enum):
    """Supported environment types."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigurationError(Exception):
    """Base configuration error."""


class ValidationError(ConfigurationError):
    """Configuration validation error."""


class EnvironmentError(ConfigurationError):
    """Environment configuration error."""


@dataclass
class BaseConfigSection(ABC):
    """Base class for configuration sections."""

    @classmethod
    @abstractmethod
    def from_dict(cls: builtins.type[T], data: builtins.dict[str, Any]) -> T:  # type: ignore[name-defined]
        """Create instance from dictionary."""

    def validate(self) -> None:
        """Validate configuration section."""


@dataclass
class DatabaseConfigSection(BaseConfigSection):
    """Database configuration section."""

    host: str
    port: int
    database: str
    username: str
    password: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    ssl_mode: str = "prefer"
    connection_timeout: int = 30

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "DatabaseConfigSection":
        return cls(
            host=data.get("host", "localhost"),
            port=data.get("port", 5432),
            database=data["database"],  # Required
            username=data["username"],  # Required
            password=data["password"],  # Required
            pool_size=data.get("pool_size", 10),
            max_overflow=data.get("max_overflow", 20),
            pool_timeout=data.get("pool_timeout", 30),
            pool_recycle=data.get("pool_recycle", 3600),
            ssl_mode=data.get("ssl_mode", "prefer"),
            connection_timeout=data.get("connection_timeout", 30),
        )

    def validate(self) -> None:
        if not self.database:
            raise ValidationError("Database name is required")
        if not self.username:
            raise ValidationError("Database username is required")
        if not self.password:
            raise ValidationError("Database password is required")
        if self.port <= 0 or self.port > 65535:
            raise ValidationError(f"Invalid port number: {self.port}")
        if self.pool_size <= 0:
            raise ValidationError("Pool size must be positive")

    @property
    def connection_url(self) -> str:
        """Get database connection URL."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class SecurityConfigSection(BaseConfigSection):
    """Security configuration section."""

    @dataclass
    class TLSConfig:
        enabled: bool = True
        mtls: bool = True
        require_client_auth: bool = True
        server_cert: str = ""
        server_key: str = ""
        client_ca: str = ""
        client_cert: str = ""
        client_key: str = ""
        verify_hostname: bool = True

    @dataclass
    class AuthConfig:
        required: bool = True
        jwt_enabled: bool = True
        jwt_algorithm: str = "HS256"
        jwt_secret: str = ""
        api_key_enabled: bool = True
        client_cert_enabled: bool = True
        extract_subject: bool = True

    @dataclass
    class AuthzConfig:
        enabled: bool = True
        policy_config: str = ""
        default_action: str = "deny"

    tls: TLSConfig = field(default_factory=TLSConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    authz: AuthzConfig = field(default_factory=AuthzConfig)

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "SecurityConfigSection":
        tls_data = data.get("grpc_tls", {})
        tls_config = cls.TLSConfig(
            enabled=tls_data.get("enabled", True),
            mtls=tls_data.get("mtls", True),
            require_client_auth=tls_data.get("require_client_auth", True),
            server_cert=tls_data.get("server_cert", ""),
            server_key=tls_data.get("server_key", ""),
            client_ca=tls_data.get("client_ca", ""),
            client_cert=tls_data.get("client_cert", ""),
            client_key=tls_data.get("client_key", ""),
            verify_hostname=tls_data.get("verify_hostname", True),
        )

        auth_data = data.get("auth", {})
        jwt_data = auth_data.get("jwt", {})
        client_cert_data = auth_data.get("client_cert", {})
        auth_config = cls.AuthConfig(
            required=auth_data.get("required", True),
            jwt_enabled=jwt_data.get("enabled", True),
            jwt_algorithm=jwt_data.get("algorithm", "HS256"),
            jwt_secret=jwt_data.get("secret", ""),
            api_key_enabled=auth_data.get("api_key_enabled", True),
            client_cert_enabled=client_cert_data.get("enabled", True),
            extract_subject=client_cert_data.get("extract_subject", True),
        )

        authz_data = data.get("authz", {})
        authz_config = cls.AuthzConfig(
            enabled=authz_data.get("enabled", True),
            policy_config=authz_data.get("policy_config", ""),
            default_action=authz_data.get("default_action", "deny"),
        )

        return cls(tls=tls_config, auth=auth_config, authz=authz_config)

    def validate(self) -> None:
        if self.tls.enabled and self.tls.mtls:
            if not self.tls.server_cert:
                raise ValidationError("Server certificate is required for mTLS")
            if not self.tls.server_key:
                raise ValidationError("Server key is required for mTLS")
            if self.tls.require_client_auth and not self.tls.client_ca:
                raise ValidationError("Client CA is required for client authentication")

        if self.auth.required and self.auth.jwt_enabled:
            if not self.auth.jwt_secret:
                raise ValidationError("JWT secret is required when JWT is enabled")

        if self.authz.enabled and not self.authz.policy_config:
            raise ValidationError(
                "Policy config path is required when authorization is enabled"
            )


@dataclass
class LoggingConfigSection(BaseConfigSection):
    """Logging configuration section."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handlers: builtins.list[str] = field(default_factory=lambda: ["console"])
    file: str | None = None
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "LoggingConfigSection":
        return cls(
            level=data.get("level", "INFO"),
            format=data.get(
                "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            handlers=data.get("handlers", ["console"]),
            file=data.get("file"),
            max_bytes=data.get("max_bytes", 10485760),
            backup_count=data.get("backup_count", 5),
        )

    def validate(self) -> None:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            raise ValidationError(f"Invalid log level: {self.level}")

        valid_handlers = ["console", "file", "syslog"]
        for handler in self.handlers:
            if handler not in valid_handlers:
                raise ValidationError(f"Invalid log handler: {handler}")

        if "file" in self.handlers and not self.file:
            raise ValidationError("File path required when file handler is enabled")


@dataclass
class MonitoringConfigSection(BaseConfigSection):
    """Monitoring configuration section."""

    enabled: bool = True
    metrics_port: int = 9090
    health_check_port: int = 8080
    prometheus_enabled: bool = True
    tracing_enabled: bool = True
    jaeger_endpoint: str = ""
    service_name: str = ""

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "MonitoringConfigSection":
        return cls(
            enabled=data.get("enabled", True),
            metrics_port=data.get("metrics_port", 9090),
            health_check_port=data.get("health_check_port", 8080),
            prometheus_enabled=data.get("prometheus_enabled", True),
            tracing_enabled=data.get("tracing_enabled", True),
            jaeger_endpoint=data.get("jaeger_endpoint", ""),
            service_name=data.get("service_name", ""),
        )

    def validate(self) -> None:
        if self.metrics_port <= 0 or self.metrics_port > 65535:
            raise ValidationError(f"Invalid metrics port: {self.metrics_port}")
        if self.health_check_port <= 0 or self.health_check_port > 65535:
            raise ValidationError(
                f"Invalid health check port: {self.health_check_port}"
            )
        if self.tracing_enabled and not self.jaeger_endpoint:
            raise ValidationError("Jaeger endpoint required when tracing is enabled")


@dataclass
class ResilienceConfigSection(BaseConfigSection):
    """Resilience configuration section."""

    @dataclass
    class CircuitBreakerConfig:
        failure_threshold: int = 5
        recovery_timeout: int = 60
        half_open_max_calls: int = 3

    @dataclass
    class RetryPolicyConfig:
        max_attempts: int = 3
        backoff_multiplier: float = 1.5
        max_delay_seconds: int = 30

    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    retry_policy: RetryPolicyConfig = field(default_factory=RetryPolicyConfig)

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "ResilienceConfigSection":
        cb_data = data.get("circuit_breaker", {})
        circuit_breaker = cls.CircuitBreakerConfig(
            failure_threshold=cb_data.get("failure_threshold", 5),
            recovery_timeout=cb_data.get("recovery_timeout", 60),
            half_open_max_calls=cb_data.get("half_open_max_calls", 3),
        )

        retry_data = data.get("retry_policy", {})
        retry_policy = cls.RetryPolicyConfig(
            max_attempts=retry_data.get("max_attempts", 3),
            backoff_multiplier=retry_data.get("backoff_multiplier", 1.5),
            max_delay_seconds=retry_data.get("max_delay_seconds", 30),
        )

        return cls(circuit_breaker=circuit_breaker, retry_policy=retry_policy)

    def validate(self) -> None:
        if self.circuit_breaker.failure_threshold <= 0:
            raise ValidationError("Circuit breaker failure threshold must be positive")
        if self.retry_policy.max_attempts <= 0:
            raise ValidationError("Retry max attempts must be positive")


class ServiceConfig:
    """Service-specific configuration with validation and environment support."""

    def __init__(
        self,
        service_name: str,
        environment: str | Environment = Environment.DEVELOPMENT,
        config_path: Path | None = None,
    ):
        self.service_name = service_name
        self.environment = (
            Environment(environment) if isinstance(environment, str) else environment
        )
        self.config_path = config_path

        self._raw_config: builtins.dict[str, Any] = {}
        self._database: DatabaseConfigSection | None = None
        self._security: SecurityConfigSection | None = None
        self._logging: LoggingConfigSection | None = None
        self._monitoring: MonitoringConfigSection | None = None
        self._resilience: ResilienceConfigSection | None = None

        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load and merge configuration from multiple sources."""
        # 1. Load base configuration
        base_config = self._load_base_config()

        # 2. Load environment-specific configuration
        env_config = self._load_environment_config()

        # 3. Load service-specific configuration
        service_config = self._load_service_config()

        # 4. Merge configurations (service > environment > base)
        self._raw_config = self._merge_configs(base_config, env_config, service_config)

        # 5. Expand environment variables
        self._raw_config = self._expand_env_vars(self._raw_config)

        # 6. Validate configuration
        self._validate_configuration()

    def _load_base_config(self) -> builtins.dict[str, Any]:
        """Load base configuration file."""
        if self.config_path:
            base_path = self.config_path / "base.yaml"
        else:
            base_path = Path("config") / "base.yaml"

        if base_path.exists():
            return self._load_yaml_file(base_path)
        return {}

    def _load_environment_config(self) -> builtins.dict[str, Any]:
        """Load environment-specific configuration."""
        if self.config_path:
            env_path = self.config_path / f"{self.environment.value}.yaml"
        else:
            env_path = Path("config") / f"{self.environment.value}.yaml"

        if env_path.exists():
            return self._load_yaml_file(env_path)
        return {}

    def _load_service_config(self) -> builtins.dict[str, Any]:
        """Load service-specific configuration."""
        if self.config_path:
            service_path = self.config_path / "services" / f"{self.service_name}.yaml"
        else:
            service_path = Path("config") / "services" / f"{self.service_name}.yaml"

        if service_path.exists():
            return self._load_yaml_file(service_path)
        return {}

    def _load_yaml_file(self, path: Path) -> builtins.dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(path, encoding="utf-8") as file:
                return yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML file {path}: {e}")
        except OSError as e:
            raise ConfigurationError(f"Error reading file {path}: {e}")

    def _merge_configs(
        self, *configs: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Merge multiple configuration dictionaries."""
        result = {}
        for config in configs:
            if config:
                result = self._deep_merge(result, config)
        return result

    def _deep_merge(
        self, base: builtins.dict[str, Any], override: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _expand_env_vars(self, obj: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(obj, dict):
            return {key: self._expand_env_vars(value) for key, value in obj.items()}
        if isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        if isinstance(obj, str):
            return self._expand_env_var_string(obj)
        return obj

    def _expand_env_var_string(self, value: str) -> str:
        """Expand environment variables in a string using ${VAR:-default} syntax."""
        pattern = r"\$\{([^}]+)\}"

        def replace_var(match):
            var_expr = match.group(1)
            if ":-" in var_expr:
                var_name, default_value = var_expr.split(":-", 1)
                return os.environ.get(var_name, default_value)
            return os.environ.get(var_expr, "")

        return re.sub(pattern, replace_var, value)

    def _validate_configuration(self) -> None:
        """Validate the loaded configuration."""
        # Validate required service-specific configuration exists
        if (
            "services" in self._raw_config
            and self.service_name not in self._raw_config["services"]
        ):
            logger.warning(
                "No service-specific configuration found for %s", self.service_name
            )

    @property
    def database(self) -> DatabaseConfigSection:
        """Get database configuration."""
        if not self._database:
            db_config = self._raw_config.get("database", {})

            # Support per-service database configuration
            if isinstance(db_config, dict) and self.service_name in db_config:
                service_db_config = db_config[self.service_name]
            else:
                service_db_config = db_config

            if not service_db_config:
                raise ConfigurationError(
                    f"No database configuration found for service {self.service_name}"
                )

            self._database = DatabaseConfigSection.from_dict(service_db_config)
            self._database.validate()

        return self._database

    @property
    def security(self) -> SecurityConfigSection:
        """Get security configuration."""
        if not self._security:
            security_config = self._raw_config.get("security", {})
            self._security = SecurityConfigSection.from_dict(security_config)
            self._security.validate()

        return self._security

    @property
    def logging(self) -> LoggingConfigSection:
        """Get logging configuration."""
        if not self._logging:
            logging_config = self._raw_config.get("logging", {})
            self._logging = LoggingConfigSection.from_dict(logging_config)
            self._logging.validate()

        return self._logging

    @property
    def monitoring(self) -> MonitoringConfigSection:
        """Get monitoring configuration."""
        if not self._monitoring:
            monitoring_config = self._raw_config.get("monitoring", {})
            # Set service name if not explicitly configured
            if "service_name" not in monitoring_config:
                monitoring_config["service_name"] = self.service_name

            self._monitoring = MonitoringConfigSection.from_dict(monitoring_config)
            self._monitoring.validate()

        return self._monitoring

    @property
    def resilience(self) -> ResilienceConfigSection:
        """Get resilience configuration."""
        if not self._resilience:
            resilience_config = self._raw_config.get("resilience", {})
            self._resilience = ResilienceConfigSection.from_dict(resilience_config)
            self._resilience.validate()

        return self._resilience

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        keys = key.split(".")
        value = self._raw_config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_service_config(self) -> builtins.dict[str, Any]:
        """Get service-specific configuration section."""
        services_config = self._raw_config.get("services", {})
        return services_config.get(self.service_name, {})

    def to_dict(self) -> builtins.dict[str, Any]:
        """Export configuration as dictionary."""
        return self._raw_config.copy()


def get_environment() -> Environment:
    """Get current environment from environment variable."""
    env_name = os.environ.get("SERVICE_ENV", "development").lower()
    try:
        return Environment(env_name)
    except ValueError:
        logger.warning("Invalid environment %s, defaulting to development", env_name)
        return Environment.DEVELOPMENT


def create_service_config(
    service_name: str,
    environment: str | Environment | None = None,
    config_path: Path | None = None,
) -> ServiceConfig:
    """Create a service configuration instance."""
    if environment is None:
        environment = get_environment()

    return ServiceConfig(service_name, environment, config_path)
