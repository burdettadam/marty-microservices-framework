"""
Core interfaces for the Certificate Management Plugin.

This module defines the abstract interfaces that all certificate management
components must implement, providing a consistent API across different
backends and implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import CertificateInfo


class ICertificateAuthorityClient(ABC):
    """
    Interface for Certificate Authority clients.

    Provides standardized operations for interacting with different
    Certificate Authority systems like OpenXPKI, Vault PKI, etc.
    """

    @abstractmethod
    async def get_certificates(self, filter_params: dict[str, Any] | None = None) -> list[CertificateInfo]:
        """
        Retrieve certificates from the CA.

        Args:
            filter_params: Optional filtering parameters (country, status, etc.)

        Returns:
            List of certificate information objects
        """
        pass

    @abstractmethod
    async def get_expiring_certificates(self, days_threshold: int) -> list[CertificateInfo]:
        """
        Get certificates expiring within the specified days.

        Args:
            days_threshold: Number of days to look ahead for expiring certificates

        Returns:
            List of certificates expiring within the threshold
        """
        pass

    @abstractmethod
    async def import_certificate(self, cert_data: bytes, metadata: dict[str, Any] | None = None) -> str:
        """
        Import a certificate into the CA.

        Args:
            cert_data: Certificate data in DER or PEM format
            metadata: Optional metadata for the certificate

        Returns:
            Certificate identifier assigned by the CA
        """
        pass

    @abstractmethod
    async def export_certificate(self, cert_id: str) -> bytes:
        """
        Export a certificate from the CA.

        Args:
            cert_id: Certificate identifier

        Returns:
            Certificate data in DER format
        """
        pass

    @abstractmethod
    async def revoke_certificate(self, serial_number: str, reason: str) -> bool:
        """
        Revoke a certificate.

        Args:
            serial_number: Certificate serial number
            reason: Revocation reason

        Returns:
            True if revocation was successful
        """
        pass

    @abstractmethod
    async def get_certificate_status(self, serial_number: str) -> str:
        """
        Get the current status of a certificate.

        Args:
            serial_number: Certificate serial number

        Returns:
            Certificate status (valid, revoked, expired, etc.)
        """
        pass


class ICertificateStore(ABC):
    """
    Interface for certificate storage backends.

    Provides standardized operations for storing and retrieving certificates
    from different storage systems like Vault, file system, database, etc.
    """

    @abstractmethod
    async def store_certificate(self, cert_id: str, cert_data: bytes, metadata: dict[str, Any] | None = None) -> None:
        """
        Store a certificate.

        Args:
            cert_id: Unique certificate identifier
            cert_data: Certificate data in DER or PEM format
            metadata: Optional metadata for the certificate
        """
        pass

    @abstractmethod
    async def retrieve_certificate(self, cert_id: str) -> bytes | None:
        """
        Retrieve a certificate by ID.

        Args:
            cert_id: Certificate identifier

        Returns:
            Certificate data or None if not found
        """
        pass

    @abstractmethod
    async def list_certificates(self, filter_params: dict[str, Any] | None = None) -> list[str]:
        """
        List certificate IDs.

        Args:
            filter_params: Optional filtering parameters

        Returns:
            List of certificate identifiers
        """
        pass

    @abstractmethod
    async def delete_certificate(self, cert_id: str) -> bool:
        """
        Delete a certificate.

        Args:
            cert_id: Certificate identifier

        Returns:
            True if deletion was successful
        """
        pass

    @abstractmethod
    async def get_certificate_metadata(self, cert_id: str) -> dict[str, Any] | None:
        """
        Get certificate metadata.

        Args:
            cert_id: Certificate identifier

        Returns:
            Certificate metadata or None if not found
        """
        pass

    @abstractmethod
    async def update_certificate_metadata(self, cert_id: str, metadata: dict[str, Any]) -> bool:
        """
        Update certificate metadata.

        Args:
            cert_id: Certificate identifier
            metadata: New metadata

        Returns:
            True if update was successful
        """
        pass


class ICertificateParser(ABC):
    """
    Interface for certificate parsing implementations.

    Provides standardized operations for parsing and validating certificates
    with support for different formats and extensions.
    """

    @abstractmethod
    def parse_certificate(self, cert_data: bytes) -> CertificateInfo:
        """
        Parse certificate data into structured information.

        Args:
            cert_data: Certificate data in DER or PEM format

        Returns:
            Parsed certificate information
        """
        pass

    @abstractmethod
    def validate_certificate(self, cert_data: bytes, trusted_cas: list[bytes]) -> bool:
        """
        Validate certificate against trusted CAs.

        Args:
            cert_data: Certificate data to validate
            trusted_cas: List of trusted CA certificates

        Returns:
            True if certificate is valid
        """
        pass

    @abstractmethod
    def build_certificate_chain(self, cert_data: bytes, intermediate_certs: list[bytes]) -> list[bytes]:
        """
        Build complete certificate chain.

        Args:
            cert_data: End entity certificate
            intermediate_certs: Available intermediate certificates

        Returns:
            Complete certificate chain from end entity to root
        """
        pass

    @abstractmethod
    def extract_public_key(self, cert_data: bytes) -> bytes:
        """
        Extract public key from certificate.

        Args:
            cert_data: Certificate data

        Returns:
            Public key data
        """
        pass

    @abstractmethod
    def get_certificate_fingerprint(self, cert_data: bytes, algorithm: str = "sha256") -> str:
        """
        Calculate certificate fingerprint.

        Args:
            cert_data: Certificate data
            algorithm: Hash algorithm to use

        Returns:
            Certificate fingerprint as hex string
        """
        pass


class INotificationProvider(ABC):
    """
    Interface for certificate notification providers.

    Provides standardized operations for sending notifications about
    certificate events like expiry, revocation, etc.
    """

    @abstractmethod
    async def send_expiry_notification(self, cert_info: CertificateInfo, days_remaining: int) -> bool:
        """
        Send certificate expiry notification.

        Args:
            cert_info: Certificate information
            days_remaining: Number of days until expiry

        Returns:
            True if notification was sent successfully
        """
        pass

    @abstractmethod
    async def send_revocation_notification(self, cert_info: CertificateInfo, reason: str) -> bool:
        """
        Send certificate revocation notification.

        Args:
            cert_info: Certificate information
            reason: Revocation reason

        Returns:
            True if notification was sent successfully
        """
        pass

    @abstractmethod
    async def send_renewal_notification(self, cert_info: CertificateInfo) -> bool:
        """
        Send certificate renewal notification.

        Args:
            cert_info: Certificate information

        Returns:
            True if notification was sent successfully
        """
        pass

    @abstractmethod
    async def test_connectivity(self) -> bool:
        """
        Test notification provider connectivity.

        Returns:
            True if provider is reachable and functional
        """
        pass


class ICertificateValidator(ABC):
    """
    Interface for certificate validation implementations.

    Provides standardized operations for validating certificates
    against various policies and requirements.
    """

    @abstractmethod
    async def validate_certificate_policy(self, cert_info: CertificateInfo, policy_name: str) -> bool:
        """
        Validate certificate against a specific policy.

        Args:
            cert_info: Certificate information
            policy_name: Name of the validation policy

        Returns:
            True if certificate meets policy requirements
        """
        pass

    @abstractmethod
    async def validate_certificate_chain(self, cert_chain: list[bytes], trusted_roots: list[bytes]) -> bool:
        """
        Validate complete certificate chain.

        Args:
            cert_chain: Certificate chain to validate
            trusted_roots: Trusted root certificates

        Returns:
            True if chain is valid
        """
        pass

    @abstractmethod
    async def check_revocation_status(self, cert_info: CertificateInfo) -> str:
        """
        Check certificate revocation status.

        Args:
            cert_info: Certificate information

        Returns:
            Revocation status (valid, revoked, unknown)
        """
        pass
