"""
Request Tracing Middleware Plugin Example.

This plugin demonstrates how to implement middleware
functionality using the middleware plugin interface.
"""

import time
import uuid
from typing import Any, Dict

from ..decorators import middleware, plugin
from ..interfaces import IMiddlewarePlugin, PluginContext, PluginMetadata


@plugin(
    name="request-tracing",
    version="1.0.0",
    description="Request tracing middleware that adds correlation IDs and tracks timing",
    author="Marty Team",
    provides=["tracing", "correlation-id", "timing"],
)
class RequestTracingPlugin(IMiddlewarePlugin):
    """
    Request tracing middleware plugin.

    This plugin demonstrates:
    - Middleware implementation
    - Request/response processing
    - Correlation ID generation
    - Request timing
    """

    def __init__(self):
        super().__init__()
        self.total_requests = 0
        self.total_time = 0.0

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the tracing plugin."""
        await super().initialize(context)

        # Register tracing service
        if context.service_registry:
            context.service_registry.register_service(
                "request-tracing",
                {
                    "type": "middleware",
                    "plugin": self.plugin_metadata.name,
                    "priority": self.get_middleware_priority(),
                    "tags": ["tracing", "middleware", "observability"],
                },
            )

        self.logger.info("Request tracing middleware initialized")

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="request-tracing",
            version="1.0.0",
            description="Request tracing middleware that adds correlation IDs and tracks timing",
            author="Marty Team",
            provides=["tracing", "correlation-id", "timing"],
        )

    async def process_request(self, request: Any, call_next) -> Any:
        """
        Process an incoming request with tracing.

        Args:
            request: The incoming request object
            call_next: Function to call the next middleware/handler

        Returns:
            Response object
        """
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        start_time = time.time()

        # Add correlation ID to request
        if hasattr(request, "headers"):
            request.headers["X-Correlation-ID"] = correlation_id
        elif hasattr(request, "state"):
            request.state.correlation_id = correlation_id

        self.logger.info(f"Request started: {correlation_id}")

        try:
            # Call next middleware/handler
            response = await call_next(request)

            # Calculate processing time
            processing_time = time.time() - start_time
            self.total_requests += 1
            self.total_time += processing_time

            # Add tracing headers to response
            if hasattr(response, "headers"):
                response.headers["X-Correlation-ID"] = correlation_id
                response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"

            self.logger.info(
                f"Request completed: {correlation_id} ({processing_time:.3f}s)"
            )

            # Publish tracing event
            if self.context and self.context.event_bus:
                await self.context.event_bus.publish(
                    "request.completed",
                    {
                        "correlation_id": correlation_id,
                        "processing_time": processing_time,
                        "status": getattr(response, "status_code", "unknown"),
                    },
                    source=self.plugin_metadata.name,
                )

            return response

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(
                f"Request failed: {correlation_id} ({processing_time:.3f}s) - {e}"
            )

            # Publish error event
            if self.context and self.context.event_bus:
                await self.context.event_bus.publish(
                    "request.failed",
                    {
                        "correlation_id": correlation_id,
                        "processing_time": processing_time,
                        "error": str(e),
                    },
                    source=self.plugin_metadata.name,
                )

            raise

    def get_middleware_priority(self) -> int:
        """
        Return the priority of this middleware.

        Returns:
            Priority value (lower = higher priority)
        """
        return 10  # Run early in the middleware chain

    async def get_metrics(self) -> Dict[str, Any]:
        """Get tracing metrics."""
        avg_time = (
            self.total_time / self.total_requests if self.total_requests > 0 else 0
        )

        return {
            "total_requests": self.total_requests,
            "total_processing_time": self.total_time,
            "average_processing_time": avg_time,
            "requests_per_second": self.total_requests / self.total_time
            if self.total_time > 0
            else 0,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health = await super().health_check()

        # Add tracing-specific health information
        health["details"] = {
            "total_requests": self.total_requests,
            "average_processing_time": self.total_time / self.total_requests
            if self.total_requests > 0
            else 0,
        }

        return health
