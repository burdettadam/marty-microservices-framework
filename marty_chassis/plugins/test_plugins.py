"""
Tests for the plugin architecture.

This module contains basic tests to verify the plugin system functionality.
"""

import asyncio
from typing import Any, Dict

import pytest

from marty_chassis.config import ChassisConfig
from marty_chassis.plugins import (
    CoreServices,
    IEventHandlerPlugin,
    IMiddlewarePlugin,
    IPlugin,
    PluginManager,
    PluginMetadata,
    event_handler,
    middleware,
    plugin,
)


@plugin(
    name="test-plugin",
    version="1.0.0",
    description="Test plugin for unit tests",
    author="Test Suite",
)
class TestPlugin(IPlugin):
    """Simple test plugin."""

    def __init__(self):
        super().__init__()
        self.initialized = False
        self.started = False

    @property
    def plugin_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin for unit tests",
            author="Test Suite",
        )

    async def initialize(self, context):
        await super().initialize(context)
        self.initialized = True

    async def start(self):
        await super().start()
        self.started = True

    async def stop(self):
        await super().stop()
        self.started = False


@plugin(name="test-middleware", version="1.0.0", description="Test middleware plugin")
class TestMiddlewarePlugin(IMiddlewarePlugin):
    """Test middleware plugin."""

    def __init__(self):
        super().__init__()
        self.requests_processed = 0

    @property
    def plugin_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test-middleware",
            version="1.0.0",
            description="Test middleware plugin",
        )

    async def process_request(self, request, call_next):
        self.requests_processed += 1
        # Add test header
        if hasattr(request, "headers"):
            request.headers["X-Test-Middleware"] = "processed"

        response = await call_next(request)

        # Add response header
        if hasattr(response, "headers"):
            response.headers["X-Test-Processed"] = str(self.requests_processed)

        return response

    def get_middleware_priority(self):
        return 100


@plugin(
    name="test-event-handler", version="1.0.0", description="Test event handler plugin"
)
class TestEventHandlerPlugin(IEventHandlerPlugin):
    """Test event handler plugin."""

    def __init__(self):
        super().__init__()
        self.events_handled = {}

    @property
    def plugin_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="test-event-handler",
            version="1.0.0",
            description="Test event handler plugin",
        )

    def get_event_subscriptions(self):
        return {"test.event": "handle_test_event", "user.login": "handle_user_login"}

    async def handle_event(self, event_type, event_data):
        if event_type not in self.events_handled:
            self.events_handled[event_type] = 0
        self.events_handled[event_type] += 1

    async def handle_test_event(self, event_data):
        await self.handle_event("test.event", event_data)

    async def handle_user_login(self, event_data):
        await self.handle_event("user.login", event_data)


