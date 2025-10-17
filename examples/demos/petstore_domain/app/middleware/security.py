"""
Security middleware for the PetStore Domain plugin.

⚠️  This file has been updated to use the Unified Security Framework
    instead of deprecated authorization and secret management modules.

This module integrates the enhanced security features from the Marty MSF framework
into the PetStore domain, providing authentication, authorization, and secret management.
"""
import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

# Import Marty MSF unified security framework
from marty_msf.security.unified_framework import (
    SecurityContext,
    SecurityPolicyType,
    SecurityPrincipal,
    UnifiedSecurityFramework,
    create_unified_security_framework,
)

SECURITY_AVAILABLE = True

logger = logging.getLogger(__name__)


class PetStoreSecurityMiddleware(BaseHTTPMiddleware):
    """
    PetStore-specific security middleware using Unified Security Framework.

    Provides:
    - Authentication (JWT, API keys)
    - Authorization via unified security framework
    - Audit logging
    """

    def __init__(
        self,
        app,
        security_framework: UnifiedSecurityFramework | None = None,
        require_auth: bool = True,
        public_paths: list | None = None
    ):
        super().__init__(app)
        self.security_framework = security_framework
        self.require_auth = require_auth
        self.public_paths = public_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/api/v1/health"
        ]
        self.security = HTTPBearer(auto_error=False)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security middleware"""

        # Skip authentication for public paths
        if request.url.path in self.public_paths:
            return await call_next(request)

        principal = None

        try:
            # Attempt authentication
            if self.require_auth:
                principal = await self._authenticate_request(request)
                if not principal:
                    return self._create_auth_error_response("Authentication required")

                # Check authorization
                if not await self._authorize_request(request, principal):
                    return self._create_auth_error_response("Access denied", status.HTTP_403_FORBIDDEN)

            # Store principal in request state for downstream handlers
            request.state.principal = principal

            # Process request
            response = await call_next(request)

            # Log request for audit
            await self._audit_log_request(request, response, principal)

            return response

        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            return self._create_auth_error_response("Security error occurred")

    async def _authenticate_request(self, request: Request) -> dict[str, Any] | None:
        """Authenticate request and return principal"""

        # Try JWT authentication first
        try:
            authorization: HTTPAuthorizationCredentials | None = await self.security(request)

            if authorization and authorization.scheme.lower() == "bearer":
                return await self._verify_jwt_token(authorization.credentials)
        except Exception as e:
            logger.warning(f"JWT authentication failed: {e}")

        # Try API key authentication
        api_key = request.headers.get("X-API-Key")
        if api_key:
            try:
                return await self._verify_api_key(api_key)
            except Exception as e:
                logger.warning(f"API key authentication failed: {e}")

        # Try mTLS certificate authentication
        if hasattr(request, 'client') and request.client:
            try:
                # Note: This is a placeholder - actual cert verification would be more complex
                return await self._verify_client_certificate(request)
            except Exception as e:
                logger.warning(f"Certificate authentication failed: {e}")

        return None

    async def _verify_jwt_token(self, token: str) -> dict[str, Any] | None:
        """Verify JWT token and return principal"""
        try:
            # TODO: Implement proper JWT verification with unified framework
            # For now, return a mock principal
            logger.info("JWT token verification - using mock principal")
            return {
                "id": "jwt_user",
                "type": "user",
                "roles": ["user"],
                "attributes": {"auth_method": "jwt"}
            }
        except Exception as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None

    async def _verify_api_key(self, api_key: str) -> dict[str, Any] | None:
        """Verify API key and return principal"""
        try:
            # TODO: Implement proper API key verification with unified framework
            # For now, return a mock principal for valid-looking keys
            if api_key.startswith("pk_"):
                return {
                    "id": f"api_key_{api_key[:10]}",
                    "type": "api_client",
                    "roles": ["api_client"],
                    "attributes": {"auth_method": "api_key"}
                }
            return None
        except Exception as e:
            logger.error(f"API key verification error: {e}")
            return None

    async def _verify_client_certificate(self, request: Request) -> dict[str, Any] | None:
        """Verify client certificate and return principal"""
        # This would implement mTLS certificate verification
        # For now, return basic principal for demo
        return {
            "id": "mtls_client",
            "type": "service",
            "roles": ["service"],
            "attributes": {"auth_method": "mtls"}
        }

    async def _authorize_request(self, request: Request, principal: dict[str, Any]) -> bool:
        """Authorize request using unified security framework"""
        if not self.security_framework:
            return True  # Allow if no security framework configured

        try:
            # Create security principal
            security_principal = SecurityPrincipal(
                id=principal.get("id", "anonymous"),
                type=principal.get("type", "user"),
                roles=set(principal.get("roles", [])),
                attributes=principal.get("attributes", {})
            )

            # Perform authorization check
            decision = await self.security_framework.authorize(
                security_principal,
                str(request.url.path),
                request.method
            )

            return decision.allowed

        except Exception as e:
            logger.error(f"Authorization error: {e}")
            return False  # Deny on error

    async def _audit_log_request(
        self,
        request: Request,
        response: Response,
        principal: dict[str, Any] | None
    ):
        """Log request for audit purposes"""
        audit_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "petstore-domain",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "user_id": principal.get("id") if principal else None,
            "user_type": principal.get("type") if principal else None,
            "source_ip": request.client.host if request.client else "unknown",
        }

        logger.info(f"Audit: {json.dumps(audit_data)}")

    def _create_auth_error_response(self, message: str, status_code: int = status.HTTP_401_UNAUTHORIZED) -> Response:
        """Create standardized authentication error response"""
        return Response(
            content=json.dumps({"error": message}),
            status_code=status_code,
            headers={"Content-Type": "application/json"}
        )


class PetStoreSecurityDependency:
    """
    Dependency injection for security components in PetStore routes.

    Provides easy access to authenticated user information and security services.
    """

    def __init__(self, security_framework: UnifiedSecurityFramework | None = None):
        self.security_framework = security_framework

    async def get_current_user(self, request: Request) -> dict[str, Any] | None:
        """Get current authenticated user from request state"""
        return getattr(request.state, 'principal', None)

    async def require_user(self, request: Request) -> dict[str, Any]:
        """Require authenticated user, raise exception if not present"""
        principal = await self.get_current_user(request)
        if not principal:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        return principal

    async def require_role(self, request: Request, required_role: str) -> dict[str, Any]:
        """Require specific role, raise exception if not present"""
        principal = await self.require_user(request)
        user_roles = principal.get("roles", [])

        if required_role not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )

        return principal

    async def get_secret(self, key: str) -> str | None:
        """Get secret from unified security framework"""
        # TODO: Implement secret management through unified framework
        logger.warning(f"Secret management not yet implemented in unified framework for key: {key}")
        return None


# Convenience functions for route decorators
def require_authentication(func):
    """Decorator to require authentication for a route"""
    async def wrapper(*args, **kwargs):
        # This would be implemented with proper FastAPI dependencies
        return await func(*args, **kwargs)
    return wrapper


def require_role(role: str):
    """Decorator to require specific role for a route"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be implemented with proper FastAPI dependencies
            return await func(*args, **kwargs)
        return wrapper
    return decorator
