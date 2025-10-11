"""
Configuration management for the Marty Chassis framework.

This module provides a unified configuration system that supports:
- YAML configuration files
- Environment variable overrides
- Runtime configuration updates
- Type validation and conversion
- Environment-specific configs (dev, test, prod)
"""

import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Set, TypeVar, Union

import yaml
from pydantic import BaseModel, Field, ValidationError, validator
from pydantic_settings import BaseSettings

from .exceptions import ConfigurationError

T = TypeVar("T", bound=BaseModel)


class Environment(str, Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SecurityConfig(BaseModel):
    """Security configuration."""

    jwt_secret_key: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_minutes: int = Field(
        default=30, description="JWT expiration in minutes"
    )
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    enable_cors: bool = Field(default=True, description="Enable CORS")
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")
    rate_limit_requests: int = Field(
        default=100, description="Rate limit requests per minute"
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds"
    )


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = Field(..., description="Database URL")
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max pool overflow")
    echo: bool = Field(default=False, description="Echo SQL queries")


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    service_name: str = Field(..., description="Service name for tracing")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_format: str = Field(default="json", description="Log format (json|text)")
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=8000, description="Metrics server port")
    enable_tracing: bool = Field(default=True, description="Enable distributed tracing")
    jaeger_endpoint: str | None = Field(default=None, description="Jaeger endpoint")


class ResilienceConfig(BaseModel):
    """Resilience configuration."""

    enable_circuit_breaker: bool = Field(
        default=True, description="Enable circuit breaker"
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5, description="Failure threshold"
    )
    circuit_breaker_recovery_timeout: int = Field(
        default=60, description="Recovery timeout"
    )
    retry_attempts: int = Field(default=3, description="Retry attempts")
    retry_backoff_factor: float = Field(default=2.0, description="Retry backoff factor")
    timeout_seconds: int = Field(default=30, description="Request timeout")


class ServiceConfig(BaseModel):
    """Service-specific configuration."""

    name: str = Field(..., description="Service name")
    version: str = Field(default="1.0.0", description="Service version")
    description: str = Field(default="", description="Service description")
    host: str = Field(default="0.0.0.0", description="Service host")
    port: int = Field(default=8080, description="Service port")
    debug: bool = Field(default=False, description="Debug mode")


class ChassisConfig(BaseSettings):
    """Main chassis configuration class."""

    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT)

    # Service configuration
    service: ServiceConfig = Field(default_factory=ServiceConfig)

    # Security configuration
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # Database configuration (optional)
    database: DatabaseConfig | None = None

    # Observability configuration
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    # Resilience configuration
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False

    @validator("security")
    def validate_security_config(cls, v):
        """Validate security configuration."""
        if not v.jwt_secret_key:
            raise ValueError("JWT secret key is required")
        if len(v.jwt_secret_key) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        return v

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> "ChassisConfig":
        """Load configuration from YAML file."""
        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
            return cls(**data)
        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {file_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML configuration: {e}")
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")

    @classmethod
    def from_env(cls, env_prefix: str = "CHASSIS") -> "ChassisConfig":
        """Load configuration from environment variables."""
        try:
            return cls(_env_prefix=env_prefix)
        except ValidationError as e:
            raise ConfigurationError(
                f"Environment configuration validation failed: {e}"
            )

    def to_yaml(self, file_path: str | Path) -> None:
        """Save configuration to YAML file."""
        try:
            with open(file_path, "w") as f:
                yaml.dump(self.dict(), f, default_flow_style=False, indent=2)
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}")


class ConfigManager:
    """Configuration manager for handling multiple configurations."""

    def __init__(self, config: ChassisConfig | None = None):
        self._config = config or ChassisConfig()
        self._overrides: dict[str, Any] = {}

    @property
    def config(self) -> ChassisConfig:
        """Get the current configuration."""
        return self._config

    def load_from_yaml(self, file_path: str | Path) -> None:
        """Load configuration from YAML file."""
        self._config = ChassisConfig.from_yaml(file_path)

    def load_from_env(self, env_prefix: str = "CHASSIS") -> None:
        """Load configuration from environment variables."""
        self._config = ChassisConfig.from_env(env_prefix)

    def set_override(self, key: str, value: Any) -> None:
        """Set a configuration override."""
        self._overrides[key] = value

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with override support."""
        if key in self._overrides:
            return self._overrides[key]

        # Navigate nested configuration
        obj = self._config
        for part in key.split("."):
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return default
        return obj

    def clear_overrides(self) -> None:
        """Clear all configuration overrides."""
        self._overrides.clear()

    def validate(self) -> None:
        """Validate the current configuration."""
        try:
            # Re-parse to trigger validation
            ChassisConfig(**self._config.dict())
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")


def load_config(
    yaml_file: str | Path | None = None,
    env_prefix: str = "CHASSIS",
    environment: Environment | None = None,
) -> ChassisConfig:
    """
    Load configuration with automatic environment detection.

    Priority order:
    1. YAML file (if provided)
    2. Environment variables
    3. Defaults
    """
    config = None

    # Try to load from YAML first
    if yaml_file and Path(yaml_file).exists():
        config = ChassisConfig.from_yaml(yaml_file)
    else:
        # Load from environment variables
        config = ChassisConfig.from_env(env_prefix)

    # Override environment if specified
    if environment:
        config.environment = environment

    return config


# Global configuration instance
_global_config: ConfigManager | None = None


def get_config() -> ConfigManager:
    """Get the global configuration manager."""
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager()
    return _global_config


def set_config(config: ChassisConfig) -> None:
    """Set the global configuration."""
    global _global_config
    _global_config = ConfigManager(config)
