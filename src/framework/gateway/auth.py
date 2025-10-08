"""
Authentication and Authorization Module for API Gateway

Comprehensive authentication and authorization system supporting multiple providers,
token validation, role-based access control, and sophisticated authorization policies.
"""

import base64
import hashlib
import hmac
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

import jwt

from .core import GatewayRequest, GatewayResponse

logger = logging.getLogger(__name__)


class AuthenticationType(Enum):
    """Authentication types."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    JWT = "jwt"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    CUSTOM = "custom"


class AuthorizationModel(Enum):
    """Authorization models."""

    NONE = "none"
    RBAC = "rbac"  # Role-Based Access Control
    ABAC = "abac"  # Attribute-Based Access Control
    ACL = "acl"  # Access Control List
    CUSTOM = "custom"


@dataclass
class Principal:
    """Authenticated principal (user, service, etc.)."""

    id: str
    type: str = "user"  # user, service, system
    name: Optional[str] = None
    email: Optional[str] = None
    roles: Set[str] = field(default_factory=set)
    permissions: Set[str] = field(default_factory=set)
    attributes: Dict[str, Any] = field(default_factory=dict)
    groups: Set[str] = field(default_factory=set)

    # Token information
    token_type: Optional[str] = None
    token_expires: Optional[float] = None
    token_scope: Set[str] = field(default_factory=set)

    # Authentication metadata
    auth_method: Optional[str] = None
    auth_time: Optional[float] = None
    issuer: Optional[str] = None


@dataclass
class AuthenticationConfig:
    """Configuration for authentication."""

    # Basic settings
    auth_type: AuthenticationType = AuthenticationType.NONE
    required: bool = True
    realm: str = "API Gateway"

    # JWT settings
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_audience: Optional[str] = None
    jwt_issuer: Optional[str] = None
    jwt_leeway: int = 10  # seconds

    # API Key settings
    api_key_header: str = "X-API-Key"
    api_key_query_param: str = "api_key"
    api_key_validator: Optional[Callable[[str], Optional[Principal]]] = None

    # OAuth2 settings
    oauth2_introspection_url: Optional[str] = None
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None

    # Basic auth settings
    basic_auth_validator: Optional[Callable[[str, str], Optional[Principal]]] = None

    # Custom authentication
    custom_authenticator: Optional[
        Callable[[GatewayRequest], Optional[Principal]]
    ] = None

    # Token caching
    cache_tokens: bool = True
    cache_duration: int = 300  # 5 minutes

    # Headers
    principal_header: str = "X-Principal-ID"
    roles_header: str = "X-Principal-Roles"


@dataclass
class AuthorizationConfig:
    """Configuration for authorization."""

    # Basic settings
    model: AuthorizationModel = AuthorizationModel.RBAC
    default_action: str = "deny"  # allow, deny

    # Role-based settings
    role_hierarchy: Dict[str, List[str]] = field(default_factory=dict)
    super_admin_roles: Set[str] = field(
        default_factory=lambda: {"admin", "super_admin"}
    )

    # Permission settings
    permission_separator: str = ":"
    wildcard_permissions: bool = True

    # Resource-based settings
    resource_patterns: Dict[str, str] = field(default_factory=dict)

    # Custom authorization
    custom_authorizer: Optional[Callable[[Principal, GatewayRequest], bool]] = None

    # Policy settings
    policy_evaluation_order: List[str] = field(
        default_factory=lambda: ["deny", "allow"]
    )
    combine_policies: str = (
        "first_applicable"  # first_applicable, permit_overrides, deny_overrides
    )


@dataclass
class AuthorizationRule:
    """Authorization rule definition."""

    name: str
    effect: str  # allow, deny
    actions: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class AuthenticationResult:
    """Result of authentication attempt."""

    success: bool
    principal: Optional[Principal] = None
    error: Optional[str] = None
    challenge: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorizationResult:
    """Result of authorization check."""

    allowed: bool
    reason: Optional[str] = None
    matched_rules: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Authenticator(ABC):
    """Abstract authenticator interface."""

    @abstractmethod
    def authenticate(self, request: GatewayRequest) -> AuthenticationResult:
        """Authenticate request and return principal."""
        raise NotImplementedError


class NoneAuthenticator(Authenticator):
    """No authentication (allow all)."""

    def authenticate(self, request: GatewayRequest) -> AuthenticationResult:
        """Always allow with anonymous principal."""
        principal = Principal(
            id="anonymous",
            type="anonymous",
            name="Anonymous User",
            auth_method="none",
            auth_time=time.time(),
        )

        return AuthenticationResult(success=True, principal=principal)


class ApiKeyAuthenticator(Authenticator):
    """API key authentication."""

    def __init__(self, config: AuthenticationConfig):
        self.config = config
        self.api_keys: Dict[str, Principal] = {}

    def add_api_key(self, api_key: str, principal: Principal):
        """Add API key for principal."""
        self.api_keys[api_key] = principal

    def authenticate(self, request: GatewayRequest) -> AuthenticationResult:
        """Authenticate using API key."""
        # Try header first
        api_key = request.get_header(self.config.api_key_header)

        # Try query parameter if not in header
        if not api_key:
            api_key = request.query_params.get(self.config.api_key_query_param)

        if not api_key:
            return AuthenticationResult(
                success=False,
                error="API key required",
                challenge=f'ApiKey realm="{self.config.realm}"',
            )

        # Validate API key
        if self.config.api_key_validator:
            principal = self.config.api_key_validator(api_key)
        else:
            principal = self.api_keys.get(api_key)

        if not principal:
            return AuthenticationResult(success=False, error="Invalid API key")

        # Set authentication metadata
        principal.auth_method = "api_key"
        principal.auth_time = time.time()

        return AuthenticationResult(success=True, principal=principal)


class JWTAuthenticator(Authenticator):
    """JWT token authentication."""

    def __init__(self, config: AuthenticationConfig):
        self.config = config
        self._token_cache: Dict[str, Tuple[Principal, float]] = {}

    def authenticate(self, request: GatewayRequest) -> AuthenticationResult:
        """Authenticate using JWT token."""
        # Extract token from Authorization header
        auth_header = request.get_header("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return AuthenticationResult(
                success=False,
                error="Bearer token required",
                challenge=f'Bearer realm="{self.config.realm}"',
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Check cache
        if self.config.cache_tokens and token in self._token_cache:
            principal, expires_at = self._token_cache[token]
            if time.time() < expires_at:
                return AuthenticationResult(success=True, principal=principal)
            else:
                # Remove expired token from cache
                del self._token_cache[token]

        try:
            # Decode and validate JWT
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
                audience=self.config.jwt_audience,
                issuer=self.config.jwt_issuer,
                leeway=self.config.jwt_leeway,
            )

            # Extract principal information
            principal = self._create_principal_from_jwt(payload)
            principal.auth_method = "jwt"
            principal.auth_time = time.time()

            # Cache token if configured
            if self.config.cache_tokens:
                cache_expires = time.time() + self.config.cache_duration
                self._token_cache[token] = (principal, cache_expires)

            return AuthenticationResult(success=True, principal=principal)

        except jwt.ExpiredSignatureError:
            return AuthenticationResult(success=False, error="Token expired")
        except jwt.InvalidTokenError as e:
            return AuthenticationResult(success=False, error=f"Invalid token: {str(e)}")

    def _create_principal_from_jwt(self, payload: Dict[str, Any]) -> Principal:
        """Create principal from JWT payload."""
        principal_id = payload.get("sub") or payload.get("user_id") or payload.get("id")
        if not principal_id:
            raise jwt.InvalidTokenError("Token missing subject/user_id")

        principal = Principal(
            id=str(principal_id),
            name=payload.get("name"),
            email=payload.get("email"),
            token_type="jwt",
            token_expires=payload.get("exp"),
            issuer=payload.get("iss"),
        )

        # Extract roles
        roles = payload.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]
        principal.roles = set(roles)

        # Extract permissions
        permissions = payload.get("permissions", [])
        if isinstance(permissions, str):
            permissions = [permissions]
        principal.permissions = set(permissions)

        # Extract scope
        scope = payload.get("scope", "")
        if isinstance(scope, str):
            principal.token_scope = set(scope.split())
        elif isinstance(scope, list):
            principal.token_scope = set(scope)

        # Extract groups
        groups = payload.get("groups", [])
        if isinstance(groups, str):
            groups = [groups]
        principal.groups = set(groups)

        # Store additional attributes
        for key, value in payload.items():
            if key not in [
                "sub",
                "user_id",
                "id",
                "name",
                "email",
                "roles",
                "permissions",
                "scope",
                "groups",
                "exp",
                "iat",
                "iss",
                "aud",
            ]:
                principal.attributes[key] = value

        return principal


class BasicAuthenticator(Authenticator):
    """HTTP Basic authentication."""

    def __init__(self, config: AuthenticationConfig):
        self.config = config

    def authenticate(self, request: GatewayRequest) -> AuthenticationResult:
        """Authenticate using Basic authentication."""
        auth_header = request.get_header("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return AuthenticationResult(
                success=False,
                error="Basic authentication required",
                challenge=f'Basic realm="{self.config.realm}"',
            )

        try:
            # Decode credentials
            encoded_credentials = auth_header[6:]  # Remove "Basic " prefix
            decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
            username, password = decoded_credentials.split(":", 1)

            # Validate credentials
            if self.config.basic_auth_validator:
                principal = self.config.basic_auth_validator(username, password)
                if principal:
                    principal.auth_method = "basic"
                    principal.auth_time = time.time()
                    return AuthenticationResult(success=True, principal=principal)

            return AuthenticationResult(success=False, error="Invalid credentials")

        except Exception as e:
            return AuthenticationResult(
                success=False, error=f"Authentication error: {str(e)}"
            )


class CustomAuthenticator(Authenticator):
    """Custom authentication using provided function."""

    def __init__(self, config: AuthenticationConfig):
        self.config = config

    def authenticate(self, request: GatewayRequest) -> AuthenticationResult:
        """Authenticate using custom function."""
        if not self.config.custom_authenticator:
            return AuthenticationResult(
                success=False, error="No custom authenticator configured"
            )

        try:
            principal = self.config.custom_authenticator(request)
            if principal:
                principal.auth_method = "custom"
                principal.auth_time = time.time()
                return AuthenticationResult(success=True, principal=principal)
            else:
                return AuthenticationResult(
                    success=False, error="Authentication failed"
                )
        except Exception as e:
            return AuthenticationResult(
                success=False, error=f"Authentication error: {str(e)}"
            )


class Authorizer(ABC):
    """Abstract authorizer interface."""

    @abstractmethod
    def authorize(
        self, principal: Principal, request: GatewayRequest
    ) -> AuthorizationResult:
        """Check if principal is authorized for request."""
        raise NotImplementedError


class RBACAuthorizer(Authorizer):
    """Role-Based Access Control authorizer."""

    def __init__(self, config: AuthorizationConfig):
        self.config = config
        self.rules: List[AuthorizationRule] = []

    def add_rule(self, rule: AuthorizationRule):
        """Add authorization rule."""
        self.rules.append(rule)
        # Sort rules by priority (higher priority first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def authorize(
        self, principal: Principal, request: GatewayRequest
    ) -> AuthorizationResult:
        """Authorize using RBAC rules."""
        # Check if super admin
        if principal.roles & self.config.super_admin_roles:
            return AuthorizationResult(
                allowed=True, reason="Super admin access", matched_rules=["super_admin"]
            )

        # Evaluate rules
        matched_rules = []
        final_decision = self.config.default_action == "allow"

        for rule in self.rules:
            if self._rule_matches(rule, principal, request):
                matched_rules.append(rule.name)

                if rule.effect == "allow":
                    if self.config.combine_policies == "first_applicable":
                        return AuthorizationResult(
                            allowed=True,
                            reason=f"Allowed by rule: {rule.name}",
                            matched_rules=matched_rules,
                        )
                    elif self.config.combine_policies == "permit_overrides":
                        final_decision = True
                        break

                elif rule.effect == "deny":
                    if self.config.combine_policies == "first_applicable":
                        return AuthorizationResult(
                            allowed=False,
                            reason=f"Denied by rule: {rule.name}",
                            matched_rules=matched_rules,
                        )
                    elif self.config.combine_policies == "deny_overrides":
                        final_decision = False
                        break

        return AuthorizationResult(
            allowed=final_decision,
            reason="Default policy"
            if not matched_rules
            else f"Combined rules: {matched_rules}",
            matched_rules=matched_rules,
        )

    def _rule_matches(
        self, rule: AuthorizationRule, principal: Principal, request: GatewayRequest
    ) -> bool:
        """Check if rule matches principal and request."""
        # Check roles
        if rule.roles and not (principal.roles & set(rule.roles)):
            return False

        # Check permissions
        if rule.permissions and not self._has_permissions(principal, rule.permissions):
            return False

        # Check actions (HTTP methods)
        if rule.actions and request.method.value.lower() not in [
            a.lower() for a in rule.actions
        ]:
            return False

        # Check resources (paths)
        if rule.resources and not self._matches_resources(request.path, rule.resources):
            return False

        # Check conditions
        for condition_key, condition_value in rule.conditions.items():
            if not self._evaluate_condition(
                condition_key, condition_value, principal, request
            ):
                return False

        return True

    def _has_permissions(
        self, principal: Principal, required_permissions: List[str]
    ) -> bool:
        """Check if principal has required permissions."""
        for required in required_permissions:
            if not self._has_permission(principal, required):
                return False
        return True

    def _has_permission(self, principal: Principal, required_permission: str) -> bool:
        """Check if principal has specific permission."""
        # Direct permission check
        if required_permission in principal.permissions:
            return True

        # Wildcard permission check
        if self.config.wildcard_permissions:
            permission_parts = required_permission.split(
                self.config.permission_separator
            )

            for granted in principal.permissions:
                if granted.endswith("*"):
                    granted_prefix = granted[:-1]
                    if required_permission.startswith(granted_prefix):
                        return True

                # Check hierarchical permissions
                granted_parts = granted.split(self.config.permission_separator)
                if len(granted_parts) <= len(permission_parts):
                    if granted_parts == permission_parts[: len(granted_parts)]:
                        return True

        return False

    def _matches_resources(self, path: str, resource_patterns: List[str]) -> bool:
        """Check if path matches any resource pattern."""
        for pattern in resource_patterns:
            if self._matches_resource_pattern(path, pattern):
                return True
        return False

    def _matches_resource_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches resource pattern."""
        # Exact match
        if pattern == path:
            return True

        # Wildcard match
        if "*" in pattern:
            # Convert wildcard pattern to regex
            regex_pattern = pattern.replace("*", ".*")
            if re.match(f"^{regex_pattern}$", path):
                return True

        # Prefix match
        if pattern.endswith("/") and path.startswith(pattern):
            return True

        return False

    def _evaluate_condition(
        self, key: str, value: Any, principal: Principal, request: GatewayRequest
    ) -> bool:
        """Evaluate authorization condition."""
        if key == "time_range":
            # Check if current time is within range
            current_time = time.time()
            start_time = value.get("start", 0)
            end_time = value.get("end", float("inf"))
            return start_time <= current_time <= end_time

        elif key == "ip_address":
            # Check if request IP is in allowed list
            ip = request.get_header("X-Forwarded-For") or request.get_header(
                "X-Real-IP"
            )
            return ip in value if isinstance(value, list) else ip == value

        elif key == "user_attribute":
            # Check user attribute
            attr_name = value.get("name")
            attr_value = value.get("value")
            return principal.attributes.get(attr_name) == attr_value

        elif key == "header":
            # Check request header
            header_name = value.get("name")
            header_value = value.get("value")
            return request.get_header(header_name) == header_value

        # Default: condition not met
        return False


