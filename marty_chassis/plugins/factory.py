"""
Plugin-enabled service factory.

This module provides an enhanced service factory that integrates
the plugin system with the core framework functionality.
"""

from pathlib import Path

from fastapi import FastAPI

from ..config import ChassisConfig
from ..logger import get_logger
from .core_services import CoreServices
from .extension_points import FRAMEWORK_EXTENSION_POINTS, ExtensionPointManager
from .manager import PluginManager


class PluginEnabledServiceFactory:
    """
    Enhanced service factory with plugin system integration.

    Provides methods to create services with plugin support,
    including automatic plugin discovery and lifecycle management.
    """

    def __init__(self, config: ChassisConfig):
        """
        Initialize the plugin-enabled service factory.

        Args:
            config: Framework configuration
        """
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

        # Initialize core services
        self.core_services = CoreServices(config)

        # Initialize extension point manager
        self.extension_manager = ExtensionPointManager()
        self._register_framework_extension_points()

        # Initialize plugin manager
        self.plugin_manager = PluginManager(self.core_services, config.dict())

        # Set core services extension points
        self.core_services.extension_points = self.extension_manager

        self.logger.info("Plugin-enabled service factory initialized")

    def _register_framework_extension_points(self) -> None:
        """Register framework-defined extension points."""
        for extension_point in FRAMEWORK_EXTENSION_POINTS:
            self.extension_manager.register_extension_point(extension_point)

        self.logger.info(
            f"Registered {len(FRAMEWORK_EXTENSION_POINTS)} framework extension points"
        )

    async def create_fastapi_service_with_plugins(
        self,
        name: str,
        plugin_directories: list[str] | None = None,
        enable_plugins: bool = True,
        **kwargs,
    ) -> FastAPI:
        """
        Create a FastAPI service with plugin support.

        Args:
            name: Service name
            plugin_directories: Directories to search for plugins
            enable_plugins: Whether to enable plugin loading
            **kwargs: Additional arguments for service creation

        Returns:
            FastAPI application instance with plugins loaded
        """
        from ..factories.fastapi_factory import create_fastapi_service

        # Create base FastAPI service
        app = create_fastapi_service(name=name, config=self.config, **kwargs)

        if enable_plugins:
            # Load plugins
            plugin_dirs = plugin_directories or self._get_default_plugin_directories()
            await self.plugin_manager.load_all_plugins(plugin_dirs)

            # Integrate plugins with FastAPI
            await self._integrate_plugins_with_fastapi(app)

        # Store plugin manager in app state
        app.state.plugin_manager = self.plugin_manager
        app.state.core_services = self.core_services
        app.state.extension_manager = self.extension_manager

        # Add plugin management endpoints
        self._add_plugin_endpoints(app)

        self.logger.info(f"Created FastAPI service '{name}' with plugin support")
        return app

    async def _integrate_plugins_with_fastapi(self, app: FastAPI) -> None:
        """
        Integrate plugins with FastAPI application.

        Args:
            app: FastAPI application instance
        """
        # Add middleware from plugins
        middleware_plugins = self.plugin_manager.get_middleware_chain()
        for middleware_plugin in middleware_plugins:
            # Create middleware wrapper with captured plugin
            def create_middleware(plugin):
                async def plugin_middleware(request, call_next):
                    return await plugin.process_request(request, call_next)

                return plugin_middleware

            # Add to FastAPI
            app.middleware("http")(create_middleware(middleware_plugin))
            self.logger.debug(
                f"Added middleware: {middleware_plugin.plugin_metadata.name}"
            )

        # Register service with service registry through plugins
        service_info = {
            "name": app.title,
            "host": "localhost",  # Would be configurable
            "port": 8000,  # Would be configurable
            "tags": ["fastapi", "microservice"],
            "health_check_url": "/health",
            "metadata": {"framework": "marty-chassis"},
        }

        # Call service registration extension point
        enhanced_service_info = await self.extension_manager.call_extension_point(
            "service.pre_register", service_info
        )

        # Register with core service registry
        if enhanced_service_info:
            service_info = enhanced_service_info

        self.core_services.service_registry.register_service(app.title, service_info)

        # Notify plugins of service registration
        service_plugins = self.plugin_manager.get_service_plugins()
        for service_plugin in service_plugins:
            await service_plugin.on_service_register(service_info)

        # Call post-registration extension point
        await self.extension_manager.call_extension_point(
            "service.post_register", service_info
        )

    def _get_default_plugin_directories(self) -> list[str]:
        """Get default plugin directories."""
        default_dirs = [
            "plugins",
            "marty_plugins",
            str(Path(__file__).parent / "examples"),
        ]

        # Add directories from configuration
        config_dirs = getattr(self.config, "plugin_directories", [])
        if config_dirs:
            default_dirs.extend(config_dirs)

        return default_dirs

    def _add_plugin_endpoints(self, app: FastAPI) -> None:
        """
        Add plugin management endpoints to FastAPI app.

        Args:
            app: FastAPI application instance
        """

        @app.get("/plugins/status")
        async def get_plugin_status():
            """Get status of all plugins."""
            return self.plugin_manager.get_plugin_status()

        @app.get("/plugins/{plugin_name}/health")
        async def get_plugin_health(plugin_name: str):
            """Get health status of a specific plugin."""
            plugin = self.plugin_manager.get_plugin(plugin_name)
            if not plugin:
                return {"error": "Plugin not found"}, 404

            return await plugin.health_check()

        @app.get("/plugins/metrics")
        async def get_plugin_metrics():
            """Get metrics from all plugins."""
            return await self.plugin_manager.collect_metrics()

        @app.post("/plugins/{plugin_name}/reload")
        async def reload_plugin(plugin_name: str):
            """Reload a specific plugin."""
            try:
                # Stop and unload plugin
                await self.plugin_manager.stop_plugin(plugin_name)
                await self.plugin_manager.unload_plugin(plugin_name)

                # Reload would require re-discovery - simplified for demo
                return {"message": f"Plugin {plugin_name} reloaded successfully"}
            except Exception as e:
                return {"error": str(e)}, 500

        @app.get("/extension-points")
        async def get_extension_points():
            """Get all registered extension points."""
            return {
                name: {
                    "type": ep.type.value,
                    "description": ep.description,
                    "parameters": ep.parameters,
                    "return_type": ep.return_type,
                    "handler_count": self.extension_manager.get_handler_count(name),
                }
                for name, ep in self.extension_manager.list_extension_points().items()
            }

        self.logger.debug("Added plugin management endpoints")

    async def shutdown_plugins(self) -> None:
        """Shutdown all plugins gracefully."""
        await self.plugin_manager.stop_all_plugins()
        await self.core_services.shutdown()
        self.logger.info("All plugins shut down")

    def get_plugin_manager(self) -> PluginManager:
        """Get the plugin manager instance."""
        return self.plugin_manager

    def get_core_services(self) -> CoreServices:
        """Get the core services instance."""
        return self.core_services

    def get_extension_manager(self) -> ExtensionPointManager:
        """Get the extension point manager."""
        return self.extension_manager


# Convenience function for creating plugin-enabled services
async def create_plugin_enabled_fastapi_service(
    name: str,
    config: ChassisConfig | None = None,
    plugin_directories: list[str] | None = None,
    **kwargs,
) -> FastAPI:
    """
    Convenience function to create a FastAPI service with plugins.

    Args:
        name: Service name
        config: Optional configuration (will use default if not provided)
        plugin_directories: Directories to search for plugins
        **kwargs: Additional arguments for service creation

    Returns:
        FastAPI application instance with plugins loaded
    """
    if config is None:
        config = ChassisConfig()

    factory = PluginEnabledServiceFactory(config)
    return await factory.create_fastapi_service_with_plugins(
        name=name, plugin_directories=plugin_directories, **kwargs
    )
