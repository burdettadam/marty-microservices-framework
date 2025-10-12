"""
Enhanced gRPC Service Factory with Unified Observability.

This module provides a factory for creating gRPC services with automatic
observability integration using the unified configuration system.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import grpc

# MMF imports
from framework.config_factory import create_service_config
from framework.observability.unified_observability import create_observability_manager
from grpc import aio
from grpc_reflection.v1alpha import reflection

logger = logging.getLogger(__name__)


class ObservableGrpcServiceMixin:
    """
    Mixin class that adds observability capabilities to gRPC services.

    This mixin automatically integrates metrics, tracing, and health checks
    for gRPC services using the unified configuration system.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Observability will be set by the factory
        self.observability = None
        self.service_metrics = {}

    def _setup_observability(self, config):
        """Setup observability for the gRPC service."""
        self.observability = create_observability_manager(config)

        # Setup common gRPC metrics
        self.service_metrics = {
            "requests_total": self.observability.counter(
                "grpc_requests_total", "Total gRPC requests", ["method", "status"]
            ),
            "request_duration": self.observability.histogram(
                "grpc_request_duration_seconds", "gRPC request duration", ["method"]
            ),
            "active_connections": self.observability.gauge(
                "grpc_active_connections", "Active gRPC connections"
            ),
        }

        # Register health checks
        self._register_grpc_health_checks()

    def _register_grpc_health_checks(self):
        """Register gRPC-specific health checks."""
        if self.observability:
            # gRPC service health check
            self.observability.register_health_check(
                name="grpc_service", check_func=self._check_grpc_service_health, interval_seconds=30
            )

    async def _check_grpc_service_health(self):
        """Check gRPC service health."""
        from framework.observability.monitoring import HealthStatus

        try:
            # Check if service is accepting connections
            # This is a placeholder - actual implementation would check server state
            return HealthStatus.HEALTHY
        except Exception:
            return HealthStatus.UNHEALTHY

    def trace_grpc_call(self, method_name: str):
        """Decorator factory for tracing gRPC method calls."""

        def decorator(func):
            async def wrapper(request, context):
                if not self.observability:
                    return await func(request, context)

                with self.observability.trace_operation(
                    f"grpc.{method_name}",
                    grpc_method=method_name,
                    service=self.observability.service_name,
                ) as span:
                    start_time = asyncio.get_event_loop().time()

                    try:
                        # Execute the gRPC method
                        result = await func(request, context)

                        # Record success metrics
                        duration = asyncio.get_event_loop().time() - start_time

                        if self.service_metrics:
                            self.service_metrics["requests_total"].labels(
                                method=method_name, status="OK"
                            ).inc()

                            self.service_metrics["request_duration"].labels(
                                method=method_name
                            ).observe(duration)

                        if span:
                            span.set_attribute("grpc.success", True)
                            span.set_attribute("grpc.status", "OK")
                            span.set_attribute("grpc.duration", duration)

                        return result

                    except Exception as e:
                        # Record error metrics
                        if self.service_metrics:
                            self.service_metrics["requests_total"].labels(
                                method=method_name, status="ERROR"
                            ).inc()

                        if span:
                            span.set_attribute("grpc.success", False)
                            span.set_attribute("grpc.error", str(e))
                            span.set_attribute("grpc.error_type", type(e).__name__)

                        raise

            return wrapper

        return decorator


