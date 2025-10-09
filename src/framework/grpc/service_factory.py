"""
gRPC Service Factory for enterprise microservices.

This module provides a comprehensive factory pattern for creating, configuring,
and running gRPC services with consistent patterns across all services.
It provides DRY patterns for service creation, including automatic
service discovery and registration.
"""

from __future__ import annotations

import asyncio
import builtins
import importlib
import inspect
import logging
import signal
from concurrent import futures
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, dict, list

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_health.v1.health import HealthServicer

logger = logging.getLogger(__name__)


class ServicerFactoryProtocol(Protocol):
    """Protocol for servicer factory functions."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Create a servicer instance."""
        ...


class ServiceRegistrationProtocol(Protocol):
    """Protocol for service registration functions (add_*Servicer_to_server)."""

    def __call__(self, servicer: Any, server: grpc.aio.Server) -> None:
        """Add servicer to gRPC server."""
        ...


class ServiceDefinition:
    """Definition of a gRPC service for factory creation."""

    def __init__(
        self,
        name: str,
        servicer_factory: ServicerFactoryProtocol,
        registration_func: ServiceRegistrationProtocol,
        health_service_name: str | None = None,
        dependencies: dict[str, Any] | None = None,
        priority: int = 100,
    ) -> None:
        """Initialize service definition.

        Args:
            name: Service name for logging and identification
            servicer_factory: Function that creates servicer instances
            registration_func: Function to register servicer with server
            health_service_name: Name for health check service (optional)
            dependencies: Dependencies required by the servicer (optional)
            priority: Registration priority (lower numbers first)
        """
        self.name = name
        self.servicer_factory = servicer_factory
        self.registration_func = registration_func
        self.health_service_name = health_service_name or name
        self.dependencies = dependencies or {}
        self.priority = priority

    def create_servicer(self, **kwargs: Any) -> Any:
        """Create servicer instance with merged dependencies and kwargs."""
        merged_kwargs = {**self.dependencies, **kwargs}
        return self.servicer_factory(**merged_kwargs)

    def register_servicer(self, servicer: Any, server: grpc.aio.Server) -> None:
        """Register servicer with the gRPC server."""
        self.registration_func(servicer, server)


class GRPCServiceFactory:
    """Factory for creating and managing gRPC services with DRY patterns."""

    def __init__(self, config: builtins.dict[str, Any]) -> None:
        """Initialize the service factory with configuration.

        Args:
            config: Service configuration dictionary
        """
        self.config = config
        self.services: builtins.dict[str, ServiceDefinition] = {}
        self.server: grpc.aio.Server | None = None
        self.health_servicer: HealthServicer | None = None
        self._running = False

    def register_service(self, service_def: ServiceDefinition) -> None:
        """Register a service definition.

        Args:
            service_def: Service definition to register
        """
        self.services[service_def.name] = service_def
        logger.info("Registered service: %s", service_def.name)

    def create_server(
        self,
        port: int,
        max_workers: int = 10,
        options: builtins.list[tuple] | None = None,
        credentials: grpc.ServerCredentials | None = None,
        interceptors: builtins.list[grpc.aio.ServerInterceptor] | None = None,
    ) -> grpc.aio.Server:
        """Create and configure gRPC server.

        Args:
            port: Port to listen on
            max_workers: Maximum number of worker threads
            options: gRPC server options
            credentials: Server credentials for TLS
            interceptors: Server interceptors

        Returns:
            Configured gRPC server
        """
        # Default server options for production
        default_options = [
            ("grpc.keepalive_time_ms", 30000),
            ("grpc.keepalive_timeout_ms", 5000),
            ("grpc.keepalive_permit_without_calls", True),
            ("grpc.http2.max_pings_without_data", 0),
            ("grpc.http2.min_time_between_pings_ms", 10000),
            ("grpc.http2.min_ping_interval_without_data_ms", 5000),
        ]

        server_options = (options or []) + default_options
        server_interceptors = interceptors or []

        # Create server with thread pool
        self.server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=max_workers),
            options=server_options,
            interceptors=server_interceptors,
        )

        # Add health service
        self.health_servicer = HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(self.health_servicer, self.server)

        # Register all services
        self._register_services()

        # Add reflection (optional - requires grpcio-reflection)
        # reflection.enable_server_reflection(SERVICE_NAMES, self.server)

        # Add listen port
        if credentials:
            self.server.add_secure_port(f"[::]:{port}", credentials)
        else:
            self.server.add_insecure_port(f"[::]:{port}")

        logger.info("gRPC server configured on port %s", port)
        return self.server

    def _register_services(self) -> None:
        """Register all service definitions with the server."""
        if not self.server:
            raise RuntimeError("Server not created")

        # Sort services by priority
        sorted_services = sorted(self.services.values(), key=lambda s: s.priority)

        for service_def in sorted_services:
            try:
                # Create servicer instance
                servicer = service_def.create_servicer(config=self.config)

                # Register with server
                service_def.register_servicer(servicer, self.server)

                # Set health status
                if self.health_servicer:
                    self.health_servicer.set(
                        service_def.health_service_name,
                        health_pb2.HealthCheckResponse.ServingStatus.SERVING,
                    )

                logger.info("Registered servicer: %s", service_def.name)

            except Exception as e:
                logger.error("Failed to register service %s: %s", service_def.name, e)

                # Set health status to not serving
                if self.health_servicer:
                    self.health_servicer.set(
                        service_def.health_service_name,
                        health_pb2.HealthCheckResponse.ServingStatus.NOT_SERVING,
                    )
                raise

    async def start(self) -> None:
        """Start the gRPC server."""
        if not self.server:
            raise RuntimeError("Server not created")

        await self.server.start()
        self._running = True
        logger.info("gRPC server started")

    async def stop(self, grace_period: float = 5.0) -> None:
        """Stop the gRPC server gracefully.

        Args:
            grace_period: Grace period for shutdown in seconds
        """
        if not self.server or not self._running:
            return

        logger.info("Stopping gRPC server...")

        # Set all services to not serving
        if self.health_servicer:
            for service_def in self.services.values():
                self.health_servicer.set(
                    service_def.health_service_name,
                    health_pb2.HealthCheckResponse.ServingStatus.NOT_SERVING,
                )

        # Stop server with grace period
        await self.server.stop(grace_period)
        self._running = False
        logger.info("gRPC server stopped")

    async def wait_for_termination(self) -> None:
        """Wait for server termination."""
        if self.server:
            await self.server.wait_for_termination()


