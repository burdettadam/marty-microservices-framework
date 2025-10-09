"""
Hybrid service factory for the Marty Chassis.

This module provides factory functions to create services that support
both REST (FastAPI) and gRPC protocols simultaneously.
"""

import asyncio
from typing import Any, List, Optional, Type

from fastapi import FastAPI
from grpc import aio
from marty_chassis.config import ChassisConfig
from marty_chassis.factories.fastapi_factory import create_fastapi_service
from marty_chassis.factories.grpc_factory import GRPCServiceBuilder
from marty_chassis.logger import get_logger

logger = get_logger(__name__)


class HybridService:
    """Hybrid service that runs both FastAPI and gRPC servers."""

    def __init__(
        self,
        service_name: str,
        config: Optional[ChassisConfig] = None,
        fastapi_app: Optional[FastAPI] = None,
        grpc_server: Optional[aio.Server] = None,
    ):
        self.service_name = service_name
        self.config = config or ChassisConfig.from_env()
        self.fastapi_app = fastapi_app
        self.grpc_server = grpc_server

        logger.info("Hybrid service initialized", service_name=service_name)

    async def start(self) -> None:
        """Start both FastAPI and gRPC servers."""
        tasks = []

        # Start FastAPI server
        if self.fastapi_app:
            import uvicorn

            fastapi_config = uvicorn.Config(
                app=self.fastapi_app,
                host=self.config.service.host,
                port=self.config.service.port,
                log_level="info",
            )
            fastapi_server = uvicorn.Server(fastapi_config)
            tasks.append(asyncio.create_task(fastapi_server.serve()))
            logger.info("FastAPI server starting", port=self.config.service.port)

        # Start gRPC server
        if self.grpc_server:
            await self.grpc_server.start()
            tasks.append(asyncio.create_task(self.grpc_server.wait_for_termination()))
            logger.info("gRPC server starting")

        if not tasks:
            logger.warning("No servers configured to start")
            return

        try:
            # Wait for all servers
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop both servers gracefully."""
        # Stop gRPC server
        if self.grpc_server:
            await self.grpc_server.stop(grace=5)
            logger.info("gRPC server stopped")

        logger.info("Hybrid service stopped")


class HybridServiceBuilder:
    """Builder for creating hybrid services."""

    def __init__(self, service_name: str, config: Optional[ChassisConfig] = None):
        self.service_name = service_name
        self.config = config or ChassisConfig.from_env()
        self.fastapi_app: Optional[FastAPI] = None
        self.grpc_builder: Optional[GRPCServiceBuilder] = None

        logger.info("Hybrid service builder initialized", service_name=service_name)

    def with_fastapi(
        self,
        enable_auth: bool = True,
        enable_metrics: bool = True,
        enable_health_checks: bool = True,
        enable_cors: bool = True,
        trusted_hosts: Optional[List[str]] = None,
        custom_middleware: Optional[List[Any]] = None,
    ) -> "HybridServiceBuilder":
        """Add FastAPI to the hybrid service."""
        # Use a different port for FastAPI if gRPC is also enabled
        config = self.config
        if self.grpc_builder:
            # Create a copy of config with different port for FastAPI
            config = ChassisConfig(**self.config.dict())
            config.service.port = self.config.service.port + 1

        self.fastapi_app = create_fastapi_service(
            name=self.service_name,
            config=config,
            enable_auth=enable_auth,
            enable_metrics=enable_metrics,
            enable_health_checks=enable_health_checks,
            enable_cors=enable_cors,
            trusted_hosts=trusted_hosts,
            custom_middleware=custom_middleware,
        )

        logger.info("FastAPI added to hybrid service")
        return self

    def with_grpc(
        self,
        enable_auth: bool = True,
        enable_metrics: bool = True,
        enable_reflection: bool = False,
    ) -> GRPCServiceBuilder:
        """Add gRPC to the hybrid service."""
        # Use a different port for gRPC if FastAPI is also enabled
        config = self.config
        if self.fastapi_app:
            # Create a copy of config with different port for gRPC
            config = ChassisConfig(**self.config.dict())
            config.service.port = self.config.service.port + 2

        self.grpc_builder = GRPCServiceBuilder(self.service_name, config)
        self.grpc_builder.with_auth(enable_auth)
        self.grpc_builder.with_metrics(enable_metrics)
        self.grpc_builder.with_reflection(enable_reflection)

        logger.info("gRPC builder added to hybrid service")
        return self.grpc_builder

    def add_grpc_servicer(
        self, servicer: Any, service_class: Type
    ) -> "HybridServiceBuilder":
        """Add a gRPC servicer."""
        if not self.grpc_builder:
            self.with_grpc()

        if self.grpc_builder:
            self.grpc_builder.add_servicer(servicer, service_class)
        return self

    def build(self) -> HybridService:
        """Build the hybrid service."""
        grpc_server = None
        if self.grpc_builder:
            grpc_server = self.grpc_builder.build_async_server()

        service = HybridService(
            service_name=self.service_name,
            config=self.config,
            fastapi_app=self.fastapi_app,
            grpc_server=grpc_server,
        )

        logger.info("Hybrid service built successfully")
        return service


def create_hybrid_service(
    service_name: str,
    config: Optional[ChassisConfig] = None,
    enable_fastapi: bool = True,
    enable_grpc: bool = True,
    enable_auth: bool = True,
    enable_metrics: bool = True,
    enable_health_checks: bool = True,
    enable_cors: bool = True,
    enable_grpc_reflection: bool = False,
) -> HybridServiceBuilder:
    """
    Create a hybrid service with both FastAPI and gRPC.

    Args:
        service_name: Name of the service
        config: Chassis configuration
        enable_fastapi: Enable FastAPI server
        enable_grpc: Enable gRPC server
        enable_auth: Enable authentication
        enable_metrics: Enable metrics collection
        enable_health_checks: Enable health check endpoints
        enable_cors: Enable CORS for FastAPI
        enable_grpc_reflection: Enable gRPC reflection

    Returns:
        HybridServiceBuilder instance
    """
    builder = HybridServiceBuilder(service_name, config)

    if enable_fastapi:
        builder.with_fastapi(
            enable_auth=enable_auth,
            enable_metrics=enable_metrics,
            enable_health_checks=enable_health_checks,
            enable_cors=enable_cors,
        )

    if enable_grpc:
        builder.with_grpc(
            enable_auth=enable_auth,
            enable_metrics=enable_metrics,
            enable_reflection=enable_grpc_reflection,
        )

    logger.info("Hybrid service builder created", service_name=service_name)
    return builder


async def run_hybrid_service(service: HybridService) -> None:
    """Run a hybrid service."""
    await service.start()
