"""Health check service for Kubernetes probes."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class HealthStatus:
    """Health check status information."""

    status: str  # "healthy", "unhealthy", "degraded"
    uptime_seconds: float
    version: str
    checks: dict[str, Any]


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints."""

    def __init__(
        self, health_service: HealthService, *args: Any, **kwargs: Any
    ) -> None:
        self.health_service = health_service
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        """Handle GET requests for health endpoints."""
        if self.path == "/health" or self.path == "/health/":
            self._handle_health_check()
        elif self.path == "/health/live" or self.path == "/health/liveness":
            self._handle_liveness_check()
        elif self.path == "/health/ready" or self.path == "/health/readiness":
            self._handle_readiness_check()
        elif self.path == "/metrics":
            self._handle_metrics_redirect()
        else:
            self._send_response(404, {"error": "Not found"})

    def _handle_health_check(self) -> None:
        """Handle general health check."""
        status = self.health_service.get_health_status()
        status_code = 200 if status.status == "healthy" else 503
        self._send_response(
            status_code,
            {
                "status": status.status,
                "uptime_seconds": status.uptime_seconds,
                "version": status.version,
                "checks": status.checks,
                "timestamp": time.time(),
            },
        )

    def _handle_liveness_check(self) -> None:
        """Handle Kubernetes liveness probe."""
        # Liveness probe - is the service running?
        is_alive = self.health_service.is_alive()
        status_code = 200 if is_alive else 503
        self._send_response(
            status_code,
            {"status": "alive" if is_alive else "dead", "timestamp": time.time()},
        )

    def _handle_readiness_check(self) -> None:
        """Handle Kubernetes readiness probe."""
        # Readiness probe - is the service ready to accept traffic?
        is_ready = self.health_service.is_ready()
        status_code = 200 if is_ready else 503
        self._send_response(
            status_code,
            {"status": "ready" if is_ready else "not_ready", "timestamp": time.time()},
        )

    def _handle_metrics_redirect(self) -> None:
        """Redirect to metrics endpoint."""
        self._send_response(
            200,
            {
                "message": "Metrics available on the metrics port",
                "metrics_url": f"http://{self.health_service.metrics_host}:{self.health_service.metrics_port}/metrics",
            },
        )

    def _send_response(self, status_code: int, data: dict[str, Any]) -> None:
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        response_json = json.dumps(data, indent=2)
        self.wfile.write(response_json.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use structured logging."""
        logger.debug(
            "health.http.request",
            method=self.command,
            path=self.path,
            message=format % args,
        )


class HealthService:
    """Health check service for HTTP probes."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        metrics_host: str = "localhost",
        metrics_port: int = 9000,
        version: str = "unknown",
    ) -> None:
        self.host = host
        self.port = port
        self.metrics_host = metrics_host
        self.metrics_port = metrics_port
        self.version = version
        self._start_time = time.monotonic()
        self._logger = structlog.get_logger(__name__)

        self._server: HTTPServer | None = None
        self._thread: Thread | None = None
        self._stop_event = Event()

        # Health state
        self._is_alive = True
        self._is_ready = False
        self._custom_checks: dict[str, Callable[[], bool]] = {}

    def start(self) -> None:
        """Start the health check HTTP server."""
        if self._thread and self._thread.is_alive():
            self._logger.warning("health.server.already_running")
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._run_server, daemon=True)
        self._thread.start()
        self._logger.info("health.server.started", host=self.host, port=self.port)

    def stop(self) -> None:
        """Stop the health check HTTP server."""
        self._is_alive = False
        self._is_ready = False
        self._stop_event.set()

        if self._server:
            self._server.shutdown()
            self._server.server_close()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._logger.info("health.server.stopped")

    def set_ready(self, ready: bool = True) -> None:
        """Set service readiness status."""
        self._is_ready = ready
        self._logger.info("health.readiness.changed", ready=ready)

    def add_health_check(self, name: str, check_func: Callable[[], bool]) -> None:
        """Add a custom health check function."""
        self._custom_checks[name] = check_func
        self._logger.info("health.check.added", name=name)

    def is_alive(self) -> bool:
        """Check if service is alive (liveness probe)."""
        return self._is_alive

    def is_ready(self) -> bool:
        """Check if service is ready (readiness probe)."""
        return self._is_ready and self._is_alive

    def get_health_status(self) -> HealthStatus:
        """Get comprehensive health status."""
        uptime = time.monotonic() - self._start_time
        checks = {}

        # Run custom health checks
        overall_healthy = self._is_alive and self._is_ready

        for name, check_func in self._custom_checks.items():
            try:
                result = check_func()
                checks[name] = {
                    "status": "pass" if result else "fail",
                    "result": result,
                }
                if not result:
                    overall_healthy = False
            except Exception as e:
                checks[name] = {"status": "error", "error": str(e)}
                overall_healthy = False

        # Determine overall status
        if not self._is_alive:
            status = "unhealthy"
        elif not self._is_ready:
            status = "degraded"
        elif overall_healthy:
            status = "healthy"
        else:
            status = "degraded"

        return HealthStatus(
            status=status, uptime_seconds=uptime, version=self.version, checks=checks
        )

    def _run_server(self) -> None:
        """Run the HTTP server in thread."""
        try:
            # Create handler class with health service reference
            def handler_factory(*args: Any, **kwargs: Any) -> HealthCheckHandler:
                return HealthCheckHandler(self, *args, **kwargs)

            self._server = HTTPServer((self.host, self.port), handler_factory)
            self._server.timeout = 1.0  # Allow periodic shutdown checks

            while not self._stop_event.is_set():
                self._server.handle_request()

        except Exception as e:
            self._logger.error("health.server.error", error=str(e))
        finally:
            if self._server:
                self._server.server_close()
