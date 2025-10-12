"""
Enterprise Security Framework for Marty Microservices

This module provides comprehensive security capabilities including:
- Multi-factor authentication (mTLS, JWT, API Keys)
- Advanced rate limiting with Redis backend
- Role-based access control (RBAC)
- Security audit logging
- gRPC security interceptors
- FastAPI security middleware
- Cryptography management with key rotation
- Secrets management with audit trails
- Security vulnerability scanning
- Comprehensive security hardening framework

Based on enterprise patterns from the main Marty project.
"""

# Legacy security components (for backward compatibility)
from .auth import (
    APIKeyAuthenticator,
    AuthenticatedUser,
    AuthenticationResult,
    BaseAuthenticator,
    JWTAuthenticator,
    MTLSAuthenticator,
)

# Component managers
from .authentication import AuthenticationManager
from .authorization import (
    AuthorizationManager,
    Permission,
    PermissionLevel,
    PolicyEngine,
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
from .cryptography import CryptographyManager
from .errors import (
    AuthenticationError,
    AuthorizationError,
    CertificateValidationError,
    InsufficientPermissionsError,
    InvalidTokenError,
    RateLimitExceededError,
    SecurityError,
)

# New comprehensive security framework components
from .framework import SecurityHardeningFramework, create_security_framework
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
from .models import AuthenticationMethod, ComplianceStandard, SecurityEvent
from .models import SecurityLevel as NewSecurityLevel
from .models import (
    SecurityPrincipal,
    SecurityThreatLevel,
    SecurityToken,
    SecurityVulnerability,
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
from .scanning import SecurityScanner
from .secrets import SecretsManager

__all__ = [
    "APIKeyAuthenticator",
    "APIKeyConfig",
    "AuthenticatedUser",
    "AuthenticationError",
    "AuthenticationManager",
    "AuthenticationMethod",
    "AuthenticationResult",
    "AuthorizationError",
    "AuthorizationManager",
    "BaseAuthenticator",
    "CertificateValidationError",
    "ComplianceStandard",
    "CryptographyManager",
    "FastAPISecurityMiddleware",
    "GRPCSecurityInterceptor",
    "HTTPBearerOptional",
    "InsufficientPermissionsError",
    "InvalidTokenError",
    # Authentication
    "JWTAuthenticator",
    "JWTConfig",
    "MTLSAuthenticator",
    "MTLSConfig",
    "MemoryRateLimitBackend",
    "NewSecurityLevel",
    "Permission",
    "PermissionLevel",
    "PolicyEngine",
    "RateLimitConfig",
    "RateLimitExceededError",
    "RateLimitRule",
    # Rate Limiting
    "RateLimiter",
    "RedisRateLimitBackend",
    "Role",
    # Authorization
    "RoleBasedAccessControl",
    # Configuration
    "SecurityConfig",
    # Errors
    "SecurityError",
    "SecurityEvent",
    "SecurityHardeningFramework",
    "SecurityLevel",
    # Middleware
    "SecurityMiddleware",
    "SecurityPrincipal",
    "SecurityScanner",
    "SecurityThreatLevel",
    "SecurityToken",
    "SecurityVulnerability",
    "SecretsManager",
    "create_security_framework",
    "get_current_user",
    "get_rate_limiter",
    "get_rbac",
    "has_permission",
    "has_role",
    "initialize_rate_limiter",
    "rate_limit",
    "require_authentication",
    "require_permission",
    "require_permission_dependency",
    "require_role",
    "require_role_dependency",
]
