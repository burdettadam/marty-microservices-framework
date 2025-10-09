"""
Plugin Manager for the Marty Chassis Framework.

This module provides the central PluginManager class that handles
plugin discovery, loading, lifecycle management, and orchestration.
"""

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..logger import get_logger
from .exceptions import (
    PluginDependencyError,
    PluginError,
    PluginLoadError,
    PluginStateError,
)
from .interfaces import (
    IEventHandlerPlugin,
    IHealthPlugin,
    IMetricsPlugin,
    IMiddlewarePlugin,
    IPlugin,
    IServicePlugin,
    PluginContext,
    PluginState,
)


class PluginManager:
    """
    Central plugin management system.

    Handles plugin discovery, loading, dependency resolution,
    lifecycle management, and provides isolation between plugins.
    """

    def __init__(self, core_services, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the plugin manager.

        Args:
            core_services: Core framework services
            config: Plugin manager configuration
        """
        self.core_services = core_services
        self.config = config or {}
        self.logger = get_logger(self.__class__.__name__)

        # Plugin storage
        self.plugins: Dict[str, IPlugin] = {}
        self.plugin_modules: Dict[str, Any] = {}
        self.plugin_dependencies: Dict[str, Set[str]] = {}

        # Event handlers
        self._event_handlers: Dict[str, List[IEventHandlerPlugin]] = {}
        self._middleware_plugins: List[IMiddlewarePlugin] = []
        self._service_plugins: List[IServicePlugin] = []
        self._health_plugins: List[IHealthPlugin] = []
        self._metrics_plugins: List[IMetricsPlugin] = []

        # Plugin isolation
        self._plugin_contexts: Dict[str, PluginContext] = {}

        self.logger.info("Plugin manager initialized")

    async def discover_plugins(self, discovery_paths: List[str]) -> List[str]:
        """
        Discover plugins from specified paths.

        Args:
            discovery_paths: List of paths to search for plugins

        Returns:
            List of discovered plugin module names
        """
        discovered = []

        for path in discovery_paths:
            try:
                path_obj = Path(path)
                if path_obj.is_dir():
                    # Directory-based discovery
                    for plugin_file in path_obj.glob("*.py"):
                        if plugin_file.name != "__init__.py":
                            module_name = plugin_file.stem
                            discovered.append(f"{path_obj.name}.{module_name}")
                            self.logger.debug(f"Discovered plugin: {module_name}")
                elif path_obj.is_file() and path_obj.suffix == ".py":
                    # Single file discovery
                    module_name = path_obj.stem
                    discovered.append(module_name)
                    self.logger.debug(f"Discovered plugin file: {module_name}")
            except Exception as e:
                self.logger.warning(f"Error discovering plugins in {path}: {e}")

        self.logger.info(f"Discovered {len(discovered)} plugins")
        return discovered

    async def load_plugin(
        self, module_name: str, plugin_path: Optional[str] = None
    ) -> IPlugin:
        """
        Load a single plugin from a module.

        Args:
            module_name: Name of the module to load
            plugin_path: Optional path to the plugin module

        Returns:
            Loaded plugin instance
        """
        try:
            # Import the module
            if plugin_path:
                spec = importlib.util.spec_from_file_location(module_name, plugin_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                else:
                    raise PluginLoadError(module_name, "Failed to create module spec")
            else:
                module = importlib.import_module(module_name)

            self.plugin_modules[module_name] = module

            # Find plugin classes in the module
            plugin_classes = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, IPlugin)
                    and attr != IPlugin
                    and hasattr(attr, "_plugin_metadata")
                ):
                    plugin_classes.append(attr)

            if not plugin_classes:
                raise PluginLoadError(module_name, "No plugin classes found in module")

            if len(plugin_classes) > 1:
                self.logger.warning(
                    f"Multiple plugin classes found in {module_name}, using first one"
                )

            # Instantiate the plugin
            plugin_class = plugin_classes[0]
            plugin = plugin_class()
            await plugin.load()

            # Store plugin and its dependencies
            plugin_name = plugin.plugin_metadata.name
            self.plugins[plugin_name] = plugin
            self.plugin_dependencies[plugin_name] = set(
                plugin.plugin_metadata.dependencies
            )

            self.logger.info(
                f"Loaded plugin: {plugin_name} v{plugin.plugin_metadata.version}"
            )
            return plugin

        except Exception as e:
            error_msg = f"Failed to load plugin from {module_name}: {str(e)}"
            self.logger.error(error_msg)
            raise PluginLoadError(module_name, error_msg, e)

    async def resolve_dependencies(self) -> List[str]:
        """
        Resolve plugin dependencies and return load order.

        Returns:
            List of plugin names in dependency order

        Raises:
            PluginDependencyError: If dependencies cannot be resolved
        """
        # Topological sort for dependency resolution
        visited = set()
        temp_visited = set()
        result = []

        def visit(plugin_name: str):
            if plugin_name in temp_visited:
                raise PluginDependencyError(
                    plugin_name, ["Circular dependency detected"]
                )
            if plugin_name in visited:
                return

            temp_visited.add(plugin_name)

            # Check if plugin exists
            if plugin_name not in self.plugins:
                available_plugins = list(self.plugins.keys())
                raise PluginDependencyError(
                    plugin_name,
                    [f"Plugin not found. Available: {', '.join(available_plugins)}"],
                )

            # Visit dependencies first
            for dep in self.plugin_dependencies.get(plugin_name, set()):
                visit(dep)

            temp_visited.remove(plugin_name)
            visited.add(plugin_name)
            result.append(plugin_name)

        # Visit all plugins
        for plugin_name in self.plugins.keys():
            if plugin_name not in visited:
                visit(plugin_name)

        self.logger.info(f"Dependency resolution order: {result}")
        return result

    async def initialize_plugin(self, plugin_name: str) -> None:
        """
        Initialize a single plugin with its context.

        Args:
            plugin_name: Name of the plugin to initialize
        """
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            raise PluginError(f"Plugin not found: {plugin_name}")

        if plugin.state != PluginState.LOADED:
            raise PluginStateError(
                plugin_name, plugin.state.value, PluginState.LOADED.value
            )

        # Create plugin context
        plugin_config = self.config.get("plugins", {}).get(plugin_name, {})
        context = PluginContext(
            config=self.config,
            logger=get_logger(f"Plugin.{plugin_name}"),
            metrics_collector=getattr(self.core_services, "metrics_collector", None),
            event_bus=getattr(self.core_services, "event_bus", None),
            service_registry=getattr(self.core_services, "service_registry", None),
            extension_points=getattr(self.core_services, "extension_points", None),
            core_services=self.core_services,
            plugin_config=plugin_config,
        )

        self._plugin_contexts[plugin_name] = context

        try:
            await plugin.initialize(context)
            self.logger.info(f"Initialized plugin: {plugin_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize plugin {plugin_name}: {e}")
            plugin.state = PluginState.ERROR
            raise PluginError(f"Initialization failed: {str(e)}", plugin_name, e)

    async def start_plugin(self, plugin_name: str) -> None:
        """
        Start a single plugin.

        Args:
            plugin_name: Name of the plugin to start
        """
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            raise PluginError(f"Plugin not found: {plugin_name}")

        if plugin.state != PluginState.INITIALIZED:
            raise PluginStateError(
                plugin_name, plugin.state.value, PluginState.INITIALIZED.value
            )

        try:
            await plugin.start()

            # Register plugin with appropriate registries
            await self._register_plugin_capabilities(plugin)

            self.logger.info(f"Started plugin: {plugin_name}")
        except Exception as e:
            self.logger.error(f"Failed to start plugin {plugin_name}: {e}")
            plugin.state = PluginState.ERROR
            raise PluginError(f"Start failed: {str(e)}", plugin_name, e)

    async def stop_plugin(self, plugin_name: str) -> None:
        """
        Stop a single plugin.

        Args:
            plugin_name: Name of the plugin to stop
        """
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            raise PluginError(f"Plugin not found: {plugin_name}")

        try:
            await plugin.stop()

            # Unregister plugin capabilities
            await self._unregister_plugin_capabilities(plugin)

            self.logger.info(f"Stopped plugin: {plugin_name}")
        except Exception as e:
            self.logger.error(f"Failed to stop plugin {plugin_name}: {e}")
            raise PluginError(f"Stop failed: {str(e)}", plugin_name, e)

    async def unload_plugin(self, plugin_name: str) -> None:
        """
        Unload a single plugin.

        Args:
            plugin_name: Name of the plugin to unload
        """
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            raise PluginError(f"Plugin not found: {plugin_name}")

        try:
            await plugin.unload()

            # Clean up
            del self.plugins[plugin_name]
            if plugin_name in self._plugin_contexts:
                del self._plugin_contexts[plugin_name]
            if plugin_name in self.plugin_dependencies:
                del self.plugin_dependencies[plugin_name]

            self.logger.info(f"Unloaded plugin: {plugin_name}")
        except Exception as e:
            self.logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            raise PluginError(f"Unload failed: {str(e)}", plugin_name, e)

    async def load_all_plugins(self, discovery_paths: List[str]) -> None:
        """
        Discover, load, and start all plugins.

        Args:
            discovery_paths: Paths to search for plugins
        """
        try:
            # Discover plugins
            plugin_modules = await self.discover_plugins(discovery_paths)

            # Load plugins
            for module_name in plugin_modules:
                try:
                    await self.load_plugin(module_name)
                except PluginLoadError as e:
                    self.logger.error(f"Failed to load plugin {module_name}: {e}")
                    continue

            # Resolve dependencies and get load order
            load_order = await self.resolve_dependencies()

            # Initialize plugins in dependency order
            for plugin_name in load_order:
                await self.initialize_plugin(plugin_name)

            # Start plugins in dependency order
            for plugin_name in load_order:
                await self.start_plugin(plugin_name)

            self.logger.info(
                f"Successfully loaded and started {len(load_order)} plugins"
            )

        except Exception as e:
            self.logger.error(f"Failed to load all plugins: {e}")
            raise

    async def stop_all_plugins(self) -> None:
        """Stop all plugins in reverse dependency order."""
        # Get plugins in reverse dependency order
        try:
            load_order = await self.resolve_dependencies()
            stop_order = list(reversed(load_order))

            for plugin_name in stop_order:
                if plugin_name in self.plugins:
                    try:
                        await self.stop_plugin(plugin_name)
                    except Exception as e:
                        self.logger.error(f"Error stopping plugin {plugin_name}: {e}")

            self.logger.info("All plugins stopped")
        except Exception as e:
            self.logger.error(f"Error stopping plugins: {e}")

    async def _register_plugin_capabilities(self, plugin: IPlugin) -> None:
        """Register plugin with appropriate capability registries."""
        plugin_name = plugin.plugin_metadata.name

        # Register event handlers
        if isinstance(plugin, IEventHandlerPlugin):
            subscriptions = plugin.get_event_subscriptions()
            for event_type in subscriptions.keys():
                if event_type not in self._event_handlers:
                    self._event_handlers[event_type] = []
                self._event_handlers[event_type].append(plugin)
            self.logger.debug(f"Registered event handlers for {plugin_name}")

        # Register middleware
        if isinstance(plugin, IMiddlewarePlugin):
            self._middleware_plugins.append(plugin)
            # Sort by priority
            self._middleware_plugins.sort(key=lambda p: p.get_middleware_priority())
            self.logger.debug(f"Registered middleware for {plugin_name}")

        # Register service hooks
        if isinstance(plugin, IServicePlugin):
            self._service_plugins.append(plugin)
            self.logger.debug(f"Registered service hooks for {plugin_name}")

        # Register health checks
        if isinstance(plugin, IHealthPlugin):
            self._health_plugins.append(plugin)
            self.logger.debug(f"Registered health checks for {plugin_name}")

        # Register metrics
        if isinstance(plugin, IMetricsPlugin):
            self._metrics_plugins.append(plugin)
            self.logger.debug(f"Registered metrics for {plugin_name}")

    async def _unregister_plugin_capabilities(self, plugin: IPlugin) -> None:
        """Unregister plugin from capability registries."""
        plugin_name = plugin.plugin_metadata.name

        # Unregister event handlers
        if isinstance(plugin, IEventHandlerPlugin):
            for event_type, handlers in self._event_handlers.items():
                if plugin in handlers:
                    handlers.remove(plugin)
            self.logger.debug(f"Unregistered event handlers for {plugin_name}")

        # Unregister middleware
        if isinstance(plugin, IMiddlewarePlugin) and plugin in self._middleware_plugins:
            self._middleware_plugins.remove(plugin)
            self.logger.debug(f"Unregistered middleware for {plugin_name}")

        # Unregister service hooks
        if isinstance(plugin, IServicePlugin) and plugin in self._service_plugins:
            self._service_plugins.remove(plugin)
            self.logger.debug(f"Unregistered service hooks for {plugin_name}")

        # Unregister health checks
        if isinstance(plugin, IHealthPlugin) and plugin in self._health_plugins:
            self._health_plugins.remove(plugin)
            self.logger.debug(f"Unregistered health checks for {plugin_name}")

        # Unregister metrics
        if isinstance(plugin, IMetricsPlugin) and plugin in self._metrics_plugins:
            self._metrics_plugins.remove(plugin)
            self.logger.debug(f"Unregistered metrics for {plugin_name}")

    def get_plugin(self, plugin_name: str) -> Optional[IPlugin]:
        """Get a plugin by name."""
        return self.plugins.get(plugin_name)

    def get_plugins_by_type(self, plugin_type: type) -> List[IPlugin]:
        """Get all plugins of a specific type."""
        return [
            plugin
            for plugin in self.plugins.values()
            if isinstance(plugin, plugin_type)
        ]

    def get_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all plugins."""
        status = {}
        for name, plugin in self.plugins.items():
            status[name] = {
                "state": plugin.state.value,
                "version": plugin.plugin_metadata.version,
                "description": plugin.plugin_metadata.description,
                "dependencies": list(plugin.plugin_metadata.dependencies),
            }
        return status

    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Handle an event by dispatching to registered handlers.

        Args:
            event_type: Type of the event
            event_data: Event payload
        """
        handlers = self._event_handlers.get(event_type, [])
        if handlers:
            tasks = [
                handler.handle_event(event_type, event_data) for handler in handlers
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_middleware_chain(self) -> List[IMiddlewarePlugin]:
        """Get the ordered middleware chain."""
        return self._middleware_plugins.copy()

    def get_service_plugins(self) -> List[IServicePlugin]:
        """Get all service plugins."""
        return self._service_plugins.copy()

    async def collect_health_status(self) -> Dict[str, Any]:
        """Collect health status from all health plugins."""
        health_status = {"plugins": {}}

        for plugin in self._health_plugins:
            try:
                plugin_health = await plugin.check_health()
                health_status["plugins"][plugin.plugin_metadata.name] = plugin_health
            except Exception as e:
                health_status["plugins"][plugin.plugin_metadata.name] = {
                    "healthy": False,
                    "error": str(e),
                }

        return health_status

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all metrics plugins."""
        metrics = {}

        for plugin in self._metrics_plugins:
            try:
                plugin_metrics = await plugin.collect_metrics()
                plugin_name = plugin.plugin_metadata.name
                metrics[f"plugin.{plugin_name}"] = plugin_metrics
            except Exception as e:
                self.logger.error(
                    f"Error collecting metrics from {plugin.plugin_metadata.name}: {e}"
                )

        return metrics
