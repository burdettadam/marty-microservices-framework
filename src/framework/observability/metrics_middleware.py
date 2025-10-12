"""
Metrics middleware for automatic HTTP/gRPC request metrics collection.

Provides middleware that automatically tracks request counts, latencies, and error rates
for both HTTP (FastAPI) and gRPC services, registering them with Prometheus.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available, middleware will not collect metrics")


class MetricsMiddleware:
    """Base metrics middleware for collecting request metrics."""

    def __init__(self, service_name: str):
        self.service_name = service_name

        if PROMETHEUS_AVAILABLE:
            # Request metrics
            self.requests_total = Counter(
                "mmf_requests_total",
                "Total requests",
                ["service", "method", "status"],
            )

            self.request_duration = Histogram(
                "mmf_request_duration_seconds",
                "Request duration in seconds",
                ["service", "method"],
                buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            )

            # Error metrics
            self.errors_total = Counter(
                "mmf_errors_total",
                "Total errors",
                ["service", "method", "error_type"],
            )
        else:
            logger.warning("Prometheus not available, metrics middleware disabled")

    def record_request(self, method: str, status: str, duration: float) -> None:
        """Record a request metric.

        Args:
            method: Request method/endpoint
            status: Response status
            duration: Request duration in seconds
        """
        if not PROMETHEUS_AVAILABLE:
            return

        self.requests_total.labels(
            service=self.service_name, method=method, status=status
        ).inc()

        self.request_duration.labels(
            service=self.service_name, method=method
        ).observe(duration)

    def record_error(self, method: str, error_type: str) -> None:
        """Record an error metric.

        Args:
            method: Request method/endpoint
            error_type: Type of error
        """
        if not PROMETHEUS_AVAILABLE:
            return

        self.errors_total.labels(
            service=self.service_name, method=method, error_type=error_type
        ).inc()


# FastAPI middleware
try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class FastAPIMetricsMiddleware(BaseHTTPMiddleware):
        """FastAPI middleware for collecting HTTP request metrics."""

        def __init__(self, app: Any, service_name: str):
            super().__init__(app)
            self.metrics = MetricsMiddleware(service_name)

        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            """Dispatch the request and collect metrics."""
            start_time = time.time()

            try:
                response = await call_next(request)
                duration = time.time() - start_time

                # Record successful request
                method = f"{request.method} {request.url.path}"
                status = str(response.status_code)
                self.metrics.record_request(method, status, duration)

                return response

            except Exception as e:
                duration = time.time() - start_time
                error_type = type(e).__name__

                # Record error
                method = f"{request.method} {request.url.path}"
                self.metrics.record_request(method, "ERROR", duration)
                self.metrics.record_error(method, error_type)

                raise

    FASTAPI_AVAILABLE = True

except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI/Starlette not available, FastAPI metrics middleware disabled")


# gRPC middleware
try:
    import grpc
    from grpc import aio as grpc_aio

    class GRPCMetricsInterceptor(grpc.ServerInterceptor):
        """gRPC server interceptor for collecting request metrics."""

        def __init__(self, service_name: str):
            self.metrics = MetricsMiddleware(service_name)

        def intercept_service(
            self,
            continuation: Callable[..., Any],
            handler_call_details: grpc.HandlerCallDetails,
        ) -> Any:
            """Intercept gRPC service calls to collect metrics."""

            def wrapper(behavior: Callable[..., Any]) -> Callable[..., Any]:
                def wrapped_behavior(request: Any, context: grpc.ServicerContext) -> Any:
                    method = handler_call_details.method
                    start_time = time.time()

                    try:
                        response = behavior(request, context)
                        duration = time.time() - start_time

                        # Record successful request
                        self.metrics.record_request(method, "OK", duration)

                        return response

                    except Exception as e:
                        duration = time.time() - start_time
                        error_type = type(e).__name__

                        # Record error
                        self.metrics.record_request(method, "ERROR", duration)
                        self.metrics.record_error(method, error_type)

                        raise

                return wrapper(continuation(handler_call_details))

            return wrapper(continuation(handler_call_details))

    class AsyncGRPCMetricsInterceptor(grpc_aio.ServerInterceptor):
        """Async gRPC server interceptor for collecting request metrics."""

        def __init__(self, service_name: str):
            self.metrics = MetricsMiddleware(service_name)

        async def intercept_service(
            self,
            continuation: Callable[..., Any],
            handler_call_details: grpc.HandlerCallDetails,
        ) -> Any:
            """Intercept async gRPC service calls to collect metrics."""

            def wrapper(behavior: Callable[..., Any]) -> Callable[..., Any]:
                async def wrapped_behavior(request: Any, context: grpc_aio.ServicerContext) -> Any:
                    method = handler_call_details.method
                    start_time = time.time()

                    try:
                        response = await behavior(request, context)
                        duration = time.time() - start_time

                        # Record successful request
                        self.metrics.record_request(method, "OK", duration)

                        return response

                    except Exception as e:
                        duration = time.time() - start_time
                        error_type = type(e).__name__

                        # Record error
                        self.metrics.record_request(method, "OK", duration)
                        self.metrics.record_error(method, error_type)

                        raise

                return wrapper(continuation(handler_call_details))

            return wrapper(continuation(handler_call_details))

    GRPC_AVAILABLE = True

except ImportError:
    GRPC_AVAILABLE = False
    logger.warning("gRPC not available, gRPC metrics middleware disabled")


def create_fastapi_metrics_middleware(service_name: str) -> Any:
    """Create FastAPI metrics middleware.

    Args:
        service_name: Name of the service

    Returns:
        FastAPI middleware instance or None if FastAPI not available
    """
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI not available, cannot create FastAPI metrics middleware")
        return None

    def middleware_factory(app: Any) -> FastAPIMetricsMiddleware:
        return FastAPIMetricsMiddleware(app, service_name)

    return middleware_factory


def create_grpc_metrics_interceptor(service_name: str) -> GRPCMetricsInterceptor | None:
    """Create gRPC metrics interceptor.

    Args:
        service_name: Name of the service

    Returns:
        gRPC interceptor instance or None if gRPC not available
    """
    if not GRPC_AVAILABLE:
        logger.warning("gRPC not available, cannot create gRPC metrics interceptor")
        return None

    return GRPCMetricsInterceptor(service_name)


def create_async_grpc_metrics_interceptor(service_name: str) -> AsyncGRPCMetricsInterceptor | None:
    """Create async gRPC metrics interceptor.

    Args:
        service_name: Name of the service

    Returns:
        Async gRPC interceptor instance or None if gRPC not available
    """
    if not GRPC_AVAILABLE:
        logger.warning("gRPC not available, cannot create async gRPC metrics interceptor")
        return None

    return AsyncGRPCMetricsInterceptor(service_name)
