"""
Observability components for enterprise microservices.

This package provides:
- Distributed tracing with OpenTelemetry
- Metrics collection and monitoring
- Structured logging
- Health checking
"""

from .framework_metrics import FrameworkMetrics, get_framework_metrics
from .metrics_middleware import (
    create_async_grpc_metrics_interceptor,
    create_fastapi_metrics_middleware,
    create_grpc_metrics_interceptor,
)
from .monitoring import MetricsCollector, ServiceMonitor
from .tracing import (
    auto_instrument,
    get_tracer,
    init_tracing,
    instrument_fastapi,
    instrument_grpc,
    instrument_kafka,
    instrument_requests,
    instrument_sqlalchemy,
    shutdown_tracing,
    trace_function,
    traced_operation,
)

__all__ = [
    "auto_instrument",
    "create_async_grpc_metrics_interceptor",
    "create_fastapi_metrics_middleware",
    "create_grpc_metrics_interceptor",
    "FrameworkMetrics",
    "get_framework_metrics",
    "get_tracer",
    "init_observability",
    "init_tracing",
    "instrument_fastapi",
    "instrument_grpc",
    "instrument_kafka",
    "instrument_requests",
    "instrument_sqlalchemy",
    "MetricsCollector",
    "ServiceMonitor",
    "shutdown_tracing",
    "trace_function",
    "traced_operation",
]


def init_observability(service_name: str) -> ServiceMonitor:
    """Initialize all observability components for a service.

    This function sets up:
    - OpenTelemetry tracing with auto-instrumentation
    - Prometheus metrics collection
    - Health monitoring
    - System metrics collection

    Args:
        service_name: Name of the service

    Returns:
        ServiceMonitor instance for health and metrics management
    """
    # Initialize tracing
    init_tracing(service_name)

    # Auto-instrument common libraries
    auto_instrument()

    # Create service monitor (includes metrics and health checking)
    monitor = ServiceMonitor(service_name)

    # Start monitoring
    monitor.start_monitoring()

    return monitor
