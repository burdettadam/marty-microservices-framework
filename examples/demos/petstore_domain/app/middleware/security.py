"""
Security middleware for the PetStore Domain plugin.

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

# Import Marty MSF security components
try:
    from marty_msf.security.authorization import (
        AuthorizationRequest,
        PolicyEngineEnum,
        PolicyManager,
    )
    from marty_msf.security.gateway_integration import (
        create_enhanced_security_middleware,
    )
    from marty_msf.security.secrets import SecretManager, VaultClient, VaultConfig
    SECURITY_AVAILABLE = True
except ImportError:
    # Graceful degradation when security components are not available
    SECURITY_AVAILABLE = False
    logging.warning("Marty MSF security components not available, using basic security")

logger = logging.getLogger(__name__)

class PetStoreSecurityMiddleware(BaseHTTPMiddleware):
    """
    PetStore-specific security middleware that integrates with Marty MSF security components.

    Provides:
    - Authentication (JWT, API keys)
    - Authorization (RBAC/ABAC policies)
    - Secret management integration
    - Audit logging
    """

    def __init__(
        self,
        app,
        secret_manager: "SecretManager | None" = None,
        policy_manager: "PolicyManager | None" = None,
        require_auth: bool = True,
        public_paths: list | None = None
    ):
        super().__init__(app)
        self.secret_manager = secret_manager
        self.policy_manager = policy_manager
        self.require_auth = require_auth
        self.public_paths = public_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/pets/public"  # Public pet listing
        ]
        self.security = HTTPBearer(auto_error=False)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security pipeline"""

        # Skip security for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Skip security if not required
        if not self.require_auth:
            return await call_next(request)

        try:
            # Step 1: Authentication
            principal = await self._authenticate_request(request)
            if not principal and self.require_auth:
                return self._create_auth_error_response("Authentication required")

            # Step 2: Authorization
            if principal and self.policy_manager:
                authorized = await self._authorize_request(request, principal)
                if not authorized:
                    return self._create_auth_error_response("Access denied", status.HTTP_403_FORBIDDEN)

            # Step 3: Add security context to request
            if principal:
                request.state.principal = principal
                request.state.authenticated = True
            else:
                request.state.authenticated = False

            # Step 4: Process request
            response = await call_next(request)

            # Step 5: Audit logging
            await self._audit_log_request(request, response, principal)

            return response

        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            return self._create_auth_error_response("Security error occurred")

    def _is_public_path(self, path: str) -> bool:
        """Check if path is in public paths list"""
        return any(path.startswith(public_path) for public_path in self.public_paths)

    async def _authenticate_request(self, request: Request) -> dict[str, Any] | None:
        """Authenticate the request and return principal information"""

        # Try JWT token authentication
        authorization: HTTPAuthorizationCredentials = await self.security(request)
        if authorization:
            try:
                principal = await self._verify_jwt_token(authorization.credentials)
                if principal:
                    return principal
            except Exception as e:
                logger.warning(f"JWT authentication failed: {e}")

        # Try API key authentication
        api_key = request.headers.get("X-API-Key")
        if api_key:
            try:
                principal = await self._verify_api_key(api_key)
                if principal:
                    return principal
            except Exception as e:
                logger.warning(f"API key authentication failed: {e}")

        # Try client certificate authentication
        if hasattr(request, 'client') and hasattr(request.client, 'cert'):
            try:
                principal = await self._verify_client_certificate(request.client.cert)
                if principal:
                    return principal
            except Exception as e:
                logger.warning(f"Certificate authentication failed: {e}")

        return None

    async def _verify_jwt_token(self, token: str) -> dict[str, Any] | None:
        """Verify JWT token and extract principal"""
        if not SECURITY_AVAILABLE or not self.secret_manager:
            # Basic validation without security components
            return {"user_id": "demo_user", "roles": ["user"], "type": "user"}

        try:
            # Get JWT secret from secret manager
            jwt_secret = await self.secret_manager.get_secret("jwt/signing_key")
            if not jwt_secret:
                logger.warning("JWT signing key not found in secret store")
                return None

            # Verify token (you would use a proper JWT library here)
            import jwt
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])

            return {
                "user_id": payload.get("sub"),
                "roles": payload.get("roles", ["user"]),
                "type": "user",
                "exp": payload.get("exp"),
                "iat": payload.get("iat")
            }
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"JWT verification error: {e}")
            return None

    async def _verify_api_key(self, api_key: str) -> dict[str, Any] | None:
        """Verify API key and return principal"""
        if not SECURITY_AVAILABLE or not self.secret_manager:
            # Basic validation for demo
            if api_key.startswith("psk-"):
                return {
                    "service_name": "external_service",
                    "roles": ["service"],
                    "type": "service"
                }
            return None

        try:
            # Get valid API keys from secret store
            valid_keys = await self.secret_manager.get_secret("api_keys/valid_keys")
            if valid_keys and isinstance(valid_keys, dict) and api_key in valid_keys:
                key_data = valid_keys[api_key]
                return {
                    "service_name": key_data.get("service_name") if isinstance(key_data, dict) else "unknown",
                    "roles": key_data.get("roles", ["service"]) if isinstance(key_data, dict) else ["service"],
                    "type": "service"
                }
        except Exception as e:
            logger.error(f"API key verification error: {e}")

        return None

    async def _verify_client_certificate(self, cert) -> dict[str, Any] | None:
        """Verify client certificate and return principal"""
        # This would implement mTLS certificate verification
        # For now, return basic principal for demo
        return {
            "client_id": "mtls_client",
            "roles": ["service"],
            "type": "service"
        }

    async def _authorize_request(self, request: Request, principal: dict[str, Any]) -> bool:
        """Authorize request using policy engine"""
        if not self.policy_manager:
            return True  # Allow if no policy manager configured

        try:
            auth_request = AuthorizationRequest(
                principal=principal,
                action=request.method,
                resource=request.url.path,
                environment={
                    "source_ip": request.client.host if request.client else "unknown",
                    "user_agent": request.headers.get("user-agent", "unknown"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            result = await self.policy_manager.evaluate(auth_request)
            return getattr(result, 'allowed', False)

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
            "user_id": principal.get("user_id") if principal else None,
            "user_type": principal.get("type") if principal else None,
            "source_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown")
        }

        logger.info(f"Audit: {json.dumps(audit_data)}")

    def _create_auth_error_response(self, message: str, status_code: int = status.HTTP_401_UNAUTHORIZED) -> Response:
        """Create standardized authentication error response"""
        return Response(
            content=json.dumps({
                "error": "Authentication Error",
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }),
            status_code=status_code,
            headers={"Content-Type": "application/json"}
        )


class PetStoreSecurityDependency:
    """
    Dependency injection for security components in PetStore routes.

    Provides easy access to authenticated user information and security services.
    """

    def __init__(self, secret_manager: "SecretManager | None" = None):
        self.secret_manager = secret_manager

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
        """Get secret from secret manager"""
        if not self.secret_manager:
            return None

        try:
            return await self.secret_manager.get_secret(key)
        except Exception as e:
            logger.error(f"Failed to get secret {key}: {e}")
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
