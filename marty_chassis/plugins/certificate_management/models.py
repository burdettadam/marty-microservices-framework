"""
Data models for the Certificate Management Plugin.

This module defines the core data structures used throughout the
certificate management system, including certificate information,
configuration objects, and related models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class CertificateStatus(Enum):
    """Certificate status enumeration."""
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"
    UNKNOWN = "unknown"


class CertificateType(Enum):
    """Certificate type enumeration."""
    CSCA = "csca"  # Country Signing Certificate Authority
    DS = "ds"      # Document Signer
    CSCA_LINK = "csca_link"  # CSCA Link Certificate
    END_ENTITY = "end_entity"
    INTERMEDIATE = "intermediate"
    ROOT = "root"
    UNKNOWN = "unknown"


class NotificationLevel(Enum):
    """Notification level enumeration."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class CertificateInfo:
    """
    Comprehensive certificate information container.

    Contains all relevant information about a certificate including
    standard X.509 fields and ICAO-specific extensions.
    """
    serial_number: str
    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime

    # Optional fields
    country_code: str | None = None
    certificate_type: CertificateType = CertificateType.UNKNOWN
    status: CertificateStatus = CertificateStatus.UNKNOWN
    fingerprint_sha256: str = ""
    fingerprint_sha1: str = ""

    # Public key information
    public_key_algorithm: str = ""
    public_key_size: int | None = None

    # Extensions
    key_usage: list[str] = field(default_factory=list)
    extended_key_usage: list[str] = field(default_factory=list)

    # ICAO-specific fields
    document_type_list: list[str] = field(default_factory=list)
    master_list_identifier: str | None = None

    # Metadata
    source_ca: str | None = None
    import_date: datetime | None = None
    last_updated: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def days_until_expiry(self) -> int:
        """Calculate days until certificate expires."""
        if self.not_after:
            delta = self.not_after - datetime.now()
            return max(0, delta.days)
        return 0

    @property
    def is_expired(self) -> bool:
        """Check if certificate is expired."""
        return datetime.now() > self.not_after if self.not_after else False

    @property
    def is_valid_now(self) -> bool:
        """Check if certificate is currently valid (time-wise)."""
        now = datetime.now()
        return (self.not_before <= now <= self.not_after
                if self.not_before and self.not_after else False)


@dataclass
class ExpiryNotificationConfig:
    """Configuration for certificate expiry notifications."""
    enabled: bool = True
    notification_days: list[int] = field(default_factory=lambda: [30, 15, 7, 3, 1])
    check_interval_hours: int = 24
    history_enabled: bool = True
    history_storage_type: str = "file"  # file, database, memory
    history_storage_path: str | None = None
    max_history_age_days: int = 365

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.check_interval_hours < 1:
            raise ValueError("Check interval must be at least 1 hour")
        if not self.notification_days or min(self.notification_days) < 0:
            raise ValueError("Notification days must be positive integers")


@dataclass
class CertificateStoreConfig:
    """Configuration for certificate storage backend."""
    store_type: str  # vault, file, database
    connection_params: dict[str, Any] = field(default_factory=dict)
    encryption_enabled: bool = True
    backup_enabled: bool = True
    backup_location: str | None = None
    compression_enabled: bool = False
    max_certificate_size_mb: int = 10

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.store_type not in ["vault", "file", "database"]:
            raise ValueError(f"Unsupported store type: {self.store_type}")
        if self.max_certificate_size_mb < 1:
            raise ValueError("Maximum certificate size must be at least 1 MB")


@dataclass
class CertificateAuthorityConfig:
    """Configuration for Certificate Authority client."""
    ca_type: str  # openxpki, vault_pki, etc.
    connection_params: dict[str, Any] = field(default_factory=dict)
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    connection_timeout_seconds: int = 30
    read_timeout_seconds: int = 60
    verify_ssl: bool = True

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.retry_attempts < 0:
            raise ValueError("Retry attempts must be non-negative")
        if self.connection_timeout_seconds < 1:
            raise ValueError("Connection timeout must be at least 1 second")


@dataclass
class NotificationProviderConfig:
    """Configuration for notification provider."""
    provider_type: str  # email, webhook, logging, slack, etc.
    connection_params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    retry_attempts: int = 3
    retry_delay_seconds: int = 10
    notification_level: NotificationLevel = NotificationLevel.WARNING

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.retry_attempts < 0:
            raise ValueError("Retry attempts must be non-negative")


@dataclass
class CertificateManagementConfig:
    """Main configuration for the Certificate Management Plugin."""
    enabled: bool = True

    # Sub-configurations
    certificate_authorities: dict[str, CertificateAuthorityConfig] = field(default_factory=dict)
    certificate_stores: dict[str, CertificateStoreConfig] = field(default_factory=dict)
    notification_providers: dict[str, NotificationProviderConfig] = field(default_factory=dict)
    expiry_monitoring: ExpiryNotificationConfig = field(default_factory=ExpiryNotificationConfig)

    # Global settings
    default_ca: str | None = None
    default_store: str | None = None
    security_policy: str = "strict"  # strict, standard, permissive
    audit_enabled: bool = True
    metrics_enabled: bool = True

    # Parser settings
    parser_strict_mode: bool = False
    validate_certificate_chains: bool = True
    check_revocation_status: bool = True

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.certificate_authorities:
            raise ValueError("At least one certificate authority must be configured")
        if not self.certificate_stores:
            raise ValueError("At least one certificate store must be configured")
        if self.security_policy not in ["strict", "standard", "permissive"]:
            raise ValueError(f"Invalid security policy: {self.security_policy}")


@dataclass
class CertificateOperation:
    """Represents a certificate operation for audit logging."""
    operation_id: str
    operation_type: str  # import, export, validate, monitor, etc.
    certificate_id: str | None = None
    certificate_serial: str | None = None
    ca_name: str | None = None
    store_name: str | None = None
    user_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, success, failed
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationRecord:
    """Record of a sent notification."""
    notification_id: str
    certificate_serial: str
    notification_type: str  # expiry, revocation, renewal
    provider: str
    recipient: str
    sent_at: datetime
    status: str  # sent, failed, pending
    days_remaining: int | None = None
    error_message: str | None = None


@dataclass
class CertificateValidationResult:
    """Result of certificate validation."""
    is_valid: bool
    certificate_serial: str
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    trust_path: list[str] = field(default_factory=list)
    revocation_status: str = "unknown"
    policy_violations: list[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)


@dataclass
class CertificateMetrics:
    """Certificate management metrics."""
    total_certificates: int = 0
    valid_certificates: int = 0
    expired_certificates: int = 0
    expiring_soon: int = 0  # Within configured threshold
    revoked_certificates: int = 0
    certificates_by_type: dict[str, int] = field(default_factory=dict)
    certificates_by_ca: dict[str, int] = field(default_factory=dict)
    certificates_by_country: dict[str, int] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)
