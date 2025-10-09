"""
Plugin architecture interfaces and base classes.

This module defines the core interfaces that all plugins must implement,
along with supporting data structures for plugin metadata and context.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from ..logger import get_logger


class PluginState(str, Enum):
    """Plugin lifecycle states."""

    UNLOADED = "unloaded"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """Plugin metadata and configuration."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    entry_points: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validate metadata after initialization."""
        if not self.name:
            raise ValueError("Plugin name is required")
        if not self.version:
            raise ValueError("Plugin version is required")


@dataclass
class PluginContext:
    """Context provided to plugins during initialization."""

    config: Dict[str, Any]
    logger: Any
    metrics_collector: Any
    event_bus: Any
    service_registry: Any
    extension_points: Any
    core_services: Any
    plugin_config: Dict[str, Any] = field(default_factory=dict)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with optional default."""
        return self.plugin_config.get(key, default)


class IPlugin(ABC):
    """
    Base interface for all plugins.

    Defines the core lifecycle methods that all plugins must implement
    to participate in the plugin system.
    """

    def __init__(self):
        self.metadata: Optional[PluginMetadata] = None
        self.state: PluginState = PluginState.UNLOADED
        self.context: Optional[PluginContext] = None
        self.logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass

    async def load(self) -> None:
        """
        Load the plugin but don't initialize it yet.

        This is where the plugin can perform any one-time setup
        that doesn't require access to the framework context.
        """
        self.state = PluginState.LOADED
        self.logger.debug(f"Plugin {self.plugin_metadata.name} loaded")

    @abstractmethod
    async def initialize(self, context: PluginContext) -> None:
        """
        Initialize the plugin with the framework context.

        Args:
            context: The plugin context containing access to core services
        """
        self.context = context
        self.state = PluginState.INITIALIZED
        self.logger.info(f"Plugin {self.plugin_metadata.name} initialized")

    async def start(self) -> None:
        """
        Start the plugin.

        This is where the plugin should begin its active operations,
        register event handlers, start background tasks, etc.
        """
        if self.state != PluginState.INITIALIZED:
            raise RuntimeError(f"Plugin must be initialized before starting")

        self.state = PluginState.STARTED
        self.logger.info(f"Plugin {self.plugin_metadata.name} started")

    async def stop(self) -> None:
        """
        Stop the plugin gracefully.

        Clean up resources, stop background tasks, unregister handlers.
        """
        if self.state == PluginState.STARTED:
            self.state = PluginState.STOPPED
            self.logger.info(f"Plugin {self.plugin_metadata.name} stopped")

    async def unload(self) -> None:
        """
        Unload the plugin completely.

        Perform final cleanup and prepare for removal from the system.
        """
        await self.stop()
        self.state = PluginState.UNLOADED
        self.logger.debug(f"Plugin {self.plugin_metadata.name} unloaded")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the plugin.

        Returns:
            Dict containing health status and details
        """
        return {
            "name": self.plugin_metadata.name,
            "state": self.state.value,
            "healthy": self.state == PluginState.STARTED,
            "details": {},
        }


class IServicePlugin(IPlugin):
    """
    Interface for plugins that provide service registry hooks.

    Service plugins can participate in service discovery, registration,
    and lifecycle management.
    """

    @abstractmethod
    async def on_service_register(self, service_info: Dict[str, Any]) -> None:
        """Called when a service is being registered."""
        pass

    @abstractmethod
    async def on_service_unregister(self, service_info: Dict[str, Any]) -> None:
        """Called when a service is being unregistered."""
        pass

    async def on_service_discovery(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Called during service discovery.

        Args:
            query: Service discovery query parameters

        Returns:
            List of matching services this plugin knows about
        """
        return []


class IMiddlewarePlugin(IPlugin):
    """
    Interface for plugins that provide middleware functionality.

    Middleware plugins can process requests and responses,
    adding cross-cutting concerns like authentication, logging, etc.
    """

    @abstractmethod
    async def process_request(self, request: Any, call_next) -> Any:
        """
        Process an incoming request.

        Args:
            request: The incoming request object
            call_next: Function to call the next middleware/handler

        Returns:
            Response object
        """
        pass

    @abstractmethod
    def get_middleware_priority(self) -> int:
        """
        Return the priority of this middleware (lower = higher priority).

        Returns:
            Integer priority value
        """
        pass


class IEventHandlerPlugin(IPlugin):
    """
    Interface for plugins that handle events in the system.

    Event handler plugins can subscribe to and publish events,
    enabling loose coupling between components.
    """

    @abstractmethod
    def get_event_subscriptions(self) -> Dict[str, str]:
        """
        Return event subscriptions for this plugin.

        Returns:
            Dict mapping event types to handler method names
        """
        pass

    @abstractmethod
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Handle an event.

        Args:
            event_type: Type of the event
            event_data: Event payload data
        """
        pass

    async def publish_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Publish an event to the system.

        Args:
            event_type: Type of the event
            event_data: Event payload data
        """
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(event_type, event_data)


class IHealthPlugin(IPlugin):
    """
    Interface for plugins that provide custom health checks.

    Health plugins can add custom health indicators and
    participate in overall system health monitoring.
    """

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """
        Perform a detailed health check.

        Returns:
            Dict with health status and detailed information
        """
        pass

    @abstractmethod
    def get_health_check_interval(self) -> int:
        """
        Return the interval (in seconds) for periodic health checks.

        Returns:
            Interval in seconds, or 0 to disable periodic checks
        """
        pass


class IMetricsPlugin(IPlugin):
    """
    Interface for plugins that provide custom metrics.

    Metrics plugins can expose custom metrics and
    participate in system observability.
    """

    @abstractmethod
    async def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect plugin-specific metrics.

        Returns:
            Dict containing metric names and values
        """
        pass

    @abstractmethod
    def get_metric_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        Return metric definitions for this plugin.

        Returns:
            Dict mapping metric names to their definitions
        """
        pass
