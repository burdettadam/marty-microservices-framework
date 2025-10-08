"""
Observability components for enterprise microservices.

This package provides:
- Distributed tracing with OpenTelemetry
- Metrics collection and monitoring
- Structured logging
- Health checking
"""

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
    "get_tracer",
    "init_tracing",
    "instrument_fastapi",
    "instrument_grpc",
    "instrument_kafka",
    "instrument_requests",
    "instrument_sqlalchemy",
    "shutdown_tracing",
    "trace_function",
    "traced_operation",
]
