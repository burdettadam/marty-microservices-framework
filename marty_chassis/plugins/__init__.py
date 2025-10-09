"""
Plugin Architecture for Marty Chassis Framework

This module provides a comprehensive plugin architecture that allows for extensible
microservices functionality through well-defined interfaces and extension points.

Key Features:
- Abstract plugin interfaces for different types of extensions
- Plugin lifecycle management (load, initialize, start, stop, unload)
- Service registry hooks for dynamic service discovery
- Middleware registration for request/response processing
- Event handler system for decoupled communication
- Plugin isolation and sandboxing
- Dynamic loading from directories or entry points
- Core services access (config, logging, metrics)

Plugin Types:
- IPlugin: Base plugin interface
- IServicePlugin: Service registration and discovery hooks
- IMiddlewarePlugin: Request/response middleware
- IEventHandlerPlugin: Event-driven communication
- IHealthPlugin: Health check extensions
- IMetricsPlugin: Custom metrics collection

Usage:
    >>> from marty_chassis.plugins import PluginManager, IPlugin
    >>> from marty_chassis.plugins.decorators import plugin

    @plugin(name="my-plugin", version="1.0.0")
    class MyPlugin(IPlugin):
        async def initialize(self, context):
            self.logger = context.logger
            await self.setup_resources()

        async def start(self):
            self.logger.info("Plugin started")
"""

from .core_services import CoreServices
from .decorators import event_handler, middleware, plugin, service_hook
from .discovery import DirectoryPluginDiscoverer, EntryPointDiscoverer
from .exceptions import PluginError, PluginLoadError, PluginStateError
from .extension_points import ExtensionPoint, ExtensionPointManager
from .factory import PluginEnabledServiceFactory, create_plugin_enabled_fastapi_service
from .interfaces import (
    IEventHandlerPlugin,
    IHealthPlugin,
    IMetricsPlugin,
    IMiddlewarePlugin,
    IPlugin,
    IServicePlugin,
    PluginContext,
    PluginMetadata,
    PluginState,
)
from .manager import PluginManager

__all__ = [
    # Core interfaces
    "IPlugin",
    "IServicePlugin",
    "IMiddlewarePlugin",
    "IEventHandlerPlugin",
    "IHealthPlugin",
    "IMetricsPlugin",
    "PluginContext",
    "PluginMetadata",
    "PluginState",
    # Plugin management
    "PluginManager",
    # Discovery mechanisms
    "DirectoryPluginDiscoverer",
    "EntryPointDiscoverer",
    # Decorators
    "plugin",
    "service_hook",
    "middleware",
    "event_handler",
    # Extension points
    "ExtensionPointManager",
    "ExtensionPoint",
    # Core services
    "CoreServices",
    # Plugin-enabled factories
    "PluginEnabledServiceFactory",
    "create_plugin_enabled_fastapi_service",
    # Exceptions
    "PluginError",
    "PluginLoadError",
    "PluginStateError",
]
