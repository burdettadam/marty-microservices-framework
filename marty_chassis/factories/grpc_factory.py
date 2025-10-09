"""
gRPC service factory for the Marty Chassis.

This module provides factory functions to create gRPC services with
all cross-cutting concerns automatically configured.
"""

import asyncio
from concurrent import futures
from typing import Any, List, Optional, Type

import grpc
from grpc import aio
from grpc_reflection.v1alpha import reflection
from marty_chassis.config import ChassisConfig
from marty_chassis.logger import LogConfig, get_logger, init_global_logger
from marty_chassis.metrics import init_metrics
from marty_chassis.security import JWTAuth, RBACMiddleware

logger = get_logger(__name__)


class GRPCServiceBuilder:
    """Builder class for creating gRPC services with chassis features."""

    def __init__(self, service_name: str, config: Optional[ChassisConfig] = None):
        self.service_name = service_name
        self.config = config or ChassisConfig.from_env()
        self.servicers: List[Any] = []
        self.interceptors: List[Any] = []
        self.enable_reflection = False
        self.enable_metrics = True
        self.enable_auth = True

        # Initialize logging
        log_config = LogConfig(
            service_name=service_name,
            service_version=self.config.service.version,
            level=self.config.observability.log_level,
            format_type=self.config.observability.log_format,
        )
        init_global_logger(log_config)

        logger.info("Initializing gRPC service builder", service_name=service_name)

    def add_servicer(self, servicer: Any, service_class: Type) -> "GRPCServiceBuilder":
        """Add a gRPC servicer to the server."""
        self.servicers.append((servicer, service_class))
        logger.info(f"Added servicer: {service_class.__name__}")
        return self

    def add_interceptor(self, interceptor: Any) -> "GRPCServiceBuilder":
        """Add a gRPC interceptor."""
        self.interceptors.append(interceptor)
        logger.info(f"Added interceptor: {interceptor.__class__.__name__}")
        return self

    def with_reflection(self, enable: bool = True) -> "GRPCServiceBuilder":
        """Enable/disable gRPC reflection."""
        self.enable_reflection = enable
        return self

    def with_metrics(self, enable: bool = True) -> "GRPCServiceBuilder":
        """Enable/disable metrics collection."""
        self.enable_metrics = enable
        return self

    def with_auth(self, enable: bool = True) -> "GRPCServiceBuilder":
        """Enable/disable authentication."""
        self.enable_auth = enable
        return self

    def build_async_server(self) -> aio.Server:
        """Build an async gRPC server."""
        # Initialize metrics
        if self.enable_metrics:
            init_metrics(self.service_name, self.config.service.version)

        # Create server with interceptors
        server = aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            interceptors=self.interceptors,
        )

        # Add servicers
        for servicer, service_class in self.servicers:
            service_class.add_servicer_to_server(servicer, server)
            logger.info(f"Registered servicer: {service_class.__name__}")

        # Add reflection if enabled
        if self.enable_reflection:
            service_names = [
                service_class.DESCRIPTOR.services_by_name.values()
                for _, service_class in self.servicers
            ]
            reflection.enable_server_reflection(service_names, server)
            logger.info("gRPC reflection enabled")

        # Configure server address
        listen_addr = f"{self.config.service.host}:{self.config.service.port}"
        server.add_insecure_port(listen_addr)

        logger.info("Async gRPC server built", address=listen_addr)
        return server

    def build_sync_server(self) -> grpc.Server:
        """Build a synchronous gRPC server."""
        # Initialize metrics
        if self.enable_metrics:
            init_metrics(self.service_name, self.config.service.version)

        # Create server with interceptors
        server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=10),
            interceptors=self.interceptors,
        )

        # Add servicers
        for servicer, service_class in self.servicers:
            service_class.add_servicer_to_server(servicer, server)
            logger.info(f"Registered servicer: {service_class.__name__}")

        # Add reflection if enabled
        if self.enable_reflection:
            service_names = [
                service_class.DESCRIPTOR.services_by_name.values()
                for _, service_class in self.servicers
            ]
            reflection.enable_server_reflection(service_names, server)
            logger.info("gRPC reflection enabled")

        # Configure server address
        listen_addr = f"{self.config.service.host}:{self.config.service.port}"
        server.add_insecure_port(listen_addr)

        logger.info("Sync gRPC server built", address=listen_addr)
        return server


def create_grpc_service(
    service_name: str,
    config: Optional[ChassisConfig] = None,
    enable_auth: bool = True,
    enable_metrics: bool = True,
    enable_reflection: bool = False,
) -> GRPCServiceBuilder:
    """
    Create a gRPC service builder with chassis features.

    Args:
        service_name: Name of the service
        config: Chassis configuration
        enable_auth: Enable authentication
        enable_metrics: Enable metrics collection
        enable_reflection: Enable gRPC reflection

    Returns:
        GRPCServiceBuilder instance
    """
    builder = GRPCServiceBuilder(service_name, config)
    builder.with_auth(enable_auth)
    builder.with_metrics(enable_metrics)
    builder.with_reflection(enable_reflection)

    logger.info("gRPC service builder created", service_name=service_name)
    return builder


class AuthInterceptor(grpc.aio.ServerInterceptor):
    """gRPC authentication interceptor."""

    def __init__(self, jwt_auth: JWTAuth, rbac: Optional[RBACMiddleware] = None):
        self.jwt_auth = jwt_auth
        self.rbac = rbac

    async def intercept_service(self, continuation, handler_call_details):
        """Intercept gRPC calls for authentication."""
        # Extract metadata
        metadata = dict(handler_call_details.invocation_metadata)

        # Check for authorization header
        auth_header = metadata.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                token_data = self.jwt_auth.verify_token(token)
                # Add user context to call
                handler_call_details.invocation_metadata.append(
                    ("user_id", token_data.sub)
                )
                logger.debug("gRPC call authenticated", user_id=token_data.sub)
            except Exception as e:
                logger.warning("gRPC authentication failed", error=str(e))
                # Return unauthenticated error
                return grpc.aio.unary_unary_rpc_method_handler(
                    lambda request, context: context.abort(
                        grpc.StatusCode.UNAUTHENTICATED, "Authentication failed"
                    )
                )

        return await continuation(handler_call_details)


class MetricsInterceptor(grpc.aio.ServerInterceptor):
    """gRPC metrics collection interceptor."""

    def __init__(self, metrics_collector):
        self.metrics = metrics_collector

    async def intercept_service(self, continuation, handler_call_details):
        """Intercept gRPC calls for metrics collection."""
        import time

        method_name = handler_call_details.method
        start_time = time.time()

        try:
            response = await continuation(handler_call_details)
            duration = time.time() - start_time

            # Record successful call
            self.metrics.record_business_operation(
                operation=method_name,
                status="success",
                duration=duration,
            )

            return response
        except Exception as e:
            duration = time.time() - start_time

            # Record failed call
            self.metrics.record_business_operation(
                operation=method_name,
                status="error",
                duration=duration,
            )

            logger.error("gRPC call failed", method=method_name, error=str(e))
            raise


async def run_grpc_server(server: aio.Server) -> None:
    """Run an async gRPC server."""
    await server.start()
    logger.info("gRPC server started")

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await server.stop(grace=5)
        logger.info("gRPC server stopped")


def run_grpc_server_sync(server: grpc.Server) -> None:
    """Run a synchronous gRPC server."""
    server.start()
    logger.info("gRPC server started")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        server.stop(grace=5)
        logger.info("gRPC server stopped")
