"""
Middleware for request processing.
"""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def add_correlation_id_middleware(app):
    """Add correlation ID middleware to track requests."""

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next: Callable):
        """Add correlation ID to each request."""
        correlation_id = str(uuid.uuid4())

        # Add to request state
        request.state.correlation_id = correlation_id

        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        # Add to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = str(process_time)

        return response
