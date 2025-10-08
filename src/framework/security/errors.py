"""
Security error classes for the enterprise security framework.
"""

from typing import Any, Dict, Optional


class SecurityError(Exception):
    """Base security error."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "SECURITY_ERROR"
        self.details = details or {}


class AuthenticationError(SecurityError):
    """Authentication failed."""

    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: str = "AUTH_FAILED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)


class AuthorizationError(SecurityError):
    """Authorization failed."""

    def __init__(
        self,
        message: str = "Access denied",
        error_code: str = "ACCESS_DENIED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)


class RateLimitExceededError(SecurityError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        error_code: str = "RATE_LIMIT_EXCEEDED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)
        self.retry_after = retry_after


class InvalidTokenError(AuthenticationError):
    """Invalid or expired token."""

    def __init__(
        self,
        message: str = "Invalid token",
        error_code: str = "INVALID_TOKEN",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)


class CertificateValidationError(AuthenticationError):
    """Certificate validation failed."""

    def __init__(
        self,
        message: str = "Certificate validation failed",
        error_code: str = "CERT_VALIDATION_FAILED",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details)


class InsufficientPermissionsError(AuthorizationError):
    """User lacks required permissions."""

    def __init__(
        self,
        required_permission: str,
        message: Optional[str] = None,
        error_code: str = "INSUFFICIENT_PERMISSIONS",
        details: Optional[Dict[str, Any]] = None,
    ):
        message = message or f"Required permission: {required_permission}"
        details = details or {"required_permission": required_permission}
        super().__init__(message, error_code, details)
