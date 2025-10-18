"""
Enhanced Security Exceptions

Comprehensive exception classes for security operations with detailed error information,
audit logging hooks, and proper error handling for all security scenarios.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SecurityErrorType(Enum):
    """Types of security errors for categorization and handling."""
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_DENIED = "authorization_denied"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    TOKEN_MALFORMED = "token_malformed"
    PERMISSION_DENIED = "permission_denied"
    ROLE_REQUIRED = "role_required"
    RESOURCE_ACCESS_DENIED = "resource_access_denied"
    POLICY_EVALUATION_FAILED = "policy_evaluation_failed"
    AUDIT_LOG_FAILED = "audit_log_failed"
    CONFIGURATION_ERROR = "configuration_error"
    EXTERNAL_PROVIDER_ERROR = "external_provider_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    ACCOUNT_LOCKED = "account_locked"
    CLAIMS_VERIFICATION_FAILED = "claims_verification_failed"


class SecurityError(Exception):
    """Base security exception with audit logging and detailed context."""

    def __init__(
        self,
        message: str,
        error_type: SecurityErrorType,
        context: dict[str, Any] | None = None,
        audit_log: bool = True,
        severity: str = "medium"
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)
        self.severity = severity

        # Add security context if available
        self.context.update({
            "error_type": error_type.value,
            "timestamp": self.timestamp.isoformat(),
            "severity": severity
        })

        if audit_log:
            self._audit_security_error()

    def _audit_security_error(self):
        """Log security error for audit purposes."""
        try:
            audit_data = {
                "event_type": "security_error",
                "error_type": self.error_type.value,
                "message": self.message,
                "context": self.context,
                "timestamp": self.timestamp.isoformat(),
                "severity": self.severity
            }

            # Use appropriate logging level based on severity
            if self.severity == "critical":
                logger.critical(f"Security Error: {self.message}", extra=audit_data)
            elif self.severity == "high":
                logger.error(f"Security Error: {self.message}", extra=audit_data)
            elif self.severity == "medium":
                logger.warning(f"Security Error: {self.message}", extra=audit_data)
            else:
                logger.info(f"Security Error: {self.message}", extra=audit_data)

        except Exception as e:
            # Never let audit logging break the security flow
            logger.error(f"Failed to audit security error: {e}")

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_type.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context
        }


class AuthenticationError(SecurityError):
    """Authentication-related security errors."""

    def __init__(
        self,
        message: str,
        auth_method: str | None = None,
        principal_id: str | None = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if auth_method:
            context["auth_method"] = auth_method
        if principal_id:
            context["principal_id"] = principal_id

        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.AUTHENTICATION_FAILED)
        kwargs.setdefault("severity", "high")

        super().__init__(message, **kwargs)


class AuthorizationError(SecurityError):
    """Authorization-related security errors."""

    def __init__(
        self,
        message: str,
        resource: str | None = None,
        action: str | None = None,
        required_permissions: list | None = None,
        required_roles: list | None = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if resource:
            context["resource"] = resource
        if action:
            context["action"] = action
        if required_permissions:
            context["required_permissions"] = required_permissions
        if required_roles:
            context["required_roles"] = required_roles

        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.AUTHORIZATION_DENIED)
        kwargs.setdefault("severity", "medium")

        super().__init__(message, **kwargs)


class TokenError(SecurityError):
    """Token-related security errors with detailed token information."""

    def __init__(
        self,
        message: str,
        token_type: str | None = None,
        expiry_time: datetime | None = None,
        issuer: str | None = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if token_type:
            context["token_type"] = token_type
        if expiry_time:
            context["expiry_time"] = expiry_time.isoformat()
        if issuer:
            context["issuer"] = issuer

        kwargs["context"] = context
        kwargs.setdefault("severity", "medium")

        super().__init__(message, **kwargs)


class TokenExpiredError(TokenError):
    """Token has expired."""

    def __init__(self, message: str = "Token has expired", **kwargs):
        kwargs.setdefault("error_type", SecurityErrorType.TOKEN_EXPIRED)
        super().__init__(message, **kwargs)


class TokenInvalidError(TokenError):
    """Token is invalid or cannot be verified."""

    def __init__(self, message: str = "Token is invalid", **kwargs):
        kwargs.setdefault("error_type", SecurityErrorType.TOKEN_INVALID)
        super().__init__(message, **kwargs)


class TokenMalformedError(TokenError):
    """Token is malformed or corrupted."""

    def __init__(self, message: str = "Token is malformed", **kwargs):
        kwargs.setdefault("error_type", SecurityErrorType.TOKEN_MALFORMED)
        kwargs.setdefault("severity", "high")
        super().__init__(message, **kwargs)


class PermissionDeniedError(AuthorizationError):
    """Specific permission is required but not granted."""

    def __init__(self, message: str, permission: str, **kwargs):
        context = kwargs.get("context", {})
        context["denied_permission"] = permission
        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.PERMISSION_DENIED)

        super().__init__(message, **kwargs)


class RoleRequiredError(AuthorizationError):
    """Specific role is required but not assigned."""

    def __init__(self, message: str, required_role: str, **kwargs):
        context = kwargs.get("context", {})
        context["required_role"] = required_role
        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.ROLE_REQUIRED)

        super().__init__(message, **kwargs)


class PolicyEvaluationError(SecurityError):
    """Policy evaluation failed due to engine or configuration issues."""

    def __init__(
        self,
        message: str,
        policy_id: str | None = None,
        engine_type: str | None = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if policy_id:
            context["policy_id"] = policy_id
        if engine_type:
            context["engine_type"] = engine_type

        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.POLICY_EVALUATION_FAILED)
        kwargs.setdefault("severity", "high")

        super().__init__(message, **kwargs)


class RateLimitExceededError(SecurityError):
    """Rate limit has been exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: int | None = None,
        reset_time: datetime | None = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if limit:
            context["limit"] = limit
        if reset_time:
            context["reset_time"] = reset_time.isoformat()

        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.RATE_LIMIT_EXCEEDED)
        kwargs.setdefault("severity", "medium")

        super().__init__(message, **kwargs)


