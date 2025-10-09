"""
Core services provided to plugins.

This module defines the core services that plugins can access,
including configuration, logging, metrics, and event bus functionality.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..config import ChassisConfig
from ..logger import get_logger


@dataclass
class EventBusMessage:
    """Event bus message structure."""

    event_type: str
    event_data: Dict[str, Any]
    source: str
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    correlation_id: Optional[str] = None


class EventBus:
    """
    Simple event bus for plugin communication.

    Provides publish/subscribe functionality for loose coupling
    between plugins and framework components.
    """

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.logger = get_logger(self.__class__.__name__)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Handler function to call
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        self.logger.debug(f"Subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """
        Unsubscribe from an event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        if event_type in self.subscribers and handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
            self.logger.debug(f"Unsubscribed from event: {event_type}")

    async def publish(
        self, event_type: str, event_data: Dict[str, Any], source: str = "unknown"
    ) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event_type: Type of event to publish
            event_data: Event payload data
            source: Source of the event
        """
        message = EventBusMessage(
            event_type=event_type, event_data=event_data, source=source
        )

        handlers = self.subscribers.get(event_type, [])
        if handlers:
            self.logger.debug(
                f"Publishing event {event_type} to {len(handlers)} handlers"
            )
            tasks = []
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        tasks.append(handler(message))
                    else:
                        # Run sync handlers in thread pool
                        future = asyncio.get_event_loop().run_in_executor(
                            None, handler, message
                        )
                        tasks.append(future)
                except Exception as e:
                    self.logger.error(f"Error creating task for event handler: {e}")

            if tasks:
                # Wait for all handlers but don't fail if one fails
                await asyncio.gather(*tasks, return_exceptions=True)


class ServiceRegistry:
    """
    Simple service registry for service discovery.

    Allows plugins to register and discover services
    within the framework ecosystem.
    """

    def __init__(self):
        self.services: Dict[str, Dict[str, Any]] = {}
        self.logger = get_logger(self.__class__.__name__)

    def register_service(self, name: str, service_info: Dict[str, Any]) -> None:
        """
        Register a service.

        Args:
            name: Service name
            service_info: Service metadata and connection info
        """
        self.services[name] = {
            **service_info,
            "registered_at": asyncio.get_event_loop().time(),
        }
        self.logger.info(f"Registered service: {name}")

    def unregister_service(self, name: str) -> None:
        """
        Unregister a service.

        Args:
            name: Service name to unregister
        """
        if name in self.services:
            del self.services[name]
            self.logger.info(f"Unregistered service: {name}")

    def discover_service(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Discover a service by name.

        Args:
            name: Service name to find

        Returns:
            Service info if found, None otherwise
        """
        return self.services.get(name)

    def discover_services(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Discover services by tag.

        Args:
            tag: Optional tag to filter by

        Returns:
            List of matching services
        """
        if tag is None:
            return list(self.services.values())

        return [
            service
            for service in self.services.values()
            if tag in service.get("tags", [])
        ]

    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """List all registered services."""
        return self.services.copy()


class CoreServices:
    """
    Container for core services provided to plugins.

    This class aggregates all the core services that plugins
    can access through their context.
    """

    def __init__(self, config: ChassisConfig, metrics_collector=None):
        """
        Initialize core services.

        Args:
            config: Framework configuration
            metrics_collector: Optional metrics collector
        """
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

        # Initialize core services
        self.event_bus = EventBus()
        self.service_registry = ServiceRegistry()
        self.metrics_collector = metrics_collector

        # Extension points registry
        self.extension_points: Dict[str, List[Callable]] = {}

        self.logger.info("Core services initialized")

    def register_extension_point(self, name: str, handler: Callable) -> None:
        """
        Register an extension point handler.

        Args:
            name: Extension point name
            handler: Handler function
        """
        if name not in self.extension_points:
            self.extension_points[name] = []
        self.extension_points[name].append(handler)
        self.logger.debug(f"Registered extension point: {name}")

    def unregister_extension_point(self, name: str, handler: Callable) -> None:
        """
        Unregister an extension point handler.

        Args:
            name: Extension point name
            handler: Handler function to remove
        """
        if name in self.extension_points and handler in self.extension_points[name]:
            self.extension_points[name].remove(handler)
            self.logger.debug(f"Unregistered extension point: {name}")

    async def call_extension_point(self, name: str, *args, **kwargs) -> List[Any]:
        """
        Call all handlers for an extension point.

        Args:
            name: Extension point name
            *args: Arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers

        Returns:
            List of results from all handlers
        """
        handlers = self.extension_points.get(name, [])
        if not handlers:
            return []

        results = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(*args, **kwargs)
                else:
                    result = handler(*args, **kwargs)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error calling extension point {name}: {e}")
                results.append(None)

        return results

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found

        Returns:
            Configuration value
        """
        try:
            # Support dot notation for nested config
            keys = key.split(".")
            value = self.config
            for k in keys:
                if hasattr(value, k):
                    value = getattr(value, k)
                else:
                    return default
            return value
        except (AttributeError, KeyError):
            return default

    async def shutdown(self) -> None:
        """Shutdown all core services."""
        self.logger.info("Shutting down core services")
        # Add any cleanup logic here
