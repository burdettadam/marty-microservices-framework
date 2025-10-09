"""
Unit tests for the Marty Chassis package.

This module contains comprehensive tests for all chassis components.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml

# Test imports
from marty_chassis.config import ChassisConfig, ConfigManager, Environment
from marty_chassis.health import HealthCheck, HealthStatus
from marty_chassis.logger import get_logger, setup_logging
from marty_chassis.metrics import MetricsCollector
from marty_chassis.resilience import CircuitBreaker, RetryPolicy
from marty_chassis.security import JWTAuth, RBACMiddleware
from marty_chassis.service_mesh import ManifestGenerator
from marty_chassis.templates import TemplateGenerator


class TestConfig:
    """Test configuration management."""

    def test_default_config(self):
        """Test default configuration creation."""
        config = ChassisConfig()
        assert config.environment == Environment.DEVELOPMENT
        assert config.service.name == "marty-service"
        assert config.service.port == 8000

    def test_config_from_env(self):
        """Test configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "CHASSIS_ENVIRONMENT": "production",
                "CHASSIS_SERVICE__NAME": "test-service",
                "CHASSIS_SERVICE__PORT": "9000",
            },
        ):
            config = ChassisConfig.from_env()
            assert config.environment == Environment.PRODUCTION
            assert config.service.name == "test-service"
            assert config.service.port == 9000

    def test_config_from_file(self):
        """Test configuration from YAML file."""
        config_data = {
            "environment": "testing",
            "service": {"name": "yaml-service", "port": 7000},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            manager = ConfigManager()
            config = manager.load_config(config_file)
            assert config.environment == Environment.TESTING
            assert config.service.name == "yaml-service"
            assert config.service.port == 7000
        finally:
            os.unlink(config_file)


class TestSecurity:
    """Test security components."""

    def test_jwt_auth_creation(self):
        """Test JWT authentication creation."""
        auth = JWTAuth()
        assert auth.secret is not None
        assert auth.algorithm == "HS256"

    def test_token_creation_and_validation(self):
        """Test JWT token creation and validation."""
        auth = JWTAuth()
        payload = {"sub": "test-user", "role": "admin"}

        token = auth.create_access_token(payload)
        assert token is not None

        decoded = auth.decode_token(token)
        assert decoded["sub"] == "test-user"
        assert decoded["role"] == "admin"

    def test_rbac_middleware(self):
        """Test RBAC middleware functionality."""
        middleware = RBACMiddleware()

        # Test role checking
        user_data = {"roles": ["admin", "user"]}
        assert middleware.has_role(user_data, "admin")
        assert middleware.has_role(user_data, "user")
        assert not middleware.has_role(user_data, "superuser")


class TestHealth:
    """Test health check system."""

    @pytest.mark.asyncio
    async def test_health_check_creation(self):
        """Test health check system creation."""
        health = HealthCheck()
        assert len(health.checks) == 0

    @pytest.mark.asyncio
    async def test_health_check_registration(self):
        """Test health check registration."""
        health = HealthCheck()

        @health.register("test-service")
        async def test_check():
            return True

        assert "test-service" in health.checks

        status = await health.check_all()
        assert status.status == HealthStatus.HEALTHY
        assert "test-service" in status.checks
        assert status.checks["test-service"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure handling."""
        health = HealthCheck()

        @health.register("failing-service")
        async def failing_check():
            raise Exception("Service unavailable")

        status = await health.check_all()
        assert status.status == HealthStatus.UNHEALTHY
        assert status.checks["failing-service"]["status"] == "unhealthy"


class TestMetrics:
    """Test metrics collection."""

    def test_metrics_collector_creation(self):
        """Test metrics collector creation."""
        metrics = MetricsCollector()
        assert metrics.registry is not None

    def test_counter_metrics(self):
        """Test counter metrics."""
        metrics = MetricsCollector()
        counter = metrics.counter("test_counter_total", "Test counter description")

        counter.inc()
        counter.inc(5)

        # Counter should have been incremented
        assert counter._value._value == 6

    def test_histogram_metrics(self):
        """Test histogram metrics."""
        metrics = MetricsCollector()
        histogram = metrics.histogram("test_duration_seconds", "Test duration")

        histogram.observe(0.1)
        histogram.observe(0.5)
        histogram.observe(1.0)

        # Histogram should have recorded observations
        assert histogram._sum._value == 1.6

    def test_gauge_metrics(self):
        """Test gauge metrics."""
        metrics = MetricsCollector()
        gauge = metrics.gauge("test_gauge", "Test gauge")

        gauge.set(42)
        assert gauge._value._value == 42

        gauge.inc(8)
        assert gauge._value._value == 50

        gauge.dec(10)
        assert gauge._value._value == 40


class TestResilience:
    """Test resilience patterns."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """Test circuit breaker with successful calls."""
        circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=1)

        call_count = 0

        @circuit_breaker.protected
        async def successful_call():
            nonlocal call_count
            call_count += 1
            return "success"

        # Should succeed
        result = await successful_call()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_failure(self):
        """Test circuit breaker with failures."""
        circuit_breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=1)

        @circuit_breaker.protected
        async def failing_call():
            raise Exception("Service error")

        # First failure
        with pytest.raises(Exception):
            await failing_call()

        # Second failure should trip the circuit breaker
        with pytest.raises(Exception):
            await failing_call()

        # Third call should be blocked by circuit breaker
        with pytest.raises(Exception):
            await failing_call()

    @pytest.mark.asyncio
    async def test_retry_policy_success(self):
        """Test retry policy with eventual success."""
        retry_policy = RetryPolicy(max_attempts=3, base_delay=0.01)

        attempt_count = 0

        @retry_policy.retry
        async def flaky_call():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await flaky_call()
        assert result == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_policy_max_attempts(self):
        """Test retry policy reaches max attempts."""
        retry_policy = RetryPolicy(max_attempts=2, base_delay=0.01)

        @retry_policy.retry
        async def always_failing_call():
            raise Exception("Always fails")

        with pytest.raises(Exception):
            await always_failing_call()


class TestLogging:
    """Test logging system."""

    def test_logger_creation(self):
        """Test logger creation."""
        logger = get_logger("test-logger")
        assert logger.name == "test-logger"

    def test_logging_setup(self):
        """Test logging setup."""
        # Test that setup doesn't raise errors
        setup_logging(level="INFO", format_type="json")
        logger = get_logger("test")

        # Test logging works
        logger.info("Test message", extra={"test_field": "test_value"})


class TestTemplates:
    """Test template system."""

    def test_template_generator_creation(self):
        """Test template generator creation."""
        generator = TemplateGenerator()
        assert generator is not None

    def test_built_in_templates(self):
        """Test built-in template availability."""
        generator = TemplateGenerator()

        # Test that built-in templates exist
        fastapi_template = generator.get_builtin_template("fastapi")
        assert fastapi_template is not None

        grpc_template = generator.get_builtin_template("grpc")
        assert grpc_template is not None

        hybrid_template = generator.get_builtin_template("hybrid")
        assert hybrid_template is not None

    def test_service_generation(self):
        """Test service generation from template."""
        generator = TemplateGenerator()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "test-service"

            generator.generate_service(
                service_name="test-service",
                service_type="fastapi",
                output_dir=str(output_dir),
                template_data={
                    "service_name": "test-service",
                    "python_package": "test_service",
                },
            )

            # Check that files were created
            assert output_dir.exists()
            assert (output_dir / "src").exists()
            assert (output_dir / "pyproject.toml").exists()


class TestServiceMesh:
    """Test service mesh manifest generation."""

    def test_manifest_generator_creation(self):
        """Test manifest generator creation."""
        generator = ManifestGenerator("test-service")
        assert generator.service_name == "test-service"

    def test_istio_manifest_generation(self):
        """Test Istio manifest generation."""
        generator = ManifestGenerator("test-service")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            generator.generate_all_manifests(
                output_dir=output_dir, service_mesh="istio", include_monitoring=True
            )

            # Check that Istio manifests were created
            istio_dir = output_dir / "istio"
            assert istio_dir.exists()
            assert (istio_dir / "deployment.yaml").exists()
            assert (istio_dir / "service.yaml").exists()
            assert (istio_dir / "virtualservice.yaml").exists()
            assert (istio_dir / "destinationrule.yaml").exists()

            # Check monitoring manifests
            monitoring_dir = output_dir / "monitoring"
            assert monitoring_dir.exists()
            assert (monitoring_dir / "servicemonitor.yaml").exists()

    def test_linkerd_manifest_generation(self):
        """Test Linkerd manifest generation."""
        generator = ManifestGenerator("test-service")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            generator.generate_all_manifests(
                output_dir=output_dir, service_mesh="linkerd", include_monitoring=False
            )

            # Check that Linkerd manifests were created
            linkerd_dir = output_dir / "linkerd"
            assert linkerd_dir.exists()
            assert (linkerd_dir / "deployment.yaml").exists()
            assert (linkerd_dir / "service.yaml").exists()
            assert (linkerd_dir / "trafficsplit.yaml").exists()
            assert (linkerd_dir / "serviceprofile.yaml").exists()


# Integration tests
class TestIntegration:
    """Integration tests for chassis components."""

    @pytest.mark.asyncio
    async def test_fastapi_service_creation(self):
        """Test FastAPI service creation with chassis."""
        config = ChassisConfig()

        # Import here to avoid circular dependencies in tests
        from marty_chassis.factories.fastapi_factory import create_fastapi_service

        app = create_fastapi_service(config)

        # Check that the app has the expected attributes
        assert app is not None
        assert hasattr(app, "router")

        # Check that health endpoints are available
        routes = [route.path for route in app.routes]
        assert any("/health" in route for route in routes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
