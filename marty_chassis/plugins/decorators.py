"""
Plugin decorators for easy plugin development.

This module provides decorators that simplify plugin creation
and registration of various plugin types and extension points.
"""

import functools
import inspect
from typing import Any

from .interfaces import PluginMetadata


def plugin(
    name: str,
    version: str,
    description: str = "",
    author: str = "",
    dependencies: list[str] | None = None,
    provides: list[str] | None = None,
    config_schema: dict[str, Any] | None = None,
):
    """
    Decorator to mark a class as a plugin.

    Args:
        name: Plugin name
        version: Plugin version
        description: Plugin description
        author: Plugin author
        dependencies: List of required plugins
        provides: List of services this plugin provides
        config_schema: JSON schema for plugin configuration

    Usage:
        @plugin(name="my-plugin", version="1.0.0", description="My awesome plugin")
        class MyPlugin(IPlugin):
            pass
    """

    def decorator(cls):
        # Create metadata
        metadata = PluginMetadata(
            name=name,
            version=version,
            description=description,
            author=author,
            dependencies=dependencies or [],
            provides=provides or [],
            config_schema=config_schema,
        )

        # Add metadata property to class
        cls._plugin_metadata = metadata

        # Ensure the class has a plugin_metadata property
        if not hasattr(cls, "plugin_metadata"):

            @property
            def plugin_metadata(self):
                return self._plugin_metadata

            cls.plugin_metadata = plugin_metadata

        return cls

    return decorator


def service_hook(event_type: str):
    """
    Decorator to register a method as a service hook.

    Args:
        event_type: Type of service event to handle

    Usage:
        @service_hook("service.register")
        async def on_service_register(self, service_info):
            pass
    """

    def decorator(func):
        func._service_hook_event = event_type
        return func

    return decorator


def middleware(priority: int = 0):
    """
    Decorator to mark a method as middleware.

    Args:
        priority: Middleware priority (lower = higher priority)

    Usage:
        @middleware(priority=10)
        async def process_request(self, request, call_next):
            return await call_next(request)
    """

    def decorator(func):
        func._middleware_priority = priority
        return func

    return decorator


def event_handler(event_types: list[str]):
    """
    Decorator to register a method as an event handler.

    Args:
        event_types: List of event types to handle

    Usage:
        @event_handler(["user.created", "user.updated"])
        async def handle_user_events(self, event_type, event_data):
            pass
    """

    def decorator(func):
        func._event_handler_types = event_types
        return func

    return decorator


def health_check(interval: int = 60):
    """
    Decorator to mark a method as a health check.

    Args:
        interval: Health check interval in seconds

    Usage:
        @health_check(interval=30)
        async def check_database_health(self):
            return {"status": "healthy"}
    """

    def decorator(func):
        func._health_check_interval = interval
        return func

    return decorator


def metrics_collector(metric_name: str, metric_type: str = "gauge"):
    """
    Decorator to mark a method as a metrics collector.

    Args:
        metric_name: Name of the metric
        metric_type: Type of metric (gauge, counter, histogram)

    Usage:
        @metrics_collector("active_connections", "gauge")
        async def get_active_connections(self):
            return 42
    """

    def decorator(func):
        func._metric_name = metric_name
        func._metric_type = metric_type
        return func

    return decorator


def extension_point(name: str):
    """
    Decorator to mark a method as providing an extension point.

    Args:
        name: Name of the extension point

    Usage:
        @extension_point("pre_request")
        async def pre_request_hook(self, request):
            # Allow other plugins to extend this
            pass
    """

    def decorator(func):
        func._extension_point_name = name
        return func

    return decorator


def async_safe(func):
    """
    Decorator to make a function async-safe by wrapping sync functions.

    Usage:
        @async_safe
        def sync_operation(self):
            return "result"
    """
    if not inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return async_wrapper
    return func
