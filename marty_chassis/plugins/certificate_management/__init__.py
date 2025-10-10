"""
Certificate Management Plugin for Marty Microservices Framework.

This plugin provides comprehensive certificate lifecycle management including:
- Certificate Authority integration
- Certificate storage and retrieval
- Certificate parsing and validation
- Expiry monitoring and notifications
- Certificate rotation and automation
"""

from .config import ConfigurationLoader, validate_configuration
from .exceptions import (
    CertificateAuthorityError,
    CertificateConfigurationError,
    CertificateExpiredError,
    CertificateManagementError,
    CertificateNotFoundError,
    CertificateParsingError,
    CertificateRevokedError,
    CertificateStorageError,
    CertificateValidationError,
    NotificationError,
)
from .interfaces import (
    ICertificateAuthorityClient,
    ICertificateParser,
    ICertificateStore,
    ICertificateValidator,
    INotificationProvider,
)
from .models import (
    CertificateInfo,
    CertificateManagementConfig,
    CertificateMetrics,
    CertificateOperation,
    NotificationRecord,
)
from .plugin import CertificateManagementPlugin

__all__ = [
    # Core plugin
    "CertificateManagementPlugin",

    # Configuration
    "ConfigurationLoader",
    "validate_configuration",

    # Interfaces
    "ICertificateAuthorityClient",
    "ICertificateStore",
    "ICertificateParser",
    "INotificationProvider",
    "ICertificateValidator",

    # Models
    "CertificateInfo",
    "CertificateManagementConfig",
    "CertificateOperation",
    "CertificateMetrics",
    "NotificationRecord",

    # Exceptions
    "CertificateManagementError",
    "CertificateParsingError",
    "CertificateStorageError",
    "CertificateAuthorityError",
    "CertificateValidationError",
    "CertificateConfigurationError",
    "CertificateNotFoundError",
    "CertificateExpiredError",
    "CertificateRevokedError",
    "NotificationError",
]
