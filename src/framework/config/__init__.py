"""
Configuration package initialization.

This package provides enterprise-grade configuration management including:
- Environment-specific configuration loading
- Type-safe configuration with validation
- Secrets management with secure storage
- Configuration hot-reloading
- Integration with external config services
- Multiple configuration sources (files, env vars, external services)
- Plugin configuration management
"""

from .manager import (  # Core classes; Enums; Providers; Utility functions; Data classes
    BaseServiceConfig,
    ConfigManager,
    ConfigMetadata,
    ConfigProvider,
    ConfigSource,
    Environment,
    EnvVarConfigProvider,
    FileConfigProvider,
    SecretManager,
    config_context,
    create_config_manager,
    create_secret_manager,
    detect_environment,
    get_config_manager,
    get_secret_manager,
    get_service_config,
    load_config_schema,
)
from .plugin_config import (
    PluginConfig,
    PluginConfigManager,
    PluginConfigProvider,
    PluginConfigSection,
    create_plugin_config_manager,
)

__all__ = [
    "BaseServiceConfig",
    # Core classes
    "ConfigManager",
    # Data classes
    "ConfigMetadata",
    # Providers
    "ConfigProvider",
    "ConfigSource",
    "EnvVarConfigProvider",
    # Enums
    "Environment",
    "FileConfigProvider",
    "SecretManager",
    "config_context",
    # Utility functions
    "create_config_manager",
    "create_secret_manager",
    "detect_environment",
    "get_config_manager",
    "get_secret_manager",
    "get_service_config",
    "load_config_schema",
    # Plugin configuration
    "PluginConfig",
    "PluginConfigSection",
    "PluginConfigProvider",
    "PluginConfigManager",
    "create_plugin_config_manager",
]
