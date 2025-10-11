"""
Security framework for the Marty Chassis.

This module provides:
- JWT authentication and authorization
- RBAC (Role-Based Access Control)
- API key authentication
- Security middleware for FastAPI and gRPC
- Rate limiting and security headers
"""

import time
from datetime import datetime, timedelta
from typing import Any, Optional, Union

import jwt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel

from ..config import SecurityConfig
from ..exceptions import AuthenticationError, AuthorizationError
from ..logger import get_logger

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(BaseModel):
    """User model for authentication."""

    id: str
    username: str
    email: str
    roles: list[str] = []
    permissions: list[str] = []
    is_active: bool = True
    created_at: datetime
    last_login: datetime | None = None


class TokenData(BaseModel):
    """Token data model."""

    sub: str  # subject (user id)
    username: str
    roles: list[str] = []
    permissions: list[str] = []
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp
    jti: str  # JWT ID


class JWTAuth:
    """JWT authentication handler."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.algorithm = config.jwt_algorithm
        self.secret_key = config.jwt_secret_key
        self.expiration_minutes = config.jwt_expiration_minutes

    def create_access_token(
        self, user: User, expires_delta: timedelta | None = None
    ) -> str:
        """Create a JWT access token for a user."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.expiration_minutes)

        now = datetime.utcnow()
        jti = f"{user.id}_{int(now.timestamp())}"

        to_encode = {
            "sub": user.id,
            "username": user.username,
            "roles": user.roles,
            "permissions": user.permissions,
            "exp": expire,
            "iat": now,
            "jti": jti,
        }

        try:
            encoded_jwt = jwt.encode(
                to_encode, self.secret_key, algorithm=self.algorithm
            )
            logger.info("JWT token created", user_id=user.id, jti=jti)
            return encoded_jwt
        except Exception as e:
            logger.error("Failed to create JWT token", error=str(e), user_id=user.id)
            raise AuthenticationError(f"Failed to create token: {e}")

    def verify_token(self, token: str) -> TokenData:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            token_data = TokenData(
                sub=payload.get("sub"),
                username=payload.get("username"),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                exp=payload.get("exp"),
                iat=payload.get("iat"),
                jti=payload.get("jti"),
            )

            logger.debug("JWT token verified", jti=token_data.jti)
            return token_data

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired", token=token[:20] + "...")
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token", error=str(e), token=token[:20] + "...")
            raise AuthenticationError(f"Invalid token: {e}")

    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)