class UnifiedGrpcServer:
    """
    gRPC server with unified observability integration.

    This server automatically configures metrics endpoints, health checks,
    and distributed tracing based on the service configuration.
    """

    def __init__(self, config_path: str = None, service_name: str = None):
        """
        Initialize the gRPC server with unified configuration.

        Args:
            config_path: Path to service configuration file
            service_name: Name of the service (used for config file lookup)
        """
        self.logger = logging.getLogger("marty.grpc.server")

        # Load configuration
        if config_path:
            self.config = create_service_config(config_path)
        elif service_name:
            self.config = create_service_config(f"config/services/{service_name}.yaml")
        else:
            raise ValueError("Either config_path or service_name must be provided")

        # Setup observability
        self.observability = create_observability_manager(self.config)

        # gRPC server components
        self.server: aio.Server | None = None
        self.servicer_instances: dict[str, Any] = {}
        self._running = False

        self.logger.info("Unified gRPC server initialized for %s", self.config.service_name)

    def add_servicer(self, servicer_class: type, add_servicer_func: callable, *args, **kwargs):
        """
        Add a servicer to the gRPC server with observability integration.

        Args:
            servicer_class: The servicer class to instantiate
            add_servicer_func: Function to add servicer to server (from pb2_grpc)
            *args, **kwargs: Arguments to pass to servicer constructor
        """
        # Create servicer instance
        if issubclass(servicer_class, ObservableGrpcServiceMixin):
            servicer = servicer_class(*args, **kwargs)
            servicer._setup_observability(self.config)
        else:
            servicer = servicer_class(*args, **kwargs)

        # Store servicer reference
        servicer_name = servicer_class.__name__
        self.servicer_instances[servicer_name] = servicer

        # Add to server (will be called when server is created)
        if not hasattr(self, "_pending_servicers"):
            self._pending_servicers = []

        self._pending_servicers.append((add_servicer_func, servicer))

        self.logger.info("Added servicer: %s", servicer_name)

    async def start(self):
        """Start the gRPC server with observability endpoints."""
        try:
            # Create gRPC server
            self.server = aio.server()

            # Add all pending servicers
            if hasattr(self, "_pending_servicers"):
                for add_func, servicer in self._pending_servicers:
                    add_func(servicer, self.server)

            # Enable reflection
            service_names = (
                reflection.SERVICE_NAME,
                *[desc.full_name for desc in self.server.get_services()],
            )
            reflection.enable_server_reflection(service_names, self.server)

            # Configure TLS if enabled
            listen_addr = self._configure_server_address()

            # Start server
            await self.server.start()
            self._running = True

            # Start observability endpoints
            await self._start_observability_endpoints()

            self.logger.info("gRPC server started on %s", listen_addr)

        except Exception as e:
            self.logger.error("Failed to start gRPC server: %s", e)
            raise

    def _configure_server_address(self) -> str:
        """Configure server listen address with TLS if enabled."""
        service_discovery = self.config.service_discovery
        service_name = self.config.service_name.replace("-", "_")
        port = service_discovery.ports.get(service_name, 8080)

        listen_addr = f"[::]:{port}"

        if self.config.security.grpc_tls and self.config.security.grpc_tls.enabled:
            # Load TLS credentials
            server_cert = self.config.security.grpc_tls.server_cert
            server_key = self.config.security.grpc_tls.server_key

            with open(server_cert, "rb") as f:
                cert_data = f.read()
            with open(server_key, "rb") as f:
                key_data = f.read()

            credentials = grpc.ssl_server_credentials([(key_data, cert_data)])
            self.server.add_secure_port(listen_addr, credentials)

            self.logger.info("gRPC TLS enabled")
        else:
            self.server.add_insecure_port(listen_addr)

        return listen_addr

    async def _start_observability_endpoints(self):
        """Start metrics and health check HTTP endpoints."""
        if not self.observability.monitoring_config.enabled:
            return

        from aiohttp import web, web_runner

        # Create HTTP application for observability endpoints
        app = web.Application()

        # Metrics endpoint
        if self.observability.monitoring_config.prometheus:
            app.router.add_get("/metrics", self._metrics_handler)

        # Health check endpoints
        app.router.add_get("/health", self._health_handler)
        app.router.add_get("/readiness", self._readiness_handler)
        app.router.add_get("/liveness", self._liveness_handler)

        # Start HTTP server for observability
        runner = web_runner.AppRunner(app)
        await runner.setup()

        health_port = self.observability.monitoring_config.health_check_port
        site = web_runner.TCPSite(runner, "localhost", health_port)
        await site.start()

        self.logger.info("Observability endpoints started on port %d", health_port)

    async def _metrics_handler(self, request):
        """Handle Prometheus metrics requests."""
        from aiohttp import web

        metrics_output = self.observability.get_metrics_output()
        return web.Response(text=metrics_output, content_type="text/plain")

    async def _health_handler(self, request):
        """Handle general health check requests."""
        from aiohttp import web

        health_status = await self.observability.get_health_status()

        # Determine overall health
        is_healthy = all(
            status.get("status") in ["healthy", "HEALTHY"] for status in health_status.values()
        )

        status_code = 200 if is_healthy else 503
        return web.json_response(health_status, status=status_code)

    async def _readiness_handler(self, request):
        """Handle readiness probe requests."""
        from aiohttp import web

        # Check if server is ready to accept traffic
        is_ready = self._running and self.server is not None

        if is_ready:
            return web.json_response({"status": "ready"})
        else:
            return web.json_response({"status": "not_ready"}, status=503)

    async def _liveness_handler(self, request):
        """Handle liveness probe requests."""
        from aiohttp import web

        # Check if server is alive (basic check)
        return web.json_response({"status": "alive"})

    async def serve(self):
        """Run the server until shutdown."""
        await self.start()

        try:
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the gRPC server."""
        if self.server and self._running:
            self.logger.info("Stopping gRPC server...")
            await self.server.stop(grace=30)
            self._running = False

            # Shutdown observability
            await self.observability.shutdown()

            self.logger.info("gRPC server stopped")


# Factory functions for common service patterns


def create_trust_anchor_server(config_path: str = None) -> UnifiedGrpcServer:
    """Create a gRPC server for trust anchor service."""
    server = UnifiedGrpcServer(config_path=config_path or "config/services/trust_anchor.yaml")
    return server


def create_document_signer_server(config_path: str = None) -> UnifiedGrpcServer:
    """Create a gRPC server for document signer service."""
    server = UnifiedGrpcServer(config_path=config_path or "config/services/document_signer.yaml")
    return server


def create_service_server(service_name: str, config_path: str = None) -> UnifiedGrpcServer:
    """Create a gRPC server for any Marty service."""
    if config_path:
        server = UnifiedGrpcServer(config_path=config_path)
    else:
        server = UnifiedGrpcServer(service_name=service_name)

    return server
