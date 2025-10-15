"""
gRPC Security Interceptors for Marty Microservices Framework

Provides security interceptors for gRPC services with:
- Certificate-based authentication (mTLS)
- Policy-based authorization
- Secret management integration
- Audit logging and compliance
- Request context propagation
"""

import builtins
import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import grpc

from marty_msf.security.authorization import DecisionType, PolicyContext, PolicyManager
from marty_msf.security.secrets import SecretManager

logger = logging.getLogger(__name__)


class SecurityInterceptor(grpc.ServerInterceptor):
    """Base gRPC security interceptor."""

    def __init__(
        self,
        secret_manager: SecretManager,
        policy_manager: PolicyManager,
        require_mtls: bool = True,
        audit_all_requests: bool = True
    ):
        """Initialize security interceptor."""
        self.secret_manager = secret_manager
        self.policy_manager = policy_manager
        self.require_mtls = require_mtls
        self.audit_all_requests = audit_all_requests

        # Metrics
        self.request_count = 0
        self.auth_failures = 0
        self.authz_failures = 0


class AuthenticationInterceptor(SecurityInterceptor):
    """gRPC authentication interceptor."""

    def intercept_service(self, continuation: Callable, handler_call_details: grpc.HandlerCallDetails):
        """Intercept gRPC calls for authentication."""
        def authenticated_handler(request, context: grpc.ServicerContext):
            self.request_count += 1

            try:
                # Extract authentication information
                auth_result = self._authenticate_grpc_request(context)

                if not auth_result["authenticated"]:
                    self.auth_failures += 1
                    if self.audit_all_requests:
                        self._audit_grpc_request(
                            handler_call_details,
                            context,
                            "AUTH_FAILED",
                            auth_result["reason"]
                        )

                    context.abort(grpc.StatusCode.UNAUTHENTICATED, auth_result["reason"])
                    return

                # Add authentication context
                context.set_metadata("principal_id", auth_result["principal"]["id"])
                context.set_metadata("auth_method", auth_result["method"])

                # Store in context for authorization interceptor
                context._security_principal = auth_result["principal"]  # type: ignore
                context._auth_method = auth_result["method"]  # type: ignore

                # Continue to next handler
                return continuation(request, context)

            except Exception as e:
                logger.error(f"gRPC authentication error: {e}")
                if self.audit_all_requests:
                    self._audit_grpc_request(
                        handler_call_details,
                        context,
                        "ERROR",
                        f"Authentication error: {e}"
                    )

                context.abort(grpc.StatusCode.INTERNAL, "Authentication error")
                return

        return grpc.unary_unary_rpc_method_handler(authenticated_handler)

    def _authenticate_grpc_request(self, context: grpc.ServicerContext) -> dict[str, Any]:
        """Authenticate gRPC request."""
        # Get client certificate if mTLS is enabled
        if self.require_mtls:
            auth_context = context.auth_context()

            # Extract peer certificate
            peer_identities = auth_context.get("x509_common_name")
            if not peer_identities:
                return {
                    "authenticated": False,
                    "reason": "No client certificate provided",
                    "principal": None
                }

            common_name = peer_identities[0].decode("utf-8")

            # Extract certificate details
            cert_fingerprint = None
            peer_cert = auth_context.get("x509_subject_alternative_name")
            if peer_cert:
                # Simplified certificate processing
                cert_fingerprint = "sha256:" + hash(str(peer_cert))[:16]

            principal = {
                "type": "service",
                "id": common_name,
                "certificate_fingerprint": cert_fingerprint,
                "roles": ["service"],  # Default role for services
                "auth_method": "mtls"
            }

            return {
                "authenticated": True,
                "method": "mtls",
                "principal": principal
            }

        # Check for JWT in metadata
        metadata = dict(context.invocation_metadata())
        authorization = metadata.get("authorization")

        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ", 1)[1]
            return self._validate_jwt_token(token)

        # Check for API key
        api_key = metadata.get("x-api-key") or metadata.get("api-key")
        if api_key:
            return self._validate_api_key(api_key)

        return {
            "authenticated": False,
            "reason": "No valid authentication method found",
            "principal": None
        }

    def _validate_jwt_token(self, token: str) -> dict[str, Any]:
        """Validate JWT token."""
        try:
            import jwt as pyjwt

            # Get JWT secret from secret manager
            jwt_secret = asyncio.run(self.secret_manager.get_secret("jwt_secret"))
            if not jwt_secret:
                return {
                    "authenticated": False,
                    "reason": "JWT validation unavailable",
                    "principal": None
                }

            payload = pyjwt.decode(token, jwt_secret, algorithms=["HS256"])

            principal = {
                "type": "user",
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "roles": payload.get("roles", []),
                "scopes": payload.get("scopes", []),
                "auth_method": "jwt"
            }

            return {
                "authenticated": True,
                "method": "jwt",
                "principal": principal
            }

        except pyjwt.InvalidTokenError as e:
            return {
                "authenticated": False,
                "reason": f"Invalid JWT token: {e}",
                "principal": None
            }
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            return {
                "authenticated": False,
                "reason": f"JWT validation failed: {e}",
                "principal": None
            }

    def _validate_api_key(self, api_key: str) -> dict[str, Any]:
        """Validate API key."""
        try:
            # Validate API key against stored keys
            stored_key = asyncio.run(self.secret_manager.get_secret(f"api_key_{api_key[:8]}"))
            if not stored_key or stored_key != api_key:
                return {
                    "authenticated": False,
                    "reason": "Invalid API key",
                    "principal": None
                }

            # Get API key metadata
            key_metadata = self.secret_manager.get_secret_metadata(f"api_key_{api_key[:8]}")

            principal = {
                "type": "api_client",
                "id": f"api_key_{api_key[:8]}",
                "scopes": key_metadata.tags.get("scopes", []) if key_metadata else [],
                "auth_method": "api_key"
            }

            return {
                "authenticated": True,
                "method": "api_key",
                "principal": principal
            }

        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return {
                "authenticated": False,
                "reason": f"API key validation failed: {e}",
                "principal": None
            }

    def _audit_grpc_request(
        self,
        handler_call_details: grpc.HandlerCallDetails,
        context: grpc.ServicerContext,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None
    ):
        """Audit gRPC security events."""
        peer = context.peer()
        invocation_metadata = dict(context.invocation_metadata())

        audit_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
            "grpc_request": {
                "method": handler_call_details.method,
                "peer": peer,
                "metadata": invocation_metadata
            },
            "metadata": metadata or {}
        }

        logger.info(f"GRPC_SECURITY_AUDIT: {audit_event}")