class TestPluginArchitecture:
    """Test suite for plugin architecture."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ChassisConfig()

    @pytest.fixture
    def core_services(self, config):
        """Create core services."""
        return CoreServices(config)

    @pytest.fixture
    def plugin_manager(self, core_services, config):
        """Create plugin manager."""
        return PluginManager(core_services, config.dict())

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self, plugin_manager):
        """Test basic plugin lifecycle."""
        # Create test plugin
        plugin = TestPlugin()

        # Test initial state
        assert not plugin.initialized
        assert not plugin.started

        # Mock loading by adding to manager
        plugin_name = plugin.plugin_metadata.name
        plugin_manager.plugins[plugin_name] = plugin
        plugin_manager.plugin_dependencies[plugin_name] = set()

        # Initialize plugin
        await plugin_manager.initialize_plugin(plugin_name)
        assert plugin.initialized

        # Start plugin
        await plugin_manager.start_plugin(plugin_name)
        assert plugin.started

        # Stop plugin
        await plugin_manager.stop_plugin(plugin_name)
        assert not plugin.started

        # Unload plugin
        await plugin_manager.unload_plugin(plugin_name)
        assert plugin_name not in plugin_manager.plugins

    @pytest.mark.asyncio
    async def test_middleware_plugin(self, plugin_manager):
        """Test middleware plugin functionality."""
        # Create and register middleware plugin
        middleware_plugin = TestMiddlewarePlugin()
        plugin_name = middleware_plugin.plugin_metadata.name

        plugin_manager.plugins[plugin_name] = middleware_plugin
        plugin_manager.plugin_dependencies[plugin_name] = set()

        # Initialize and start
        await plugin_manager.initialize_plugin(plugin_name)
        await plugin_manager.start_plugin(plugin_name)

        # Check middleware registration
        middleware_chain = plugin_manager.get_middleware_chain()
        assert len(middleware_chain) == 1
        assert middleware_chain[0] == middleware_plugin

        # Test middleware processing (mock)
        class MockRequest:
            def __init__(self):
                self.headers = {}

        class MockResponse:
            def __init__(self):
                self.headers = {}

        async def mock_call_next(request):
            return MockResponse()

        request = MockRequest()
        response = await middleware_plugin.process_request(request, mock_call_next)

        assert middleware_plugin.requests_processed == 1
        assert request.headers.get("X-Test-Middleware") == "processed"
        assert response.headers.get("X-Test-Processed") == "1"

    @pytest.mark.asyncio
    async def test_event_handler_plugin(self, plugin_manager):
        """Test event handler plugin functionality."""
        # Create and register event handler plugin
        event_plugin = TestEventHandlerPlugin()
        plugin_name = event_plugin.plugin_metadata.name

        plugin_manager.plugins[plugin_name] = event_plugin
        plugin_manager.plugin_dependencies[plugin_name] = set()

        # Initialize and start
        await plugin_manager.initialize_plugin(plugin_name)
        await plugin_manager.start_plugin(plugin_name)

        # Test event handling
        await plugin_manager.handle_event("test.event", {"data": "test"})
        await plugin_manager.handle_event("user.login", {"user_id": "123"})

        # Check events were handled
        assert event_plugin.events_handled.get("test.event", 0) == 1
        assert event_plugin.events_handled.get("user.login", 0) == 1

    @pytest.mark.asyncio
    async def test_plugin_manager_status(self, plugin_manager):
        """Test plugin manager status reporting."""
        # Add test plugin
        plugin = TestPlugin()
        plugin_name = plugin.plugin_metadata.name

        plugin_manager.plugins[plugin_name] = plugin
        plugin_manager.plugin_dependencies[plugin_name] = set()

        # Get status
        status = plugin_manager.get_plugin_status()

        assert plugin_name in status
        assert status[plugin_name]["version"] == "1.0.0"
        assert status[plugin_name]["state"] == "unloaded"  # Not started yet

    @pytest.mark.asyncio
    async def test_health_check_collection(self, plugin_manager):
        """Test health check collection from plugins."""
        # Add test plugin
        plugin = TestPlugin()
        plugin_name = plugin.plugin_metadata.name

        plugin_manager.plugins[plugin_name] = plugin
        plugin_manager.plugin_dependencies[plugin_name] = set()

        await plugin_manager.initialize_plugin(plugin_name)
        await plugin_manager.start_plugin(plugin_name)

        # Collect health status
        health_status = await plugin_manager.collect_health_status()

        # Should have plugin health information
        assert "plugins" in health_status

    @pytest.mark.asyncio
    async def test_core_services_event_bus(self, core_services):
        """Test core services event bus functionality."""
        events_received = []

        async def test_handler(message):
            events_received.append(message.event_type)

        # Subscribe to events
        core_services.event_bus.subscribe("test.event", test_handler)

        # Publish event
        await core_services.event_bus.publish("test.event", {"data": "test"})

        # Give some time for async processing
        await asyncio.sleep(0.01)

        # Check event was received
        assert "test.event" in events_received

    @pytest.mark.asyncio
    async def test_service_registry(self, core_services):
        """Test service registry functionality."""
        # Register service
        service_info = {"host": "localhost", "port": 8080, "tags": ["test", "api"]}

        core_services.service_registry.register_service("test-service", service_info)

        # Discover service
        discovered = core_services.service_registry.discover_service("test-service")
        assert discovered is not None
        assert discovered["host"] == "localhost"
        assert discovered["port"] == 8080

        # Discover by tag
        services_by_tag = core_services.service_registry.discover_services("test")
        assert len(services_by_tag) == 1
        assert "test" in services_by_tag[0]["tags"]

    def test_plugin_decorator(self):
        """Test plugin decorator functionality."""
        # The decorator should have set metadata
        plugin = TestPlugin()
        metadata = plugin.plugin_metadata

        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin for unit tests"
        assert metadata.author == "Test Suite"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
