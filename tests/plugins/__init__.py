"""
Plugin System Tests

Comprehensive test suite for the MMF plugin system including:
- Unit tests for core plugin components
- Integration tests for plugin loading and discovery
- Service registration and lifecycle tests
- Configuration management tests
- Generic plugin tests and utilities
"""

import shutil

# Import plugin system components
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from framework.plugins import MMFPlugin, PluginContext, PluginMetadata


# Test fixtures
@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture
def mock_context():
    """Create mock plugin context with MMF services."""
    context = Mock(spec=PluginContext)
    context.database = AsyncMock()
    context.security = AsyncMock()
    context.observability = AsyncMock()
    context.cache = AsyncMock()
    context.message_bus = AsyncMock()
    context.config_manager = AsyncMock()

    # Mock database operations
    context.database.execute_ddl = AsyncMock()
    context.database.insert = AsyncMock()
    context.database.query_one = AsyncMock(return_value=None)

    # Mock security operations
    context.security.get_key_info = AsyncMock(return_value={"id": "test_key"})
    context.security.sign_data = AsyncMock(return_value=b"mock_signature")
    context.security.verify_signature = AsyncMock(return_value=True)

    # Mock observability
    context.observability.get_metrics_collector = Mock(return_value=MockMetricsCollector())
    context.observability.get_tracer = Mock(return_value=MockTracer())

    # Mock cache operations
    context.cache.get = AsyncMock(return_value=None)
    context.cache.set = AsyncMock()
    context.cache.delete_pattern = AsyncMock()

    # Mock message bus
    context.message_bus.publish = AsyncMock()

    return context

# Mock classes for testing
class MockMetricsCollector:
    def increment_counter(self, name: str, labels=None):
        pass

    def start_timer(self, name: str, labels=None):
        return MockTimer()

class MockTimer:
    def stop(self):
        pass

class MockTracer:
    def start_span(self, name: str):
        return MockSpan()

class MockSpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def set_attribute(self, key: str, value):
        pass

# Simple test plugin for testing
class TestPlugin(MMFPlugin):
    def __init__(self):
        super().__init__()
        self.initialized = False
        self.started = False

    @property
    def metadata(self) -> PluginMetadata:
        """Test plugin metadata."""
        return PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin for unit testing",
            author="Test Framework"
        )

    async def initialize(self, context: PluginContext) -> None:
        self._context = context
        self.initialized = True

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def get_health_status(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self.started else "stopped",
            "initialized": self.initialized
        }
