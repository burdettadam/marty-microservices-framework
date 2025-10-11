"""
Core Plugin System Tests

Tests for the fundamental plugin system components including:
- Plugin lifecycle management
- Context creation and injection
- Plugin metadata handling
- Manager operations
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest

from framework.plugins import MMFPlugin, PluginContext, PluginManager, PluginMetadata

from . import TestPlugin, mock_context


class TestPluginMetadata:
    """Test plugin metadata handling."""

    def test_create_metadata(self):
        """Test creation of plugin metadata."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin for unit testing",
            author="Test Author",
            dependencies=["dependency1", "dependency2"],
            optional_dependencies=["optional1"]
        )

        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin for unit testing"
        assert metadata.author == "Test Author"
        assert "dependency1" in metadata.dependencies
        assert "optional1" in metadata.optional_dependencies

    def test_metadata_defaults(self):
        """Test metadata with default values."""
        metadata = PluginMetadata(
            name="minimal-plugin",
            version="1.0.0"
        )

        assert metadata.name == "minimal-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == ""
        assert metadata.author == ""
        assert metadata.dependencies == []
        assert metadata.optional_dependencies == []

class TestPluginContext:
    """Test plugin context functionality."""

    def test_context_creation(self, mock_context):
        """Test that plugin context provides access to MMF services."""
        assert mock_context.database is not None
        assert mock_context.security is not None
        assert mock_context.observability is not None
        assert mock_context.cache is not None
        assert mock_context.message_bus is not None
        assert mock_context.config_manager is not None

    @pytest.mark.asyncio
    async def test_context_database_operations(self, mock_context):
        """Test database operations through context."""
        await mock_context.database.execute_ddl("CREATE TABLE test (id INT)")
        mock_context.database.execute_ddl.assert_called_once()

        await mock_context.database.insert("test", {"id": 1})
        mock_context.database.insert.assert_called_once()

        result = await mock_context.database.query_one("SELECT * FROM test WHERE id = ?", (1,))
        mock_context.database.query_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_security_operations(self, mock_context):
        """Test security operations through context."""
        key_info = await mock_context.security.get_key_info("test_key")
        assert key_info["id"] == "test_key"

        signature = await mock_context.security.sign_data(b"test_data", "test_key")
        assert signature == b"mock_signature"

        is_valid = await mock_context.security.verify_signature(
            b"test_data", b"mock_signature", "test_key"
        )
        assert is_valid is True

class TestPluginLifecycle:
    """Test plugin lifecycle management."""

    @pytest.mark.asyncio
    async def test_plugin_initialization(self, mock_context):
        """Test plugin initialization process."""
        plugin = TestPlugin()
        assert not plugin.initialized
        assert not plugin.started

        await plugin.initialize(mock_context)
        assert plugin.initialized
        assert plugin.context == mock_context

    @pytest.mark.asyncio
    async def test_plugin_start_stop(self, mock_context):
        """Test plugin start and stop lifecycle."""
        plugin = TestPlugin()
        await plugin.initialize(mock_context)

        await plugin.start()
        assert plugin.started

        health = await plugin.get_health_status()
        assert health["status"] == "healthy"
        assert health["initialized"] is True

        await plugin.stop()
        assert not plugin.started

        health = await plugin.get_health_status()
        assert health["status"] == "stopped"

