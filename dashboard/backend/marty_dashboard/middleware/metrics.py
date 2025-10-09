"""
Metrics middleware for collecting HTTP metrics.
"""

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

# Prometheus metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress", "Number of HTTP requests currently being processed"
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting HTTP metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics collection for metrics endpoint
        if request.url.path == "/metrics":
            return await call_next(request)

        # Increment in-progress counter
        http_requests_in_progress.inc()

        start_time = time.time()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            status_code = response.status_code

        except Exception as exc:
            status_code = 500
            # Re-raise the exception
            raise exc

        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            http_requests_total.labels(
                method=method, endpoint=path, status_code=status_code
            ).inc()

            http_request_duration_seconds.labels(method=method, endpoint=path).observe(
                duration
            )

            # Decrement in-progress counter
            http_requests_in_progress.dec()

        return response
