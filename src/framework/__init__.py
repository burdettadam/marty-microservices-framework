"""
Marty Microservices Framework

Enterprise-grade framework for building production-ready microservices with Python.
"""

from . import observability, security

__version__ = "1.0.0"

# Export main observability components
from .observability import (
    FrameworkMetrics,
    MetricsCollector,
    ServiceMonitor,
    create_async_grpc_metrics_interceptor,
    create_fastapi_metrics_middleware,
    create_grpc_metrics_interceptor,
    get_framework_metrics,
    get_tracer,
    init_observability,
    init_tracing,
    trace_function,
    traced_operation,
)

# Export main security components
from .security import (
    APIKeyAuthenticator,
    FastAPISecurityMiddleware,
    GRPCSecurityInterceptor,
    JWTAuthenticator,
    MTLSAuthenticator,
    RateLimiter,
    SecurityConfig,
    SecurityLevel,
    get_current_user,
    initialize_rate_limiter,
    require_authentication,
    require_permission,
    require_role,
)

__all__ = [
    "APIKeyAuthenticator",
    "FastAPISecurityMiddleware",
    "GRPCSecurityInterceptor",
    "FrameworkMetrics",
    "JWTAuthenticator",
    "MTLSAuthenticator",
    "MetricsCollector",
    "RateLimiter",
    "SecurityConfig",
    "SecurityLevel",
    "ServiceMonitor",
    "create_async_grpc_metrics_interceptor",
    "create_fastapi_metrics_middleware",
    "create_grpc_metrics_interceptor",
    "get_current_user",
    "get_framework_metrics",
    "get_tracer",
    "init_observability",
    "init_tracing",
    "initialize_rate_limiter",
    "observability",
    "require_authentication",
    "require_permission",
    "require_role",
    "security",
    "trace_function",
    "traced_operation",
]
