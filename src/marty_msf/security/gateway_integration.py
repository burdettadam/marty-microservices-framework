"""
Enhanced API Gateway Security Integration

Integrates the enhanced security features into the API Gateway:
- HashiCorp Vault secret management
- Policy-based authorization with OPA/Oso
- Certificate management and mTLS
- Real-time policy evaluation
- Audit logging and compliance
"""

import builtins
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from marty_msf.framework.gateway.auth import (
    AuthenticationMiddleware,
    AuthorizationMiddleware,
)
from marty_msf.framework.gateway.core import GatewayRequest, GatewayResponse
from marty_msf.security.authorization import DecisionType, PolicyContext, PolicyManager
from marty_msf.security.secrets import SecretManager, VaultClient

logger = logging.getLogger(__name__)


class EnhancedSecurityMiddleware:
    """Enhanced security middleware for API Gateway with Vault and policy integration."""

    def __init__(
        self,
        secret_manager: SecretManager,
        policy_manager: PolicyManager,
        require_mtls: bool = False,
        audit_all_requests: bool = True
    ):
        """Initialize enhanced security middleware."""
        self.secret_manager = secret_manager
        self.policy_manager = policy_manager
        self.require_mtls = require_mtls
        self.audit_all_requests = audit_all_requests
        self.bearer_security = HTTPBearer(auto_error=False)

        # Metrics
        self.request_count = 0
        self.auth_failures = 0
        self.policy_denials = 0

    async def __call__(self, request: GatewayRequest, call_next) -> GatewayResponse:
        """Process request through enhanced security pipeline."""
        start_time = datetime.now(timezone.utc)
        self.request_count += 1

        try:
            # 1. Extract authentication information
            auth_result = await self._authenticate_request(request)
            if not auth_result["authenticated"]:
                self.auth_failures += 1
                if self.audit_all_requests:
                    await self._audit_request(request, "AUTH_FAILED", auth_result["reason"])

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=auth_result["reason"]
                )

            # 2. Build policy context
            policy_context = await self._build_policy_context(request, auth_result["principal"])

            # 3. Evaluate authorization policies
            policy_decision = await self.policy_manager.evaluate(policy_context)

            if policy_decision.decision == DecisionType.DENY:
                self.policy_denials += 1
                if self.audit_all_requests:
                    await self._audit_request(
                        request,
                        "AUTHZ_DENIED",
                        policy_decision.reason,
                        {"policy_decision": policy_decision}
                    )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: {policy_decision.reason}"
                )

            # 4. Add security context to request
            request.state.security_context = {
                "principal": auth_result["principal"],
                "policy_decision": policy_decision,
                "auth_method": auth_result.get("method"),
                "start_time": start_time
            }

            # 5. Process request
            response = await call_next(request)

            # 6. Audit successful request
            if self.audit_all_requests:
                processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                await self._audit_request(
                    request,
                    "SUCCESS",
                    "Request processed successfully",
                    {
                        "response_status": response.status_code,
                        "processing_time_ms": processing_time * 1000,
                        "policy_decision": policy_decision
                    }
                )

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            if self.audit_all_requests:
                await self._audit_request(request, "ERROR", str(e))

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal security error"
            )

    async def _authenticate_request(self, request: GatewayRequest) -> dict[str, Any]:
        """Authenticate request using multiple methods."""
        # Try mTLS first if required
        if self.require_mtls:
            mtls_result = await self._authenticate_mtls(request)
            if mtls_result["authenticated"]:
                return mtls_result

        # Try JWT/Bearer token
        bearer_result = await self._authenticate_bearer(request)
        if bearer_result["authenticated"]:
            return bearer_result

        # Try API key
        api_key_result = await self._authenticate_api_key(request)
        if api_key_result["authenticated"]:
            return api_key_result

        return {
            "authenticated": False,
            "reason": "No valid authentication method found",
            "principal": None
        }

    async def _authenticate_mtls(self, request: GatewayRequest) -> dict[str, Any]:
        """Authenticate using mutual TLS."""
        try:
            # Check for client certificate
            client_cert = getattr(request.state, "client_cert", None)
            if not client_cert:
                return {
                    "authenticated": False,
                    "reason": "No client certificate provided",
                    "principal": None
                }

            # Validate certificate (implementation depends on certificate format)
            # This is a simplified example
            principal = {
                "type": "service",
                "id": client_cert.get("subject", {}).get("CN", "unknown"),
                "certificate_fingerprint": client_cert.get("fingerprint"),
                "auth_method": "mtls"
            }

            return {
                "authenticated": True,
                "method": "mtls",
                "principal": principal
            }

        except Exception as e:
            logger.error(f"mTLS authentication error: {e}")
            return {
                "authenticated": False,
                "reason": f"mTLS authentication failed: {e}",
                "principal": None
            }

    async def _authenticate_bearer(self, request: GatewayRequest) -> dict[str, Any]:
        """Authenticate using JWT/Bearer token."""
        try:
            # Extract bearer token
            authorization = request.headers.get("authorization")
            if not authorization or not authorization.startswith("Bearer "):
                return {
                    "authenticated": False,
                    "reason": "No bearer token provided",
                    "principal": None
                }

            token = authorization.split(" ", 1)[1]

            # Get JWT secret from secret manager
            jwt_secret = await self.secret_manager.get_secret("jwt_secret")
            if not jwt_secret:
                logger.error("JWT secret not found in secret manager")
                return {
                    "authenticated": False,
                    "reason": "JWT validation unavailable",
                    "principal": None
                }

            # Validate JWT (simplified - would use proper JWT library)
            import jwt as pyjwt
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
            logger.error(f"JWT authentication error: {e}")
            return {
                "authenticated": False,
                "reason": f"JWT authentication failed: {e}",
                "principal": None
            }

    async def _authenticate_api_key(self, request: GatewayRequest) -> dict[str, Any]:
        """Authenticate using API key."""
        try:
            # Check headers for API key
            api_key = (
                request.headers.get("x-api-key") or
                request.headers.get("api-key") or
                request.query_params.get("api_key")
            )

            if not api_key:
                return {
                    "authenticated": False,
                    "reason": "No API key provided",
                    "principal": None
                }

            # Validate API key against stored keys
            # In production, this would hash the key and compare
            stored_key = await self.secret_manager.get_secret(f"api_key_{api_key[:8]}")
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
            logger.error(f"API key authentication error: {e}")
            return {
                "authenticated": False,
                "reason": f"API key authentication failed: {e}",
                "principal": None
            }

    async def _build_policy_context(self, request: GatewayRequest, principal: dict[str, Any]) -> PolicyContext:
        """Build context for policy evaluation."""
        # Extract resource and action from request
        resource = f"{request.method.upper()}:{request.url.path}"
        action = request.method.lower()

        # Build environment context
        environment = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "service": "api_gateway"
        }

        return PolicyContext(
            principal=principal,
            resource=resource,
            action=action,
            environment=environment
        )

    async def _audit_request(
        self,
        request: GatewayRequest,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None
    ):
        """Audit security-related request events."""
        audit_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
            "request": {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": dict(request.headers),
                "source_ip": request.client.host if request.client else "unknown"
            },
            "metadata": metadata or {}
        }

        # Log audit event (in production, this would go to a security audit system)
        logger.info(f"SECURITY_AUDIT: {audit_event}")

        # TODO: Send to external audit system (SIEM, etc.)

    async def get_metrics(self) -> dict[str, Any]:
        """Get security middleware metrics."""
        return {
            "total_requests": self.request_count,
            "auth_failures": self.auth_failures,
            "policy_denials": self.policy_denials,
            "auth_success_rate": (
                (self.request_count - self.auth_failures) / self.request_count
                if self.request_count > 0 else 0
            ),
            "authz_success_rate": (
                (self.request_count - self.policy_denials) / self.request_count
                if self.request_count > 0 else 0
            )
        }