class TestPluginManager:
    """Test plugin manager functionality."""

    @pytest.fixture
    def plugin_manager(self, mock_context):
        """Create plugin manager with mock context."""
        return PluginManager(mock_context)

    @pytest.mark.asyncio
    async def test_manager_register_plugin(self, plugin_manager, mock_context):
        """Test plugin registration with manager."""
        plugin = TestPlugin()
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin"
        )

        await plugin_manager.register_plugin("test-plugin", plugin, metadata)

        assert "test-plugin" in plugin_manager.plugins
        assert plugin_manager.plugins["test-plugin"] == plugin
        assert plugin_manager.plugin_metadata["test-plugin"] == metadata
        assert plugin.initialized

    @pytest.mark.asyncio
    async def test_manager_start_all_plugins(self, plugin_manager, mock_context):
        """Test starting all registered plugins."""
        plugin1 = TestPlugin()
        plugin2 = TestPlugin()

        await plugin_manager.register_plugin("plugin1", plugin1, PluginMetadata("plugin1", "1.0.0"))
        await plugin_manager.register_plugin("plugin2", plugin2, PluginMetadata("plugin2", "1.0.0"))

        await plugin_manager.start_all_plugins()

        assert plugin1.started
        assert plugin2.started

    @pytest.mark.asyncio
    async def test_manager_stop_all_plugins(self, plugin_manager, mock_context):
        """Test stopping all registered plugins."""
        plugin1 = TestPlugin()
        plugin2 = TestPlugin()

        await plugin_manager.register_plugin("plugin1", plugin1, PluginMetadata("plugin1", "1.0.0"))
        await plugin_manager.register_plugin("plugin2", plugin2, PluginMetadata("plugin2", "1.0.0"))

        await plugin_manager.start_all_plugins()
        assert plugin1.started and plugin2.started

        await plugin_manager.stop_all_plugins()
        assert not plugin1.started and not plugin2.started

    def test_manager_get_plugin_info(self, plugin_manager, mock_context):
        """Test retrieving plugin information."""
        # Test empty manager
        info = plugin_manager.get_plugin_info()
        assert len(info) == 0

        # Add plugin and test info
        plugin = TestPlugin()
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin"
        )

        asyncio.run(plugin_manager.register_plugin("test-plugin", plugin, metadata))

        info = plugin_manager.get_plugin_info()
        assert len(info) == 1
        assert info[0]["name"] == "test-plugin"
        assert info[0]["version"] == "1.0.0"
        assert info[0]["status"] == "registered"

    @pytest.mark.asyncio
    async def test_manager_health_check(self, plugin_manager, mock_context):
        """Test health check for all plugins."""
        plugin1 = TestPlugin()
        plugin2 = TestPlugin()

        await plugin_manager.register_plugin("plugin1", plugin1, PluginMetadata("plugin1", "1.0.0"))
        await plugin_manager.register_plugin("plugin2", plugin2, PluginMetadata("plugin2", "1.0.0"))

        await plugin_manager.start_all_plugins()

        health = await plugin_manager.get_health_status()

        assert "plugin1" in health
        assert "plugin2" in health
        assert health["plugin1"]["status"] == "healthy"
        assert health["plugin2"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_manager_duplicate_registration_error(self, plugin_manager):
        """Test error handling for duplicate plugin registration."""
        plugin1 = TestPlugin()
        plugin2 = TestPlugin()
        metadata = PluginMetadata("test-plugin", "1.0.0")

        await plugin_manager.register_plugin("test-plugin", plugin1, metadata)

        with pytest.raises(ValueError, match="Plugin 'test-plugin' is already registered"):
            await plugin_manager.register_plugin("test-plugin", plugin2, metadata)

class TestPluginErrorHandling:
    """Test error handling in plugin operations."""

    @pytest.mark.asyncio
    async def test_plugin_initialization_error(self, mock_context):
        """Test handling of plugin initialization errors."""
        class FailingPlugin(MMFPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name="failing-plugin", version="1.0.0")

            async def initialize(self, context: PluginContext) -> None:
                raise RuntimeError("Initialization failed")

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def get_health_status(self) -> dict[str, Any]:
                return {"status": "error"}

        plugin = FailingPlugin()

        with pytest.raises(RuntimeError, match="Initialization failed"):
            await plugin.initialize(mock_context)

    @pytest.mark.asyncio
    async def test_plugin_start_error(self, mock_context):
        """Test handling of plugin start errors."""
        class FailingStartPlugin(MMFPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name="failing-start-plugin", version="1.0.0")

            async def initialize(self, context: PluginContext) -> None:
                pass

            async def start(self) -> None:
                raise RuntimeError("Start failed")

            async def stop(self) -> None:
                pass

            async def get_health_status(self) -> dict[str, Any]:
                return {"status": "error"}

        plugin = FailingStartPlugin()
        await plugin.initialize(mock_context)

        with pytest.raises(RuntimeError, match="Start failed"):
            await plugin.start()
