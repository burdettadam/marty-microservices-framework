"""
Marty Microservices Framework

Enterprise-grade framework for building production-ready microservices with Python.
"""

from . import security

__version__ = "1.0.0"

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
    "JWTAuthenticator",
    "MTLSAuthenticator",
    "RateLimiter",
    "SecurityConfig",
    "SecurityLevel",
    "get_current_user",
    "initialize_rate_limiter",
    "require_authentication",
    "require_permission",
    "require_role",
    "security",
]