class AuthorizationInterceptor(SecurityInterceptor):
    """gRPC authorization interceptor."""

    def intercept_service(self, continuation: Callable, handler_call_details: grpc.HandlerCallDetails):
        """Intercept gRPC calls for authorization."""
        def authorized_handler(request, context: grpc.ServicerContext):
            try:
                # Get principal from authentication interceptor
                principal = getattr(context, "_security_principal", None)
                if not principal:
                    self.authz_failures += 1
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "No authentication context")
                    return

                # Build policy context
                policy_context = self._build_grpc_policy_context(
                    handler_call_details,
                    context,
                    principal
                )

                # Evaluate authorization policy
                policy_decision = asyncio.run(self.policy_manager.evaluate(policy_context))

                if policy_decision.decision == DecisionType.DENY:
                    self.authz_failures += 1
                    if self.audit_all_requests:
                        self._audit_grpc_request(
                            handler_call_details,
                            context,
                            "AUTHZ_DENIED",
                            policy_decision.reason,
                            {"policy_decision": policy_decision}
                        )

                    context.abort(grpc.StatusCode.PERMISSION_DENIED, policy_decision.reason)
                    return

                # Add authorization context
                context.set_metadata("policy_decision", policy_decision.decision.value)
                context._policy_decision = policy_decision  # type: ignore

                # Audit successful authorization
                if self.audit_all_requests:
                    self._audit_grpc_request(
                        handler_call_details,
                        context,
                        "SUCCESS",
                        "Request authorized",
                        {"policy_decision": policy_decision}
                    )

                # Continue to next handler
                return continuation(request, context)

            except Exception as e:
                logger.error(f"gRPC authorization error: {e}")
                if self.audit_all_requests:
                    self._audit_grpc_request(
                        handler_call_details,
                        context,
                        "ERROR",
                        f"Authorization error: {e}"
                    )

                context.abort(grpc.StatusCode.INTERNAL, "Authorization error")
                return

        return grpc.unary_unary_rpc_method_handler(authorized_handler)

    def _build_grpc_policy_context(
        self,
        handler_call_details: grpc.HandlerCallDetails,
        context: grpc.ServicerContext,
        principal: dict[str, Any]
    ) -> PolicyContext:
        """Build policy context for gRPC request."""
        # Extract service and method from gRPC method name
        method_parts = handler_call_details.method.split("/")
        service = method_parts[1] if len(method_parts) > 1 else "unknown"
        method = method_parts[2] if len(method_parts) > 2 else "unknown"

        resource = f"grpc:{service}/{method}"
        action = "call"

        # Build environment context
        peer = context.peer()
        metadata = dict(context.invocation_metadata())

        environment = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "peer": peer,
            "service": service,
            "method": method,
            "protocol": "grpc",
            "metadata": metadata
        }

        return PolicyContext(
            principal=principal,
            resource=resource,
            action=action,
            environment=environment
        )

    def _audit_grpc_request(
        self,
        handler_call_details: grpc.HandlerCallDetails,
        context: grpc.ServicerContext,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None
    ):
        """Audit gRPC authorization events."""
        peer = context.peer()
        invocation_metadata = dict(context.invocation_metadata())

        audit_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
            "grpc_request": {
                "method": handler_call_details.method,
                "peer": peer,
                "metadata": invocation_metadata
            },
            "metadata": metadata or {}
        }

        logger.info(f"GRPC_AUTHZ_AUDIT: {audit_event}")