class AuthenticationMiddleware:
    """Authentication middleware for API Gateway."""

    def __init__(self, config: AuthenticationConfig):
        self.config = config
        self.authenticator = self._create_authenticator()

    def _create_authenticator(self) -> Authenticator:
        """Create authenticator based on configuration."""
        auth_type_map = {
            AuthenticationType.NONE: NoneAuthenticator,
            AuthenticationType.API_KEY: ApiKeyAuthenticator,
            AuthenticationType.JWT: JWTAuthenticator,
            AuthenticationType.BASIC: BasicAuthenticator,
            AuthenticationType.CUSTOM: CustomAuthenticator,
        }

        authenticator_class = auth_type_map.get(self.config.auth_type)
        if not authenticator_class:
            raise ValueError(
                f"Unsupported authentication type: {self.config.auth_type}"
            )

        return authenticator_class(self.config)

    def process_request(self, request: GatewayRequest) -> Optional[GatewayResponse]:
        """Process request for authentication."""
        try:
            # Skip authentication if not required
            if (
                not self.config.required
                and self.config.auth_type == AuthenticationType.NONE
            ):
                request.context.principal = Principal(
                    id="anonymous", type="anonymous", auth_method="none"
                )
                return None

            # Authenticate request
            result = self.authenticator.authenticate(request)

            if result.success and result.principal:
                # Store principal in request context
                request.context.principal = result.principal

                # Add principal headers if configured
                if self.config.principal_header:
                    request.context.metadata.setdefault("auth_headers", {})[
                        self.config.principal_header
                    ] = result.principal.id

                if self.config.roles_header and result.principal.roles:
                    request.context.metadata.setdefault("auth_headers", {})[
                        self.config.roles_header
                    ] = ",".join(result.principal.roles)

                return None  # Continue processing

            else:
                # Authentication failed
                return self._create_auth_error_response(result)

        except Exception as e:
            logger.error(f"Error in authentication middleware: {e}")
            return self._create_auth_error_response(
                AuthenticationResult(success=False, error="Authentication error")
            )

    def _create_auth_error_response(
        self, result: AuthenticationResult
    ) -> GatewayResponse:
        """Create authentication error response."""
        from .core import GatewayResponse

        status_code = 401
        body = result.error or "Authentication required"

        response = GatewayResponse(
            status_code=status_code, body=body, content_type="text/plain"
        )

        if result.challenge:
            response.set_header("WWW-Authenticate", result.challenge)

        return response


