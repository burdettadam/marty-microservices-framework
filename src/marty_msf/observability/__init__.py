"""
Observability module for the Marty Microservices Framework.

This module provides observability features including:
- Metrics collection
- Distributed tracing
- Structured logging
- Monitoring and alerting
"""

import logging

logger = logging.getLogger(__name__)

# Core observability components are available in submodules
# Import specific components as needed:
# from marty_msf.observability.metrics import MetricsCollector
# from marty_msf.observability.tracing import TracingManager
# from marty_msf.observability.logging import StructuredLogger

# Common middleware exports
from .correlation_middleware import (
    CorrelationIdMiddleware,
    add_correlation_id_middleware,
)
from .metrics_middleware import MetricsMiddleware

__all__ = [
    "CorrelationIdMiddleware",
    "add_correlation_id_middleware",
    "MetricsMiddleware",
]
