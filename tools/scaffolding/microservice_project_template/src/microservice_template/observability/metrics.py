"""Prometheus metrics helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Final

from prometheus_client import Counter, Gauge, Histogram, start_http_server

_GRPC_REQUESTS: Final[Counter] = Counter(
    "grpc_server_requests_total",
    "Total number of gRPC requests received",
    labelnames=("method", "code"),
)
_GRPC_LATENCY: Final[Histogram] = Histogram(
    "grpc_server_handling_seconds",
    "Histogram of gRPC request handling latency",
    labelnames=("method",),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
_SERVICE_HEALTH: Final[Gauge] = Gauge(
    "service_health_status",
    "Service health indicator (1=up,0=down)",
)


@dataclass(slots=True)
class MetricsServer:
    """Tiny wrapper that exposes metrics and manages the HTTP exporter."""

    host: str
    port: int
    _thread: Thread | None = field(default=None, init=False)
    _stop: Event = field(default_factory=Event, init=False)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = Thread(target=self._serve, daemon=True)
        self._thread.start()
        _SERVICE_HEALTH.set(1)

    def stop(self) -> None:
        _SERVICE_HEALTH.set(0)
        self._stop.set()

    def observe_request(self, method: str, code: str, latency_seconds: float) -> None:
        _GRPC_REQUESTS.labels(method=method, code=code).inc()
        _GRPC_LATENCY.labels(method=method).observe(latency_seconds)

    def _serve(self) -> None:
        start_http_server(port=self.port, addr=self.host)
        self._stop.wait()
