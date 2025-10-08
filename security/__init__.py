"""
Marty Microservices Framework - Security Module

A comprehensive security framework providing enterprise-grade security capabilities
for microservices applications including authentication, rate limiting, security headers,
audit tools, and policy management.

Usage:
    from security import AuthenticationMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware

    # Add to FastAPI app
    app.add_middleware(SecurityHeadersMiddleware, config=security_config)
    app.add_middleware(RateLimitMiddleware, redis_url="redis://localhost:6379")
    app.add_middleware(AuthenticationMiddleware, jwt_secret_key=secret_key)

Requirements:
    Install security dependencies: pip install -r security/requirements.txt
"""

__version__ = "1.0.0"
__author__ = "Marty Microservices Framework"

# Import middleware components with graceful fallback
try:
    from .middleware.auth_middleware import (
        AuthenticationMiddleware,
        JWTAuthenticator,
        SecurityAuditor,
        SecurityConfig,
        get_current_user_dependency,
        require_roles,
    )

    _auth_available = True
except ImportError as e:
    _auth_available = False
    _auth_import_error = str(e)

try:
    from .middleware.rate_limiting import (
        RateLimitConfig,
        RateLimitMiddleware,
        RateLimitRule,
        SlidingWindowRateLimiter,
        rate_limit,
    )

    _rate_limit_available = True
except ImportError as e:
    _rate_limit_available = False
    _rate_limit_import_error = str(e)

try:
    from .middleware.security_headers import (
        SecurityHeadersConfig,
        SecurityHeadersMiddleware,
        create_security_headers_config,
    )

    _security_headers_available = True
except ImportError as e:
    _security_headers_available = False
    _security_headers_import_error = str(e)

# Create module attributes for discoverability
middleware = "security.middleware"
policies = "security.policies"
tools = "security.tools"
scanners = "security.scanners"


def get_availability_status():
    """Get the availability status of security components."""
    status = {
        "authentication": {
            "available": _auth_available,
            "error": _auth_import_error if not _auth_available else None,
        },
        "rate_limiting": {
            "available": _rate_limit_available,
            "error": _rate_limit_import_error if not _rate_limit_available else None,
        },
        "security_headers": {
            "available": _security_headers_available,
            "error": _security_headers_import_error
            if not _security_headers_available
            else None,
        },
    }
    return status


def check_dependencies():
    """Check if all required dependencies are installed."""
    status = get_availability_status()
    all_available = all(component["available"] for component in status.values())

    if not all_available:
        print(
            "⚠️ Some security components are not available due to missing dependencies:"
        )
        for name, info in status.items():
            if not info["available"]:
                print(f"❌ {name}: {info['error']}")
        print("\n💡 Install dependencies with: pip install -r security/requirements.txt")
    else:
        print("✅ All security components are available!")

    return all_available


# Make commonly used components available at package level when possible
__all__ = [
    # Core classes (available when dependencies are installed)
    "AuthenticationMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "SecurityConfig",
    "RateLimitConfig",
    "SecurityHeadersConfig",
    "JWTAuthenticator",
    "SecurityAuditor",
    "SlidingWindowRateLimiter",
    # Helper functions
    "require_roles",
    "get_current_user_dependency",
    "rate_limit",
    "create_security_headers_config",
    # Utility functions
    "get_availability_status",
    "check_dependencies",
    # Module info
    "__version__",
    "middleware",
    "policies",
    "tools",
    "scanners",
]

# Only add components to __all__ if they're actually importable
if not _auth_available:
    for item in [
        "AuthenticationMiddleware",
        "SecurityConfig",
        "JWTAuthenticator",
        "SecurityAuditor",
        "require_roles",
        "get_current_user_dependency",
    ]:
        if item in __all__:
            __all__.remove(item)

if not _rate_limit_available:
    for item in [
        "RateLimitMiddleware",
        "RateLimitConfig",
        "RateLimitRule",
        "SlidingWindowRateLimiter",
        "rate_limit",
    ]:
        if item in __all__:
            __all__.remove(item)

if not _security_headers_available:
    for item in [
        "SecurityHeadersMiddleware",
        "SecurityHeadersConfig",
        "create_security_headers_config",
    ]:
        if item in __all__:
            __all__.remove(item)

from .middleware.auth_middleware import (
    AuthenticationMiddleware,
    JWTAuthenticator,
    SecurityConfig,
    create_authentication_middleware,
    get_current_user_dependency,
    require_roles,
    setup_security_logging,
)
from .middleware.rate_limiting import (
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimitRule,
    SlidingWindowRateLimiter,
    create_rate_limit_config,
    create_rate_limit_middleware,
    get_rate_limit_info,
    rate_limit,
)
from .middleware.security_headers import (
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
    create_security_headers_config,
    create_security_headers_middleware,
    generate_csp_nonce,
    get_csp_nonce,
)

__all__ = [
    # Authentication
    "AuthenticationMiddleware",
    "JWTAuthenticator",
    "SecurityConfig",
    "require_roles",
    "get_current_user_dependency",
    "create_authentication_middleware",
    "setup_security_logging",
    # Rate Limiting
    "RateLimitMiddleware",
    "RateLimitConfig",
    "RateLimitRule",
    "SlidingWindowRateLimiter",
    "create_rate_limit_config",
    "create_rate_limit_middleware",
    "rate_limit",
    "get_rate_limit_info",
    # Security Headers
    "SecurityHeadersMiddleware",
    "SecurityHeadersConfig",
    "create_security_headers_config",
    "create_security_headers_middleware",
    "generate_csp_nonce",
    "get_csp_nonce",
]

__version__ = "1.0.0"