class SecretRotationMiddleware:
    """Middleware for automatic secret rotation and certificate refresh."""

    def __init__(self, secret_manager: SecretManager, check_interval: int = 3600):
        """Initialize secret rotation middleware."""
        self.secret_manager = secret_manager
        self.check_interval = check_interval
        self.last_check = datetime.now(timezone.utc)

    async def __call__(self, request: GatewayRequest, call_next) -> GatewayResponse:
        """Check for secret rotation needs on each request."""
        now = datetime.now(timezone.utc)

        # Periodic check for secret rotation
        if (now - self.last_check).total_seconds() >= self.check_interval:
            await self._check_secret_rotation()
            self.last_check = now

        return await call_next(request)

    async def _check_secret_rotation(self):
        """Check and perform secret rotation if needed."""
        try:
            # Check for secrets needing rotation
            secrets_to_rotate = self.secret_manager.get_secrets_needing_rotation()

            for secret_key in secrets_to_rotate:
                logger.info(f"Rotating secret: {secret_key}")
                success = await self.secret_manager.rotate_secret(secret_key)
                if success:
                    logger.info(f"Successfully rotated secret: {secret_key}")
                else:
                    logger.error(f"Failed to rotate secret: {secret_key}")

            # Check for expired secrets
            expired_secrets = self.secret_manager.get_expired_secrets()
            for secret_key in expired_secrets:
                logger.warning(f"Secret expired: {secret_key}")
                # Could trigger alerts or automatic cleanup

        except Exception as e:
            logger.error(f"Error during secret rotation check: {e}")


# Factory functions for easy integration
async def create_enhanced_security_middleware(
    vault_config: dict[str, Any] | None = None,
    policy_engine: str = "builtin",
    require_mtls: bool = False
) -> EnhancedSecurityMiddleware:
    """Create enhanced security middleware with proper setup."""
    # Initialize Vault client if config provided
    vault_client = None
    if vault_config:
        from marty_msf.security.secrets import VaultClient, VaultConfig
        config = VaultConfig(**vault_config)
        vault_client = VaultClient(config)
        await vault_client.authenticate()

    # Initialize secret manager
    secret_manager = SecretManager(
        service_name="api_gateway",
        vault_client=vault_client
    )

    # Initialize policy manager
    from marty_msf.security.authorization import PolicyEngineEnum, PolicyManager

    engine_map = {
        "opa": PolicyEngineEnum.OPA,
        "oso": PolicyEngineEnum.OSO,
        "builtin": PolicyEngineEnum.BUILTIN
    }

    policy_manager = PolicyManager(primary_engine=engine_map.get(policy_engine, PolicyEngineEnum.BUILTIN))

    return EnhancedSecurityMiddleware(
        secret_manager=secret_manager,
        policy_manager=policy_manager,
        require_mtls=require_mtls
    )