class ServiceRegistry:
    """Registry for automatic service discovery and registration."""

    def __init__(self) -> None:
        self.factories: builtins.dict[str, GRPCServiceFactory] = {}

    def register_factory(self, name: str, factory: GRPCServiceFactory) -> None:
        """Register a service factory.

        Args:
            name: Factory name
            factory: Service factory instance
        """
        self.factories[name] = factory

    def get_factory(self, name: str) -> GRPCServiceFactory | None:
        """Get a registered factory.

        Args:
            name: Factory name

        Returns:
            Service factory or None if not found
        """
        return self.factories.get(name)

    def discover_services(self, package_path: str) -> builtins.list[ServiceDefinition]:
        """Discover services in a package.

        Args:
            package_path: Python package path to scan

        Returns:
            List of discovered service definitions
        """
        services = []

        try:
            package = importlib.import_module(package_path)
            if package.__file__:
                package_dir = Path(package.__file__).parent
            else:
                logger.warning("Package %s has no __file__ attribute", package_path)
                return services

            for py_file in package_dir.glob("*_service.py"):
                module_name = f"{package_path}.{py_file.stem}"

                try:
                    module = importlib.import_module(module_name)

                    # Look for service definitions
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)

                        if (
                            inspect.isclass(attr)
                            and hasattr(attr, "__grpc_service__")
                            and attr.__grpc_service__
                        ):
                            # Create service definition from class
                            service_def = self._create_service_from_class(attr)
                            if service_def:
                                services.append(service_def)

                except ImportError as e:
                    logger.warning("Failed to import %s: %s", module_name, e)

        except ImportError as e:
            logger.error("Failed to import package %s: %s", package_path, e)

        return services

    def _create_service_from_class(self, cls: type) -> ServiceDefinition | None:
        """Create service definition from a service class.

        Args:
            cls: Service class

        Returns:
            Service definition or None if invalid
        """
        try:
            # Get service metadata
            name = getattr(cls, "__service_name__", cls.__name__)
            registration_func = getattr(cls, "__registration_func__", None)

            if not registration_func:
                logger.warning("No registration function for %s", name)
                return None

            # Create factory function
            def factory(**kwargs):
                return cls(**kwargs)

            return ServiceDefinition(
                name=name,
                servicer_factory=factory,
                registration_func=registration_func,
                health_service_name=name,
            )

        except (AttributeError, TypeError) as e:
            logger.error(
                "Failed to create service definition for %s: %s", cls.__name__, e
            )
            return None


# Global registry instance
service_registry = ServiceRegistry()


def grpc_service(
    name: str | None = None,
    registration_func: ServiceRegistrationProtocol | None = None,
    priority: int = 100,
) -> Callable[[type], type]:
    """Decorator to mark a class as a gRPC service.

    Args:
        name: Service name (defaults to class name)
        registration_func: Function to register with server
        priority: Registration priority

    Returns:
        Decorated class
    """

    def decorator(cls: type) -> type:
        cls.__grpc_service__ = True
        cls.__service_name__ = name or cls.__name__
        cls.__registration_func__ = registration_func
        cls.__priority__ = priority
        return cls

    return decorator


async def run_grpc_service(
    factory: GRPCServiceFactory,
    port: int,
    **server_kwargs: Any,
) -> None:
    """Run a gRPC service with proper signal handling.

    Args:
        factory: Service factory
        port: Port to listen on
        **server_kwargs: Additional server configuration
    """
    # Create and start server
    factory.create_server(port, **server_kwargs)
    await factory.start()

    # Setup signal handlers
    def signal_handler(signum, _frame):
        logger.info("Received signal %s", signum)
        asyncio.create_task(factory.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("gRPC service running on port %s", port)
        await factory.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await factory.stop()
