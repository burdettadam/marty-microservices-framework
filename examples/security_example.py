"""
Example demonstrating how to use the Enterprise Security Framework.

This example shows:
1. Setting up security configuration
2. Creating a FastAPI app with security middleware
3. Protecting endpoints with authentication and authorization
4. Setting up rate limiting
5. Using different authentication methods
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from framework.security import (
    APIKeyConfig,
    AuthenticatedUser,
    FastAPISecurityMiddleware,
    JWTConfig,
    RateLimitConfig,
    SecurityConfig,
    SecurityLevel,
    get_current_user,
    initialize_rate_limiter,
    require_authentication,
    require_permission_dependency,
    require_role_dependency,
)

# Import the security framework


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Enterprise Security Example")
    yield
    logger.info("Shutting down Enterprise Security Example")


def create_security_config() -> SecurityConfig:
    """Create a comprehensive security configuration."""

    # JWT Configuration
    jwt_config = JWTConfig(
        secret_key="your-super-secret-jwt-key-change-in-production",
        algorithm="HS256",
        access_token_expire_minutes=30,
        issuer="marty-microservices",
        audience="api-users",
    )

    # API Key Configuration
    api_key_config = APIKeyConfig(
        header_name="X-API-Key",
        allow_header=True,
        allow_query_param=False,
        valid_keys=["demo-api-key-1", "demo-api-key-2"],
    )

    # Rate Limiting Configuration
    rate_limit_config = RateLimitConfig(
        enabled=True,
        default_rate="100/minute",
        use_memory_backend=True,  # Use Redis in production
        per_endpoint_limits={"/api/sensitive": "10/minute", "/api/admin": "5/minute"},
        per_user_limits={"admin_user": "1000/minute"},
    )

    # Main Security Configuration
    security_config = SecurityConfig(
        security_level=SecurityLevel.HIGH,
        service_name="security-example",
        jwt_config=jwt_config,
        api_key_config=api_key_config,
        rate_limit_config=rate_limit_config,
        enable_jwt=True,
        enable_api_keys=True,
        enable_rate_limiting=True,
        enable_request_logging=True,
        audit_enabled=True,
    )

    return security_config


def create_app() -> FastAPI:
    """Create FastAPI application with security."""

    # Create security configuration
    security_config = create_security_config()

    # Initialize rate limiter
    initialize_rate_limiter(security_config.rate_limit_config)

    # Create FastAPI app
    app = FastAPI(
        title="Enterprise Security Example",
        description="Demonstration of the Enterprise Security Framework",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add security middleware
    app.add_middleware(FastAPISecurityMiddleware, config=security_config)

    return app


# Create the app
app = create_app()


# Public endpoints (no authentication required)
@app.get("/")
async def root():
    """Public endpoint."""
    return {"message": "Enterprise Security Framework Example", "status": "public"}


@app.get("/health")
async def health_check():
    """Health check endpoint (automatically excluded from security by middleware)."""
    return {"status": "healthy"}


# Authentication endpoints
@app.post("/auth/login")
async def login(username: str, password: str):
    """Login endpoint that returns a JWT token."""
    # In a real application, you would validate credentials against a database
    if username == "demo" and password == "password":
        from framework.security import JWTAuthenticator

        # Get security config and create authenticator
        security_config = create_security_config()
        jwt_auth = JWTAuthenticator(security_config)

        # Create authentication result
        result = await jwt_auth.authenticate(
            {"username": username, "password": password}
        )

        if result.success:
            return {
                "access_token": result.metadata["access_token"],
                "token_type": "bearer",
                "user": {
                    "username": result.user.username,
                    "roles": result.user.roles,
                    "permissions": result.user.permissions,
                },
            }

    raise HTTPException(status_code=401, detail="Invalid credentials")


# Protected endpoints
@app.get("/api/protected")
async def protected_endpoint(user: AuthenticatedUser = Depends(require_authentication)):
    """Endpoint that requires authentication."""
    return {
        "message": "This is a protected endpoint",
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "auth_method": user.auth_method,
            "roles": user.roles,
        },
    }


@app.get("/api/admin")
async def admin_endpoint(
    user: AuthenticatedUser = Depends(require_role_dependency("admin")),
):
    """Endpoint that requires admin role."""
    return {
        "message": "This is an admin-only endpoint",
        "user": user.username,
        "admin_data": "sensitive admin information",
    }


@app.get("/api/sensitive")
async def sensitive_endpoint(
    user: AuthenticatedUser = Depends(require_permission_dependency("api:write")),
):
    """Endpoint that requires specific permission and has stricter rate limiting."""
    return {
        "message": "This is a sensitive endpoint with rate limiting",
        "user": user.username,
        "sensitive_data": "classified information",
    }


@app.get("/api/user-info")
async def get_user_info(current_user: AuthenticatedUser = Depends(get_current_user)):
    """Endpoint that shows current user info (optional authentication)."""
    if current_user:
        return {
            "authenticated": True,
            "user": {
                "user_id": current_user.user_id,
                "username": current_user.username,
                "roles": current_user.roles,
                "permissions": current_user.permissions,
                "auth_method": current_user.auth_method,
            },
        }
    return {"authenticated": False, "message": "No authentication provided"}


# API Key protected endpoint
@app.get("/api/service")
async def service_endpoint(user: AuthenticatedUser = Depends(require_authentication)):
    """Endpoint that can be accessed with API keys."""
    if user.auth_method == "api_key":
        return {
            "message": "Service endpoint accessed with API key",
            "service_user": user.user_id,
            "permissions": user.permissions,
        }
    return {
        "message": "Service endpoint accessed with other auth method",
        "user": user.username,
        "auth_method": user.auth_method,
    }


# Role management endpoints
@app.post("/api/admin/assign-role")
async def assign_role(
    username: str,
    role: str,
    admin_user: AuthenticatedUser = Depends(require_role_dependency("admin")),
):
    """Admin endpoint to assign roles to users."""
    from framework.security import get_rbac

    rbac = get_rbac()

    # In a real application, you would look up the user and assign the role
    # For this demo, we'll just return a success message
    return {
        "message": f"Role '{role}' assigned to user '{username}'",
        "assigned_by": admin_user.username,
        "available_roles": list(rbac.roles.keys()),
    }


@app.get("/api/permissions")
async def list_permissions(user: AuthenticatedUser = Depends(require_authentication)):
    """Get user's permissions and available permissions."""
    from framework.security import get_rbac

    rbac = get_rbac()
    user_permissions = rbac.get_user_permissions(user)

    return {
        "user_permissions": list(user_permissions),
        "available_permissions": list(rbac.permissions.keys()),
        "user_roles": user.roles,
        "available_roles": list(rbac.roles.keys()),
    }


# Error handler for security errors
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with proper security context."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url),
        },
    )


if __name__ == "__main__":
    import uvicorn

    print("🔐 Starting Enterprise Security Framework Example")
    print("\n📋 Available endpoints:")
    print("  • GET  /                    - Public endpoint")
    print("  • GET  /health              - Health check")
    print("  • POST /auth/login          - Login (username=demo, password=password)")
    print("  • GET  /api/protected       - Requires authentication")
    print("  • GET  /api/admin           - Requires admin role")
    print("  • GET  /api/sensitive       - Requires permission + rate limited")
    print("  • GET  /api/user-info       - Optional authentication")
    print("  • GET  /api/service         - API key or JWT")
    print("  • GET  /api/permissions     - List permissions")
    print("  • POST /api/admin/assign-role - Admin role management")

    print("\n🔑 Test credentials:")
    print("  • JWT: POST /auth/login with username=demo, password=password")
    print("  • API Key: X-API-Key: demo-api-key-1")

    print("\n🚀 Starting server on http://localhost:8000")
    print("📖 API docs available at http://localhost:8000/docs")

    uvicorn.run(
        "security_example:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
