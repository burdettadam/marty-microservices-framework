"""
Enterprise Security Framework for Marty Microservices

This module provides comprehensive security capabilities including:
- Multi-factor authentication (mTLS, JWT, API Keys)
- Advanced rate limiting with Redis backend
- Role-based access control (RBAC)
- Security audit logging
- gRPC security interceptors
- FastAPI security middleware

Based on enterprise patterns from the main Marty project.
"""

from .auth import (
    APIKeyAuthenticator,
    AuthenticatedUser,
    AuthenticationResult,
    BaseAuthenticator,
    JWTAuthenticator,
    MTLSAuthenticator,
)
from .authorization import (
    Permission,
    PermissionLevel,
    Role,
    RoleBasedAccessControl,
    get_rbac,
    has_permission,
    has_role,
    require_permission,
    require_role,
)
from .config import (
    APIKeyConfig,
    JWTConfig,
    MTLSConfig,
    RateLimitConfig,
    SecurityConfig,
    SecurityLevel,
)
from .errors import (
    AuthenticationError,
    AuthorizationError,
    CertificateValidationError,
    InsufficientPermissionsError,
    InvalidTokenError,
    RateLimitExceededError,
    SecurityError,
)
from .middleware import (
    FastAPISecurityMiddleware,
    GRPCSecurityInterceptor,
    HTTPBearerOptional,
    SecurityMiddleware,
    get_current_user,
    require_authentication,
    require_permission_dependency,
    require_role_dependency,
)
from .rate_limiting import (
    MemoryRateLimitBackend,
    RateLimiter,
    RateLimitRule,
    RedisRateLimitBackend,
    get_rate_limiter,
    initialize_rate_limiter,
    rate_limit,
)

__all__ = [
    # Errors
    "SecurityError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitExceededError",
    "InvalidTokenError",
    "CertificateValidationError",
    "InsufficientPermissionsError",
    # Configuration
    "SecurityConfig",
    "SecurityLevel",
    "JWTConfig",
    "MTLSConfig",
    "APIKeyConfig",
    "RateLimitConfig",
    # Authentication
    "JWTAuthenticator",
    "APIKeyAuthenticator",
    "MTLSAuthenticator",
    "AuthenticationResult",
    "AuthenticatedUser",
    "BaseAuthenticator",
    # Authorization
    "RoleBasedAccessControl",
    "Permission",
    "Role",
    "PermissionLevel",
    "require_permission",
    "require_role",
    "get_rbac",
    "has_permission",
    "has_role",
    # Rate Limiting
    "RateLimiter",
    "RateLimitRule",
    "MemoryRateLimitBackend",
    "RedisRateLimitBackend",
    "initialize_rate_limiter",
    "get_rate_limiter",
    "rate_limit",
    # Middleware
    "SecurityMiddleware",
    "FastAPISecurityMiddleware",
    "GRPCSecurityInterceptor",
    "HTTPBearerOptional",
    "get_current_user",
    "require_authentication",
    "require_permission_dependency",
    "require_role_dependency",
]
