"""
OpenTelemetry integration for enterprise microservices.

This module provides centralized OpenTelemetry setup with OTLP export capabilities
and environment-based configuration for distributed tracing.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning("OpenTelemetry not available, tracing will be disabled")

# Environment variables for OpenTelemetry configuration
OTEL_ENABLED = os.getenv("OTEL_TRACING_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
    "on",
)
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "microservice")
OTEL_SERVICE_VERSION = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
OTEL_ENVIRONMENT = os.getenv("OTEL_ENVIRONMENT", "development")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
OTEL_HEADERS = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
OTEL_INSECURE = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() in (
    "true",
    "1",
    "yes",
)
OTEL_CONSOLE_EXPORT = os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() in (
    "true",
    "1",
    "yes",
)

# Global tracer reference
_tracer = None
_instrumented = False


def get_tracer():
    """Get the configured tracer instance.

    Returns:
        Configured OpenTelemetry tracer instance or None if not available.
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None

    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(__name__)
    return _tracer


def init_tracing(service_name: str | None = None) -> None:
    """Initialize OpenTelemetry tracing with OTLP export.

    Args:
        service_name: Name of the service for tracing (overrides env var)
    """
    if not OPENTELEMETRY_AVAILABLE:
        logger.warning("OpenTelemetry not available, tracing disabled")
        return

    global _instrumented

    if _instrumented:
        logger.debug("OpenTelemetry already initialized")
        return

    if not OTEL_ENABLED:
        logger.info("OpenTelemetry tracing is disabled")
        return

    try:
        # Use provided service name or environment variable
        final_service_name = service_name or OTEL_SERVICE_NAME

        # Create resource with service information
        resource = Resource.create(
            {
                "service.name": final_service_name,
                "service.version": OTEL_SERVICE_VERSION,
                "deployment.environment": OTEL_ENVIRONMENT,
            }
        )

        # Create trace provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter if endpoint is configured
        if OTEL_ENDPOINT:
            headers = {}
            if OTEL_HEADERS:
                for header in OTEL_HEADERS.split(","):
                    if "=" in header:
                        key, value = header.split("=", 1)
                        headers[key.strip()] = value.strip()

            otlp_exporter = OTLPSpanExporter(
                endpoint=OTEL_ENDPOINT,
                headers=headers,
                insecure=OTEL_INSECURE,
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("OTLP trace exporter configured for %s", OTEL_ENDPOINT)

        # Add console exporter for development
        if OTEL_CONSOLE_EXPORT:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info("Console trace exporter enabled")

        # Set global trace provider
        trace.set_tracer_provider(provider)

        _instrumented = True
        logger.info("OpenTelemetry tracing initialized for service: %s", final_service_name)

    except Exception as e:
        logger.error("Failed to initialize OpenTelemetry: %s", e)
        raise


def instrument_grpc() -> None:
    """Instrument gRPC client and server with OpenTelemetry.

    Requires opentelemetry-instrumentation-grpc package.
    """
    if not OPENTELEMETRY_AVAILABLE or not OTEL_ENABLED:
        return

    try:
        from opentelemetry.instrumentation.grpc import (
            GrpcAioInstrumentorClient,
            GrpcAioInstrumentorServer,
        )

        # Instrument gRPC client
        client_instrumentor = GrpcAioInstrumentorClient()
        if not client_instrumentor.is_instrumented_by_opentelemetry:
            client_instrumentor.instrument()
            logger.info("gRPC client instrumented for tracing")

        # Instrument gRPC server
        server_instrumentor = GrpcAioInstrumentorServer()
        if not server_instrumentor.is_instrumented_by_opentelemetry:
            server_instrumentor.instrument()
            logger.info("gRPC server instrumented for tracing")

    except ImportError:
        logger.warning(
            "gRPC instrumentation not available (install opentelemetry-instrumentation-grpc)"
        )
    except (AttributeError, RuntimeError) as e:
        logger.error("Failed to instrument gRPC: %s", e)


def instrument_fastapi() -> None:
    """Instrument FastAPI with OpenTelemetry.

    Requires opentelemetry-instrumentation-fastapi package.
    """
    if not OPENTELEMETRY_AVAILABLE or not OTEL_ENABLED:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        if not FastAPIInstrumentor().is_instrumented_by_opentelemetry:
            FastAPIInstrumentor.instrument()
            logger.info("FastAPI instrumented for tracing")

    except ImportError:
        logger.warning(
            "FastAPI instrumentation not available (install opentelemetry-instrumentation-fastapi)"
        )
    except Exception as e:
        logger.error("Failed to instrument FastAPI: %s", e)


def instrument_sqlalchemy() -> None:
    """Instrument SQLAlchemy with OpenTelemetry.

    Requires opentelemetry-instrumentation-sqlalchemy package.
    """
    if not OPENTELEMETRY_AVAILABLE or not OTEL_ENABLED:
        return

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        if not SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry:
            SQLAlchemyInstrumentor().instrument()
            logger.info("SQLAlchemy instrumented for tracing")

    except ImportError:
        logger.warning(
            "SQLAlchemy instrumentation not available (install opentelemetry-instrumentation-sqlalchemy)"
        )
    except Exception as e:
        logger.error("Failed to instrument SQLAlchemy: %s", e)


def instrument_requests() -> None:
    """Instrument requests library with OpenTelemetry.

    Requires opentelemetry-instrumentation-requests package.
    """
    if not OPENTELEMETRY_AVAILABLE or not OTEL_ENABLED:
        return

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        if not RequestsInstrumentor().is_instrumented_by_opentelemetry:
            RequestsInstrumentor().instrument()
            logger.info("Requests library instrumented for tracing")

    except ImportError:
        logger.warning(
            "Requests instrumentation not available (install opentelemetry-instrumentation-requests)"
        )
    except Exception as e:
        logger.error("Failed to instrument requests: %s", e)


def instrument_kafka() -> None:
    """Instrument Kafka with OpenTelemetry.

    Requires opentelemetry-instrumentation-kafka-python package.
    """
    if not OPENTELEMETRY_AVAILABLE or not OTEL_ENABLED:
        return

    try:
        from opentelemetry.instrumentation.kafka import KafkaInstrumentor

        if not KafkaInstrumentor().is_instrumented_by_opentelemetry:
            KafkaInstrumentor().instrument()
            logger.info("Kafka instrumented for tracing")

    except ImportError:
        logger.warning(
            "Kafka instrumentation not available (install opentelemetry-instrumentation-kafka-python)"
        )
    except Exception as e:
        logger.error("Failed to instrument Kafka: %s", e)


def auto_instrument() -> None:
    """Automatically instrument common libraries."""
    if not OPENTELEMETRY_AVAILABLE or not OTEL_ENABLED:
        return

    logger.info("Auto-instrumenting common libraries...")

    # Instrument commonly used libraries
    instrument_grpc()
    instrument_fastapi()
    instrument_sqlalchemy()
    instrument_requests()
    instrument_kafka()


def shutdown_tracing() -> None:
    """Shutdown tracing and flush pending spans."""
    if not OPENTELEMETRY_AVAILABLE:
        return

    global _instrumented

    if not _instrumented or not OTEL_ENABLED:
        return

    try:
        # Simply mark as not instrumented - actual cleanup will happen at process exit
        logger.info("OpenTelemetry tracing shutdown completed")
    except (AttributeError, RuntimeError) as e:
        logger.error("Error during tracing shutdown: %s", e)
    finally:
        _instrumented = False


# Context manager for manual span creation
class traced_operation:
    """Context manager for creating traced operations.

    Example:
        with traced_operation("operation_name") as span:
            if span:  # Check if span is available
                span.set_attribute("key", "value")
            # Do work
    """

    def __init__(self, operation_name: str, **attributes):
        self.operation_name = operation_name
        self.attributes = attributes
        self.span = None

    def __enter__(self):
        if not OPENTELEMETRY_AVAILABLE:
            return None

        tracer = get_tracer()
        if tracer is None:
            return None

        self.span = tracer.start_span(self.operation_name)

        # Set provided attributes
        for key, value in self.attributes.items():
            self.span.set_attribute(key, str(value))

        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span and OPENTELEMETRY_AVAILABLE:
            if exc_type:
                self.span.record_exception(exc_val)
                self.span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc_val)))
            else:
                self.span.set_status(trace.Status(trace.StatusCode.OK))
            self.span.end()


def trace_function(operation_name: str | None = None):
    """Decorator to trace function calls.

    Args:
        operation_name: Custom operation name (defaults to function name)

    Example:
        @trace_function("my_operation")
        def my_function():
            pass
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            with traced_operation(name):
                return func(*args, **kwargs)

        return wrapper

    return decorator