class SecretInjectionInterceptor(SecurityInterceptor):
    """Interceptor to inject secrets into gRPC service context."""

    def __init__(self, secret_manager: SecretManager, secrets_to_inject: list[str]):
        """Initialize secret injection interceptor."""
        super().__init__(secret_manager, None, False, False)
        self.secrets_to_inject = secrets_to_inject

    def intercept_service(self, continuation: Callable, handler_call_details: grpc.HandlerCallDetails):
        """Inject secrets into gRPC service context."""
        def secret_injected_handler(request, context: grpc.ServicerContext):
            # Inject configured secrets
            secrets = {}
            for secret_key in self.secrets_to_inject:
                secret_value = asyncio.run(self.secret_manager.get_secret(secret_key))
                if secret_value:
                    secrets[secret_key] = secret_value
                else:
                    logger.warning(f"Secret not found: {secret_key}")

            # Add secrets to context
            context._injected_secrets = secrets  # type: ignore

            return continuation(request, context)

        return grpc.unary_unary_rpc_method_handler(secret_injected_handler)


def create_security_interceptors(
    secret_manager: SecretManager,
    policy_manager: PolicyManager,
    require_mtls: bool = True,
    secrets_to_inject: list[str] | None = None
) -> list[grpc.ServerInterceptor]:
    """Create a chain of security interceptors for gRPC services."""
    interceptors = []

    # Authentication interceptor (always first)
    auth_interceptor = AuthenticationInterceptor(
        secret_manager=secret_manager,
        policy_manager=policy_manager,
        require_mtls=require_mtls
    )
    interceptors.append(auth_interceptor)

    # Authorization interceptor (after authentication)
    authz_interceptor = AuthorizationInterceptor(
        secret_manager=secret_manager,
        policy_manager=policy_manager
    )
    interceptors.append(authz_interceptor)

    # Secret injection interceptor (optional)
    if secrets_to_inject:
        secret_interceptor = SecretInjectionInterceptor(
            secret_manager=secret_manager,
            secrets_to_inject=secrets_to_inject
        )
        interceptors.append(secret_interceptor)

    return interceptors


# Helper function to get secrets from gRPC context
def get_secret_from_context(context: grpc.ServicerContext, secret_key: str) -> str | None:
    """Get injected secret from gRPC context."""
    secrets = getattr(context, "_injected_secrets", {})
    return secrets.get(secret_key)


# Helper function to get principal from gRPC context
def get_principal_from_context(context: grpc.ServicerContext) -> dict[str, Any] | None:
    """Get authenticated principal from gRPC context."""
    return getattr(context, "_security_principal", None)


# Helper function to get policy decision from gRPC context
def get_policy_decision_from_context(context: grpc.ServicerContext) -> Any:
    """Get policy decision from gRPC context."""
    return getattr(context, "_policy_decision", None)


# Add necessary import for asyncio
import asyncio