class AuthorizationMiddleware:
    """Authorization middleware for API Gateway."""

    def __init__(self, config: AuthorizationConfig):
        self.config = config
        self.authorizer = self._create_authorizer()

    def _create_authorizer(self) -> Authorizer:
        """Create authorizer based on configuration."""
        if self.config.model == AuthorizationModel.RBAC:
            return RBACAuthorizer(self.config)
        else:
            raise ValueError(f"Unsupported authorization model: {self.config.model}")

    def add_rule(self, rule: AuthorizationRule):
        """Add authorization rule."""
        if hasattr(self.authorizer, "add_rule"):
            self.authorizer.add_rule(rule)

    def process_request(self, request: GatewayRequest) -> Optional[GatewayResponse]:
        """Process request for authorization."""
        try:
            # Skip authorization if no model
            if self.config.model == AuthorizationModel.NONE:
                return None

            # Get principal from request context
            principal = getattr(request.context, "principal", None)
            if not principal:
                logger.warning("No principal found for authorization check")
                return self._create_authz_error_response("No authenticated principal")

            # Custom authorization
            if self.config.custom_authorizer:
                try:
                    allowed = self.config.custom_authorizer(principal, request)
                    if not allowed:
                        return self._create_authz_error_response(
                            "Access denied by custom authorizer"
                        )
                    return None
                except Exception as e:
                    logger.error(f"Custom authorizer error: {e}")
                    return self._create_authz_error_response("Authorization error")

            # Standard authorization
            result = self.authorizer.authorize(principal, request)

            if result.allowed:
                # Store authorization metadata
                request.context.metadata["authorization"] = {
                    "allowed": True,
                    "matched_rules": result.matched_rules,
                    "reason": result.reason,
                }
                return None  # Continue processing
            else:
                return self._create_authz_error_response(
                    result.reason or "Access denied"
                )

        except Exception as e:
            logger.error(f"Error in authorization middleware: {e}")
            return self._create_authz_error_response("Authorization error")

    def _create_authz_error_response(self, reason: str) -> GatewayResponse:
        """Create authorization error response."""
        from .core import GatewayResponse

        return GatewayResponse(
            status_code=403, body=f"Forbidden: {reason}", content_type="text/plain"
        )


# Convenience functions
def create_jwt_auth(secret: str, algorithm: str = "HS256") -> AuthenticationMiddleware:
    """Create JWT authentication middleware."""
    config = AuthenticationConfig(
        auth_type=AuthenticationType.JWT, jwt_secret=secret, jwt_algorithm=algorithm
    )
    return AuthenticationMiddleware(config)


def create_api_key_auth(api_keys: Dict[str, Principal]) -> AuthenticationMiddleware:
    """Create API key authentication middleware."""
    config = AuthenticationConfig(auth_type=AuthenticationType.API_KEY)
    middleware = AuthenticationMiddleware(config)

    # Add API keys
    if isinstance(middleware.authenticator, ApiKeyAuthenticator):
        for key, principal in api_keys.items():
            middleware.authenticator.add_api_key(key, principal)

    return middleware


def create_rbac_authz() -> AuthorizationMiddleware:
    """Create RBAC authorization middleware."""
    config = AuthorizationConfig(model=AuthorizationModel.RBAC)
    return AuthorizationMiddleware(config)
