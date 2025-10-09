"""
Core exceptions for the Marty Chassis framework.

This module defines the exception hierarchy used throughout the chassis,
providing clear error types for different failure scenarios.
"""

from typing import Any, Dict, Optional


class ChassisError(Exception):
    """Base exception for all chassis-related errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary representation."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
        }


class ConfigurationError(ChassisError):
    """Raised when configuration is invalid or missing."""

    pass


class ValidationError(ChassisError):
    """Raised when data validation fails."""

    pass


class ServiceError(ChassisError):
    """Raised when service operations fail."""

    pass


class AuthenticationError(ChassisError):
    """Raised when authentication fails."""

    pass


class AuthorizationError(ChassisError):
    """Raised when authorization fails."""

    pass


class CircuitBreakerError(ChassisError):
    """Raised when circuit breaker is open."""

    pass


class ClientError(ChassisError):
    """Raised when client operations fail."""

    pass


class HealthCheckError(ChassisError):
    """Raised when health checks fail."""

    pass


class MetricsError(ChassisError):
    """Raised when metrics collection fails."""

    pass


class TemplateError(ChassisError):
    """Raised when template operations fail."""

    pass


class CLIError(ChassisError):
    """Raised when CLI operations fail."""

    pass