class APIKeyAuth:
    """API key authentication handler."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.header_name = config.api_key_header
        self.valid_keys: set[str] = set()

    def add_api_key(self, api_key: str) -> None:
        """Add a valid API key."""
        self.valid_keys.add(api_key)

    def remove_api_key(self, api_key: str) -> None:
        """Remove an API key."""
        self.valid_keys.discard(api_key)

    def verify_api_key(self, api_key: str) -> bool:
        """Verify an API key."""
        is_valid = api_key in self.valid_keys
        if not is_valid:
            logger.warning("Invalid API key used", api_key=api_key[:8] + "...")
        return is_valid


class RBACMiddleware:
    """Role-Based Access Control middleware."""

    def __init__(self):
        self.role_permissions: dict[str, set[str]] = {}
        self.resource_permissions: dict[str, set[str]] = {}

    def add_role(self, role: str, permissions: list[str]) -> None:
        """Add a role with its permissions."""
        self.role_permissions[role] = set(permissions)
        logger.info("Role added", role=role, permissions=permissions)

    def add_resource_permission(self, resource: str, permissions: list[str]) -> None:
        """Add permissions required for a resource."""
        self.resource_permissions[resource] = set(permissions)

    def has_permission(self, user_roles: list[str], required_permission: str) -> bool:
        """Check if user roles have the required permission."""
        user_permissions = set()
        for role in user_roles:
            if role in self.role_permissions:
                user_permissions.update(self.role_permissions[role])

        return required_permission in user_permissions

    def has_resource_access(self, user_roles: list[str], resource: str) -> bool:
        """Check if user has access to a resource."""
        if resource not in self.resource_permissions:
            return True  # No permissions required

        required_permissions = self.resource_permissions[resource]
        user_permissions = set()

        for role in user_roles:
            if role in self.role_permissions:
                user_permissions.update(self.role_permissions[role])

        return bool(required_permissions.intersection(user_permissions))


class SecurityMiddleware:
    """Security middleware for FastAPI applications."""

    def __init__(
        self,
        jwt_auth: JWTAuth,
        api_key_auth: APIKeyAuth | None = None,
        rbac: RBACMiddleware | None = None,
        rate_limiter: Optional["RateLimiter"] = None,
    ):
        self.jwt_auth = jwt_auth
        self.api_key_auth = api_key_auth
        self.rbac = rbac
        self.rate_limiter = rate_limiter
        self.bearer = HTTPBearer(auto_error=False)

    async def authenticate_request(self, request: Request) -> TokenData | None:
        """Authenticate a request using JWT or API key."""
        # Try JWT authentication first
        credentials: HTTPAuthorizationCredentials = await self.bearer(request)
        if credentials:
            try:
                token_data = self.jwt_auth.verify_token(credentials.credentials)
                return token_data
            except AuthenticationError:
                pass

        # Try API key authentication
        if self.api_key_auth:
            api_key = request.headers.get(self.api_key_auth.header_name)
            if api_key and self.api_key_auth.verify_api_key(api_key):
                # Create a minimal token data for API key auth
                return TokenData(
                    sub="api_key_user",
                    username="api_key",
                    roles=["api_user"],
                    permissions=["api_access"],
                    exp=int(time.time()) + 3600,  # 1 hour
                    iat=int(time.time()),
                    jti="api_key",
                )

        return None

    def require_authentication(self, token_data: TokenData | None) -> TokenData:
        """Require authentication, raise exception if not authenticated."""
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token_data

    def require_permission(self, token_data: TokenData, permission: str) -> None:
        """Require a specific permission."""
        if not self.rbac:
            return  # No RBAC configured

        if not self.rbac.has_permission(token_data.roles, permission):
            logger.warning(
                "Permission denied",
                user_id=token_data.sub,
                required_permission=permission,
                user_roles=token_data.roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )

    def require_role(self, token_data: TokenData, role: str) -> None:
        """Require a specific role."""
        if role not in token_data.roles:
            logger.warning(
                "Role required",
                user_id=token_data.sub,
                required_role=role,
                user_roles=token_data.roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required",
            )


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 100, window_seconds: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = {}

    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for the given identifier."""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time
                for req_time in self.requests[identifier]
                if req_time > window_start
            ]
        else:
            self.requests[identifier] = []

        # Check if limit exceeded
        if len(self.requests[identifier]) >= self.requests_per_minute:
            logger.warning("Rate limit exceeded", identifier=identifier)
            return False

        # Add current request
        self.requests[identifier].append(now)
        return True


# Dependency functions for FastAPI
def get_current_user(security_middleware: SecurityMiddleware):
    """FastAPI dependency to get current authenticated user."""

    async def _get_current_user(request: Request) -> TokenData:
        token_data = await security_middleware.authenticate_request(request)
        return security_middleware.require_authentication(token_data)

    return _get_current_user


def require_permission(permission: str, security_middleware: SecurityMiddleware):
    """FastAPI dependency to require a permission."""

    async def _require_permission(request: Request) -> None:
        token_data = await security_middleware.authenticate_request(request)
        token_data = security_middleware.require_authentication(token_data)
        security_middleware.require_permission(token_data, permission)

    return _require_permission


def require_role(role: str, security_middleware: SecurityMiddleware):
    """FastAPI dependency to require a role."""

    async def _require_role(request: Request) -> None:
        token_data = await security_middleware.authenticate_request(request)
        token_data = security_middleware.require_authentication(token_data)
        security_middleware.require_role(token_data, role)

    return _require_role
