"""
Extension points system for the plugin architecture.

This module provides a structured way to define and manage
extension points throughout the framework.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from ..logger import get_logger


class ExtensionPointType(str, Enum):
    """Types of extension points."""

    FILTER = "filter"  # Modify data as it passes through
    ACTION = "action"  # Perform side effects
    HOOK = "hook"  # Notification of events
    PROVIDER = "provider"  # Provide data or services


@dataclass
class ExtensionPoint:
    """Definition of an extension point."""

    name: str
    type: ExtensionPointType
    description: str
    parameters: Dict[str, str]
    return_type: Optional[str] = None
    required: bool = False

    def __post_init__(self):
        """Validate extension point definition."""
        if not self.name:
            raise ValueError("Extension point name is required")
        if not self.description:
            raise ValueError("Extension point description is required")


class ExtensionPointManager:
    """
    Manages extension points and their handlers.

    Provides a centralized registry for extension points
    and orchestrates calls to registered handlers.
    """

    def __init__(self):
        self.extension_points: Dict[str, ExtensionPoint] = {}
        self.handlers: Dict[str, List[Callable]] = {}
        self.logger = get_logger(self.__class__.__name__)

    def register_extension_point(self, extension_point: ExtensionPoint) -> None:
        """
        Register a new extension point.

        Args:
            extension_point: Extension point definition
        """
        self.extension_points[extension_point.name] = extension_point
        self.handlers[extension_point.name] = []
        self.logger.info(f"Registered extension point: {extension_point.name}")

    def register_handler(
        self, extension_point_name: str, handler: Callable, priority: int = 0
    ) -> None:
        """
        Register a handler for an extension point.

        Args:
            extension_point_name: Name of the extension point
            handler: Handler function
            priority: Handler priority (lower = higher priority)
        """
        if extension_point_name not in self.extension_points:
            raise ValueError(f"Extension point not found: {extension_point_name}")

        # Store handler with priority
        handler_info = {"handler": handler, "priority": priority}
        self.handlers[extension_point_name].append(handler_info)

        # Sort by priority
        self.handlers[extension_point_name].sort(key=lambda x: x["priority"])

        self.logger.debug(
            f"Registered handler for extension point: {extension_point_name}"
        )

    def unregister_handler(self, extension_point_name: str, handler: Callable) -> None:
        """
        Unregister a handler from an extension point.

        Args:
            extension_point_name: Name of the extension point
            handler: Handler function to remove
        """
        if extension_point_name in self.handlers:
            self.handlers[extension_point_name] = [
                h
                for h in self.handlers[extension_point_name]
                if h["handler"] != handler
            ]
            self.logger.debug(
                f"Unregistered handler from extension point: {extension_point_name}"
            )

    async def call_extension_point(
        self, name: str, data: Any = None, **kwargs
    ) -> Union[Any, List[Any]]:
        """
        Call all handlers for an extension point.

        Args:
            name: Extension point name
            data: Data to pass to handlers
            **kwargs: Additional keyword arguments

        Returns:
            Result depends on extension point type:
            - FILTER: Modified data
            - ACTION: List of results
            - HOOK: None
            - PROVIDER: List of provided values
        """
        if name not in self.extension_points:
            self.logger.warning(f"Extension point not found: {name}")
            return data if data is not None else []

        extension_point = self.extension_points[name]
        handlers_info = self.handlers.get(name, [])

        if not handlers_info:
            self.logger.debug(f"No handlers registered for extension point: {name}")
            return data if data is not None else []

        handlers = [h["handler"] for h in handlers_info]

        if extension_point.type == ExtensionPointType.FILTER:
            return await self._call_filter_handlers(name, handlers, data, **kwargs)
        elif extension_point.type == ExtensionPointType.ACTION:
            return await self._call_action_handlers(name, handlers, data, **kwargs)
        elif extension_point.type == ExtensionPointType.HOOK:
            await self._call_hook_handlers(name, handlers, data, **kwargs)
            return None
        elif extension_point.type == ExtensionPointType.PROVIDER:
            return await self._call_provider_handlers(name, handlers, data, **kwargs)
        else:
            self.logger.error(f"Unknown extension point type: {extension_point.type}")
            return data if data is not None else []

    async def _call_filter_handlers(
        self, name: str, handlers: List[Callable], data: Any, **kwargs
    ) -> Any:
        """
        Call filter handlers sequentially, passing data through the chain.

        Args:
            name: Extension point name
            handlers: List of handler functions
            data: Initial data
            **kwargs: Additional arguments

        Returns:
            Filtered data after passing through all handlers
        """
        result = data

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(result, **kwargs)
                else:
                    result = handler(result, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in filter handler for {name}: {e}")
                # Continue with original data on error
                continue

        return result

    async def _call_action_handlers(
        self, name: str, handlers: List[Callable], data: Any, **kwargs
    ) -> List[Any]:
        """
        Call action handlers in parallel and collect results.

        Args:
            name: Extension point name
            handlers: List of handler functions
            data: Data to pass to handlers
            **kwargs: Additional arguments

        Returns:
            List of results from all handlers
        """
        tasks = []

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(data, **kwargs))
                else:
                    # Run sync handlers in thread pool
                    future = asyncio.get_event_loop().run_in_executor(
                        None, lambda h=handler: h(data, **kwargs)
                    )
                    tasks.append(future)
            except Exception as e:
                self.logger.error(
                    f"Error creating task for action handler in {name}: {e}"
                )

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Filter out exceptions and log them
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error in action handler for {name}: {result}")
                else:
                    valid_results.append(result)
            return valid_results

        return []

    async def _call_hook_handlers(
        self, name: str, handlers: List[Callable], data: Any, **kwargs
    ) -> None:
        """
        Call hook handlers to notify of events.

        Args:
            name: Extension point name
            handlers: List of handler functions
            data: Event data
            **kwargs: Additional arguments
        """
        tasks = []

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(data, **kwargs))
                else:
                    # Run sync handlers in thread pool
                    future = asyncio.get_event_loop().run_in_executor(
                        None, lambda h=handler: h(data, **kwargs)
                    )
                    tasks.append(future)
            except Exception as e:
                self.logger.error(
                    f"Error creating task for hook handler in {name}: {e}"
                )

        if tasks:
            # Execute all hooks but don't wait for results
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _call_provider_handlers(
        self, name: str, handlers: List[Callable], data: Any, **kwargs
    ) -> List[Any]:
        """
        Call provider handlers to collect provided values.

        Args:
            name: Extension point name
            handlers: List of handler functions
            data: Request data
            **kwargs: Additional arguments

        Returns:
            List of provided values
        """
        tasks = []

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(data, **kwargs))
                else:
                    # Run sync handlers in thread pool
                    future = asyncio.get_event_loop().run_in_executor(
                        None, lambda h=handler: h(data, **kwargs)
                    )
                    tasks.append(future)
            except Exception as e:
                self.logger.error(
                    f"Error creating task for provider handler in {name}: {e}"
                )

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Filter out exceptions and None values
            valid_results = []
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"Error in provider handler for {name}: {result}")
                elif result is not None:
                    valid_results.append(result)
            return valid_results

        return []

    def get_extension_point(self, name: str) -> Optional[ExtensionPoint]:
        """Get extension point definition by name."""
        return self.extension_points.get(name)

    def list_extension_points(self) -> Dict[str, ExtensionPoint]:
        """List all registered extension points."""
        return self.extension_points.copy()

    def get_handler_count(self, name: str) -> int:
        """Get number of handlers registered for an extension point."""
        return len(self.handlers.get(name, []))

    def clear_handlers(self, name: str) -> None:
        """Clear all handlers for an extension point."""
        if name in self.handlers:
            self.handlers[name] = []
            self.logger.debug(f"Cleared all handlers for extension point: {name}")


# Predefined extension points for the framework
FRAMEWORK_EXTENSION_POINTS = [
    ExtensionPoint(
        name="service.pre_register",
        type=ExtensionPointType.FILTER,
        description="Modify service info before registration",
        parameters={"service_info": "Dict[str, Any]"},
        return_type="Dict[str, Any]",
    ),
    ExtensionPoint(
        name="service.post_register",
        type=ExtensionPointType.HOOK,
        description="Notification after service registration",
        parameters={"service_info": "Dict[str, Any]"},
    ),
    ExtensionPoint(
        name="middleware.pre_request",
        type=ExtensionPointType.FILTER,
        description="Process request before main handler",
        parameters={"request": "Any"},
        return_type="Any",
    ),
    ExtensionPoint(
        name="middleware.post_response",
        type=ExtensionPointType.FILTER,
        description="Process response after main handler",
        parameters={"response": "Any", "request": "Any"},
        return_type="Any",
    ),
    ExtensionPoint(
        name="config.load",
        type=ExtensionPointType.PROVIDER,
        description="Provide additional configuration sources",
        parameters={"config_name": "str"},
        return_type="Dict[str, Any]",
    ),
    ExtensionPoint(
        name="health.check",
        type=ExtensionPointType.PROVIDER,
        description="Provide health check results",
        parameters={},
        return_type="Dict[str, Any]",
    ),
    ExtensionPoint(
        name="metrics.collect",
        type=ExtensionPointType.PROVIDER,
        description="Provide custom metrics",
        parameters={},
        return_type="Dict[str, Any]",
    ),
    ExtensionPoint(
        name="plugin.loaded",
        type=ExtensionPointType.HOOK,
        description="Notification when plugin is loaded",
        parameters={"plugin_name": "str", "plugin_metadata": "PluginMetadata"},
    ),
    ExtensionPoint(
        name="plugin.started",
        type=ExtensionPointType.HOOK,
        description="Notification when plugin is started",
        parameters={"plugin_name": "str", "plugin_metadata": "PluginMetadata"},
    ),
    ExtensionPoint(
        name="plugin.stopped",
        type=ExtensionPointType.HOOK,
        description="Notification when plugin is stopped",
        parameters={"plugin_name": "str", "plugin_metadata": "PluginMetadata"},
    ),
]
