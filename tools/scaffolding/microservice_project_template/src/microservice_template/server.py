"""AsyncIO gRPC server bootstrap."""

from __future__ import annotations

import asyncio
import signal

import grpc
import structlog
from microservice_template.config import AppSettings
from microservice_template.observability import MetricsServer
from microservice_template.observability.health import HealthService
from microservice_template.proto import greeter_pb2_grpc
from microservice_template.service import GreeterService


class GRPCServer:
    """Orchestrates gRPC lifecycle, metrics, and graceful shutdown."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._logger = structlog.get_logger(__name__)

        # Metrics server
        host, port = settings.metrics_bind
        self._metrics = MetricsServer(host=host, port=port)

        # Health check server
        self._health = HealthService(
            host=host,
            port=8080,  # Standard health check port
            metrics_host=host,
            metrics_port=port,
            version=settings.version,
        )

        # gRPC server setup
        self._server = grpc.aio.server(
            options=[
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_timeout_ms", 5000),
            ]
        )
        greeter_pb2_grpc.add_GreeterServiceServicer_to_server(
            GreeterService(settings=settings, metrics=self._metrics),
            self._server,
        )
        self._server.add_insecure_port(settings.grpc_bind)

    async def serve_forever(self, shutdown_after: float | None = None) -> None:
        await self.start()
        await self._wait_for_termination(shutdown_after)

    async def _wait_for_termination(self, shutdown_after: float | None) -> None:
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        try:
            if shutdown_after is None:
                await stop_event.wait()
            else:
                await asyncio.wait_for(stop_event.wait(), timeout=shutdown_after)
        except TimeoutError:
            structlog.get_logger(__name__).info(
                "grpc.server.shutdown_timer.elapsed", seconds=shutdown_after
            )

        await self._shutdown()

    async def start(self) -> None:
        self._metrics.start()
        self._health.start()
        await self._server.start()
        self._health.set_ready(True)  # Mark as ready after successful start
        self._logger.info("grpc.server.started", bind=self._settings.grpc_bind)

    async def stop(self) -> None:
        self._logger.info("grpc.server.stopping")
        self._health.set_ready(False)  # Mark as not ready during shutdown
        await self._server.stop(self._settings.shutdown_grace_period)
        self._metrics.stop()
        self._health.stop()
        self._logger.info("grpc.server.stopped")

    async def _shutdown(self) -> None:
        await self.stop()


async def serve(settings: AppSettings, shutdown_after: float | None = None) -> None:
    server = GRPCServer(settings)
    await server.serve_forever(shutdown_after=shutdown_after)
