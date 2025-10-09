"""
Plugin system exceptions.

This module defines exceptions specific to the plugin architecture,
providing clear error handling and debugging capabilities.
"""

from typing import Optional


class PluginError(Exception):
    """Base exception for all plugin-related errors."""

    def __init__(
        self,
        message: str,
        plugin_name: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        self.plugin_name = plugin_name
        self.cause = cause

        if plugin_name:
            full_message = f"Plugin '{plugin_name}': {message}"
        else:
            full_message = message

        super().__init__(full_message)


class PluginLoadError(PluginError):
    """Exception raised when a plugin fails to load."""

    def __init__(
        self, plugin_name: str, message: str, cause: Optional[Exception] = None
    ):
        super().__init__(f"Failed to load: {message}", plugin_name, cause)


class PluginStateError(PluginError):
    """Exception raised when a plugin operation is invalid for current state."""

    def __init__(self, plugin_name: str, current_state: str, required_state: str):
        message = f"Operation requires state '{required_state}' but plugin is in state '{current_state}'"
        super().__init__(message, plugin_name)


class PluginDependencyError(PluginError):
    """Exception raised when plugin dependencies cannot be resolved."""

    def __init__(self, plugin_name: str, missing_dependencies: list):
        deps = ", ".join(missing_dependencies)
        message = f"Missing dependencies: {deps}"
        super().__init__(message, plugin_name)


class PluginConfigurationError(PluginError):
    """Exception raised when plugin configuration is invalid."""

    def __init__(self, plugin_name: str, config_error: str):
        super().__init__(f"Configuration error: {config_error}", plugin_name)


class PluginDiscoveryError(PluginError):
    """Exception raised during plugin discovery."""

    def __init__(self, message: str, path: Optional[str] = None):
        if path:
            full_message = f"Discovery error in '{path}': {message}"
        else:
            full_message = f"Discovery error: {message}"
        super().__init__(full_message)
