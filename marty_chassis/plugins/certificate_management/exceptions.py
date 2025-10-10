"""
Exception classes for the Certificate Management Plugin.

This module defines custom exceptions used throughout the certificate
management system to provide clear error handling and debugging information.
"""

from typing import Any, Dict, List, Optional


class CertificateManagementError(Exception):
    """
    Base exception for all certificate management errors.

    This is the parent class for all certificate management specific
    exceptions and should be used for catching any certificate management
    related errors.
    """

    def __init__(self, message: str, error_code: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}

    def __str__(self):
        base_message = super().__str__()
        if self.error_code:
            return f"[{self.error_code}] {base_message}"
        return base_message


class CertificateNotFoundError(CertificateManagementError):
    """
    Raised when a requested certificate cannot be found.

    This exception is raised when attempting to retrieve, update, or
    perform operations on a certificate that doesn't exist in the
    specified store or CA.
    """

    def __init__(self, certificate_id: str, store_name: str = None, ca_name: str = None):
        location = store_name or ca_name or "unknown location"
        message = f"Certificate '{certificate_id}' not found in {location}"
        super().__init__(message, "CERT_NOT_FOUND", {
            "certificate_id": certificate_id,
            "store_name": store_name,
            "ca_name": ca_name
        })


class CertificateValidationError(CertificateManagementError):
    """
    Raised when certificate validation fails.

    This exception is raised when a certificate fails validation checks
    such as signature verification, chain validation, or policy compliance.
    """

    def __init__(self, message: str, validation_errors: list = None, certificate_serial: str = None):
        super().__init__(message, "CERT_VALIDATION_FAILED", {
            "validation_errors": validation_errors or [],
            "certificate_serial": certificate_serial
        })
        self.validation_errors = validation_errors or []
        self.certificate_serial = certificate_serial


class CertificateStoreError(CertificateManagementError):
    """
    Raised when certificate store operations fail.

    This exception is raised when operations on certificate storage
    backends fail, such as connection errors, authentication failures,
    or storage system errors.
    """

    def __init__(self, message: str, store_name: str = None, operation: str = None):
        super().__init__(message, "CERT_STORE_ERROR", {
            "store_name": store_name,
            "operation": operation
        })
        self.store_name = store_name
        self.operation = operation


class CertificateAuthorityError(CertificateManagementError):
    """
    Raised when Certificate Authority operations fail.

    This exception is raised when operations on Certificate Authority
    systems fail, such as connection errors, authentication failures,
    or CA system errors.
    """

    def __init__(self, message: str, ca_name: str = None, operation: str = None):
        super().__init__(message, "CERT_CA_ERROR", {
            "ca_name": ca_name,
            "operation": operation
        })
        self.ca_name = ca_name
        self.operation = operation


class CertificateParsingError(CertificateManagementError):
    """
    Raised when certificate parsing fails.

    This exception is raised when certificate data cannot be parsed
    or contains invalid format/structure.
    """

    def __init__(self, message: str, parser_type: str = None, certificate_data_length: int = None):
        super().__init__(message, "CERT_PARSING_ERROR", {
            "parser_type": parser_type,
            "certificate_data_length": certificate_data_length
        })


class CertificateConfigurationError(CertificateManagementError):
    """
    Raised when certificate management configuration is invalid.

    This exception is raised when the plugin configuration contains
    invalid or missing required parameters.
    """

    def __init__(self, message: str, config_section: str = None, invalid_fields: list = None):
        super().__init__(message, "CERT_CONFIG_ERROR", {
            "config_section": config_section,
            "invalid_fields": invalid_fields or []
        })


class CertificateNotificationError(CertificateManagementError):
    """
    Raised when certificate notification delivery fails.

    This exception is raised when notifications about certificate
    events cannot be delivered through the configured providers.
    """

    def __init__(self, message: str, provider_name: str = None, notification_type: str = None):
        super().__init__(message, "CERT_NOTIFICATION_ERROR", {
            "provider_name": provider_name,
            "notification_type": notification_type
        })


class CertificateExpiryError(CertificateManagementError):
    """
    Raised when certificate expiry monitoring encounters errors.

    This exception is raised when the expiry monitoring service
    encounters errors during certificate expiry checks.
    """

    def __init__(self, message: str, ca_name: str = None, check_type: str = None):
        super().__init__(message, "CERT_EXPIRY_ERROR", {
            "ca_name": ca_name,
            "check_type": check_type
        })


class CertificateSecurityError(CertificateManagementError):
    """
    Raised when certificate security policies are violated.

    This exception is raised when certificate operations violate
    configured security policies or requirements.
    """

    def __init__(self, message: str, policy_name: str = None, violation_details: dict = None):
        super().__init__(message, "CERT_SECURITY_ERROR", {
            "policy_name": policy_name,
            "violation_details": violation_details or {}
        })


class CertificateOperationTimeoutError(CertificateManagementError):
    """
    Raised when certificate operations timeout.

    This exception is raised when certificate management operations
    take longer than the configured timeout values.
    """

    def __init__(self, message: str, operation: str = None, timeout_seconds: int = None):
        super().__init__(message, "CERT_OPERATION_TIMEOUT", {
            "operation": operation,
            "timeout_seconds": timeout_seconds
        })


class CertificatePermissionError(CertificateManagementError):
    """
    Raised when certificate operations are not permitted.

    This exception is raised when the current user or service does not
    have sufficient permissions to perform the requested operation.
    """

    def __init__(self, message: str, operation: str = None, required_permission: str = None):
        super().__init__(message, "CERT_PERMISSION_ERROR", {
            "operation": operation,
            "required_permission": required_permission
        })


class CertificateIntegrityError(CertificateManagementError):
    """
    Raised when certificate data integrity checks fail.

    This exception is raised when certificate data appears to be
    corrupted or tampered with.
    """

    def __init__(self, message: str, certificate_id: str = None, integrity_check: str = None):
        super().__init__(message, "CERT_INTEGRITY_ERROR", {
            "certificate_id": certificate_id,
            "integrity_check": integrity_check
        })


# Aliases for compatibility with the main plugin interface
CertificateStorageError = CertificateStoreError
CertificateExpiredError = CertificateExpiryError
CertificateRevokedError = CertificateSecurityError
NotificationError = CertificateNotificationError