class AccountLockedError(AuthenticationError):
    """User account is locked due to security policy."""

    def __init__(
        self,
        message: str = "Account is locked",
        unlock_time: datetime | None = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if unlock_time:
            context["unlock_time"] = unlock_time.isoformat()

        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.ACCOUNT_LOCKED)
        kwargs.setdefault("severity", "high")

        super().__init__(message, **kwargs)


class ClaimsVerificationError(TokenError):
    """JWT claims verification failed."""

    def __init__(
        self,
        message: str,
        failed_claims: list | None = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if failed_claims:
            context["failed_claims"] = failed_claims

        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.CLAIMS_VERIFICATION_FAILED)
        kwargs.setdefault("severity", "high")

        super().__init__(message, **kwargs)


class ExternalProviderError(SecurityError):
    """External identity provider or service error."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        provider_error: str | None = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if provider:
            context["provider"] = provider
        if provider_error:
            context["provider_error"] = provider_error

        kwargs["context"] = context
        kwargs.setdefault("error_type", SecurityErrorType.EXTERNAL_PROVIDER_ERROR)
        kwargs.setdefault("severity", "high")

        super().__init__(message, **kwargs)


def handle_security_exception(func):
    """Decorator to handle security exceptions with proper logging and response formatting."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SecurityError:
            # Re-raise security errors as-is (already audited)
            raise
        except Exception as e:
            # Convert unexpected exceptions to security errors
            logger.exception(f"Unexpected error in security operation: {e}")
            raise SecurityError(
                message=f"Internal security error: {str(e)}",
                error_type=SecurityErrorType.CONFIGURATION_ERROR,
                context={"original_error": str(e)},
                severity="critical"
            )
    return wrapper


# Convenience functions for common security checks
def require_authentication(principal_id: str | None = None):
    """Raise AuthenticationError if not authenticated."""
    if not principal_id:
        raise AuthenticationError("Authentication required")


def require_permission(has_permission: bool, permission: str, resource: str | None = None):
    """Raise PermissionDeniedError if permission check fails."""
    if not has_permission:
        message = f"Permission '{permission}' required"
        if resource:
            message += f" for resource '{resource}'"
        raise PermissionDeniedError(message, permission=permission, resource=resource)


def require_role(has_role: bool, role: str):
    """Raise RoleRequiredError if role check fails."""
    if not has_role:
        raise RoleRequiredError(f"Role '{role}' required", required_role=role)


__all__ = [
    "SecurityError",
    "SecurityErrorType",
    "AuthenticationError",
    "AuthorizationError",
    "TokenError",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenMalformedError",
    "PermissionDeniedError",
    "RoleRequiredError",
    "PolicyEvaluationError",
    "RateLimitExceededError",
    "AccountLockedError",
    "ClaimsVerificationError",
    "ExternalProviderError",
    "handle_security_exception",
    "require_authentication",
    "require_permission",
    "require_role"
]
