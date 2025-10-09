"""
Metrics collection system for the Marty Chassis.

This module provides:
- Prometheus metrics collection
- Automatic HTTP request metrics
- Custom metric registration
- Grafana-compatible metrics export
"""

import time
from typing import Any, Dict, List, Optional, Union

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from ..logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Centralized metrics collector using Prometheus client."""

    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        self.service_name = service_name
        self.service_version = service_version

        # HTTP request metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
        )

        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        self.http_requests_in_progress = Gauge(
            "http_requests_in_progress",
            "HTTP requests currently in progress",
            ["method", "endpoint"],
        )

        # Service health metrics
        self.health_check_status = Gauge(
            "health_check_status",
            "Health check status (1=healthy, 0.5=degraded, 0=unhealthy)",
            ["check_name"],
        )

        self.health_check_duration_seconds = Histogram(
            "health_check_duration_seconds",
            "Health check duration in seconds",
            ["check_name"],
        )

        # Business metrics
        self.business_operations_total = Counter(
            "business_operations_total",
            "Total business operations",
            ["operation", "status"],
        )

        self.business_operation_duration_seconds = Histogram(
            "business_operation_duration_seconds",
            "Business operation duration in seconds",
            ["operation"],
        )

        # System metrics
        self.active_connections = Gauge(
            "active_connections",
            "Number of active connections",
            ["connection_type"],
        )

        # Service info metric
        self.service_info = Gauge(
            "service_info",
            "Service information",
            ["name", "version"],
        )
        self.service_info.labels(name=service_name, version=service_version).set(1)

        logger.info("Metrics collector initialized", service_name=service_name)

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
    ) -> None:
        """Record HTTP request metrics."""
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
        ).inc()

        self.http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

    def start_http_request(self, method: str, endpoint: str) -> None:
        """Mark start of HTTP request."""
        self.http_requests_in_progress.labels(
            method=method,
            endpoint=endpoint,
        ).inc()

    def end_http_request(self, method: str, endpoint: str) -> None:
        """Mark end of HTTP request."""
        self.http_requests_in_progress.labels(
            method=method,
            endpoint=endpoint,
        ).dec()

    def record_health_check(
        self,
        check_name: str,
        status: str,
        duration: float,
    ) -> None:
        """Record health check metrics."""
        # Convert status to numeric value
        status_value = {
            "healthy": 1.0,
            "degraded": 0.5,
            "unhealthy": 0.0,
        }.get(status, 0.0)

        self.health_check_status.labels(check_name=check_name).set(status_value)
        self.health_check_duration_seconds.labels(check_name=check_name).observe(
            duration
        )

    def record_business_operation(
        self,
        operation: str,
        status: str,
        duration: Optional[float] = None,
    ) -> None:
        """Record business operation metrics."""
        self.business_operations_total.labels(
            operation=operation,
            status=status,
        ).inc()

        if duration is not None:
            self.business_operation_duration_seconds.labels(
                operation=operation,
            ).observe(duration)

    def set_active_connections(self, connection_type: str, count: int) -> None:
        """Set active connections count."""
        self.active_connections.labels(connection_type=connection_type).set(count)

    def increment_counter(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a custom counter metric."""
        if not hasattr(self, f"_counter_{name}"):
            counter = Counter(
                f"custom_{name}_total",
                f"Custom counter: {name}",
                list(labels.keys()) if labels else [],
            )
            setattr(self, f"_counter_{name}", counter)

        counter = getattr(self, f"_counter_{name}")
        if labels:
            counter.labels(**labels).inc()
        else:
            counter.inc()

    def set_gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a custom gauge metric."""
        if not hasattr(self, f"_gauge_{name}"):
            gauge = Gauge(
                f"custom_{name}",
                f"Custom gauge: {name}",
                list(labels.keys()) if labels else [],
            )
            setattr(self, f"_gauge_{name}", gauge)

        gauge = getattr(self, f"_gauge_{name}")
        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> None:
        """Observe a custom histogram metric."""
        if not hasattr(self, f"_histogram_{name}"):
            histogram = Histogram(
                f"custom_{name}",
                f"Custom histogram: {name}",
                list(labels.keys()) if labels else [],
                buckets=buckets or [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            )
            setattr(self, f"_histogram_{name}", histogram)

        histogram = getattr(self, f"_histogram_{name}")
        if labels:
            histogram.labels(**labels).observe(value)
        else:
            histogram.observe(value)


class HTTPMetricsMiddleware:
    """FastAPI middleware for automatic HTTP metrics collection."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector

    def get_endpoint_from_request(self, request: Request) -> str:
        """Extract endpoint pattern from request."""
        # Try to get the route pattern
        if hasattr(request, "route") and hasattr(request.route, "path"):
            return request.route.path

        # Fallback to URL path
        return request.url.path

    async def __call__(self, request: Request, call_next):
        """Process HTTP request and collect metrics."""
        method = request.method
        endpoint = self.get_endpoint_from_request(request)

        # Start tracking request
        self.metrics.start_http_request(method, endpoint)
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Record error metric
            status_code = 500
            logger.error("Request processing failed", error=str(e))
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            self.metrics.record_http_request(method, endpoint, status_code, duration)
            self.metrics.end_http_request(method, endpoint)

        return response


def prometheus_middleware(metrics_collector: MetricsCollector):
    """Create Prometheus metrics middleware."""
    return HTTPMetricsMiddleware(metrics_collector)


def get_metrics_response() -> Response:
    """Generate Prometheus metrics response."""
    try:
        metrics_data = generate_latest(REGISTRY)
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST,
        )
    except Exception as e:
        logger.error("Failed to generate metrics", error=str(e))
        return Response(
            content="# Failed to generate metrics\n",
            status_code=500,
            media_type=CONTENT_TYPE_LATEST,
        )


class BusinessMetricsTracker:
    """Helper class for tracking business operation metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector

    def track_operation(self, operation: str):
        """Context manager for tracking business operations."""
        return OperationTracker(self.metrics, operation)


class OperationTracker:
    """Context manager for tracking operation duration and status."""

    def __init__(self, metrics_collector: MetricsCollector, operation: str):
        self.metrics = metrics_collector
        self.operation = operation
        self.start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            status = "success" if exc_type is None else "error"
            self.metrics.record_business_operation(
                self.operation,
                status,
                duration,
            )


# Global metrics collector instance
_global_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector("marty_chassis")
    return _global_metrics_collector


def init_metrics(service_name: str, service_version: str = "1.0.0") -> MetricsCollector:
    """Initialize global metrics collector."""
    global _global_metrics_collector
    _global_metrics_collector = MetricsCollector(service_name, service_version)
    return _global_metrics_collector
