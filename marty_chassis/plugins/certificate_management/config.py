"""
Configuration utilities for Certificate Management Plugin.

This module provides configuration loading and validation utilities
for the certificate management plugin.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import (
    CertificateAuthorityConfig,
    CertificateManagementConfig,
    CertificateStoreConfig,
    ExpiryNotificationConfig,
)


class ConfigurationLoader:
    """Loads and validates certificate management configuration."""

    @staticmethod
    def load_from_dict(config_dict: dict[str, Any]) -> CertificateManagementConfig:
        """
        Load configuration from a dictionary.

        Args:
            config_dict: Configuration dictionary

        Returns:
            Validated configuration object
        """
        # Extract expiry monitoring configuration
        expiry_config = config_dict.get("expiry_monitoring", {})
        expiry_monitoring = ExpiryNotificationConfig(
            enabled=expiry_config.get("enabled", True),
            check_interval_hours=expiry_config.get("check_interval_hours", 24),
            notification_days=expiry_config.get("notification_days", [30, 14, 7, 1]),
            history_enabled=expiry_config.get("history_enabled", True),
            history_storage_type=expiry_config.get("history_storage_type", "file"),
            history_storage_path=expiry_config.get("history_storage_path"),
            max_history_age_days=expiry_config.get("max_history_age_days", 365),
        )

        # Extract certificate stores configuration
        stores_config = config_dict.get("certificate_stores", {})
        certificate_stores = {}
        for store_name, store_config in stores_config.items():
            certificate_stores[store_name] = CertificateStoreConfig(
                store_type=store_config.get("type", "vault"),
                connection_params=store_config.get("connection_params", {}),
                encryption_enabled=store_config.get("encryption_enabled", True),
                backup_enabled=store_config.get("backup_enabled", False),
                backup_location=store_config.get("backup_location"),
                compression_enabled=store_config.get("compression_enabled", False),
                max_certificate_size_mb=store_config.get("max_certificate_size_mb", 10),
            )

        # Extract CA clients configuration
        cas_config = config_dict.get("certificate_authorities", {})
        ca_clients = {}
        for ca_name, ca_config in cas_config.items():
            ca_clients[ca_name] = CertificateAuthorityConfig(
                ca_type=ca_config.get("type", "openxpki"),
                connection_params=ca_config.get("connection_params", {}),
                retry_attempts=ca_config.get("retry_attempts", 3),
                retry_delay_seconds=ca_config.get("retry_delay_seconds", 5),
                connection_timeout_seconds=ca_config.get("connection_timeout_seconds", 30),
                read_timeout_seconds=ca_config.get("read_timeout_seconds", 60),
                verify_ssl=ca_config.get("verify_ssl", True),
            )

        return CertificateManagementConfig(
            enabled=config_dict.get("enabled", True),
            certificate_authorities=ca_clients,
            certificate_stores=certificate_stores,
            expiry_monitoring=expiry_monitoring,
            default_ca=config_dict.get("default_ca"),
            default_store=config_dict.get("default_store"),
            security_policy=config_dict.get("security_policy", "strict"),
            audit_enabled=config_dict.get("audit_enabled", True),
            metrics_enabled=config_dict.get("metrics_enabled", True),
            parser_strict_mode=config_dict.get("parser_strict_mode", False),
            validate_certificate_chains=config_dict.get("validate_certificate_chains", True),
            check_revocation_status=config_dict.get("check_revocation_status", True),
        )

    @staticmethod
    def load_from_file(config_path: str) -> CertificateManagementConfig:
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Validated configuration object
        """
        with open(config_path) as f:
            config_dict = yaml.safe_load(f)

        return ConfigurationLoader.load_from_dict(config_dict)

    @staticmethod
    def load_from_environment() -> CertificateManagementConfig:
        """
        Load configuration from environment variables.

        Returns:
            Configuration object with environment variable values
        """
        config_dict = {
            "enabled": os.getenv("CERT_MGMT_ENABLED", "true").lower() == "true",
            "metrics_enabled": os.getenv("CERT_MGMT_METRICS_ENABLED", "true").lower() == "true",
            "security_policy": os.getenv("CERT_MGMT_SECURITY_POLICY", "strict"),
            "audit_enabled": os.getenv("CERT_MGMT_AUDIT_ENABLED", "true").lower() == "true",
            "expiry_monitoring": {
                "enabled": os.getenv("CERT_EXPIRY_MONITORING_ENABLED", "true").lower() == "true",
                "check_interval_hours": int(os.getenv("CERT_EXPIRY_CHECK_INTERVAL", "24")),
                "notification_days": [int(x.strip()) for x in os.getenv("CERT_EXPIRY_NOTIFICATION_DAYS", "30,14,7,1").split(",")],
                "history_enabled": os.getenv("CERT_EXPIRY_HISTORY_ENABLED", "true").lower() == "true",
                "history_storage_type": os.getenv("CERT_EXPIRY_HISTORY_TYPE", "file"),
            }
        }

        # Add CA client configuration from environment
        ca_type = os.getenv("CERT_DEFAULT_CA_TYPE", "openxpki")
        ca_endpoint = os.getenv("CERT_DEFAULT_CA_ENDPOINT")
        if ca_endpoint:
            config_dict["certificate_authorities"] = {
                "default": {
                    "type": ca_type,
                    "connection_params": {"endpoint": ca_endpoint},
                    "connection_timeout_seconds": int(os.getenv("CERT_CA_TIMEOUT", "30")),
                    "retry_attempts": int(os.getenv("CERT_CA_RETRIES", "3")),
                }
            }
            config_dict["default_ca"] = "default"

        # Add certificate store configuration from environment
        store_type = os.getenv("CERT_DEFAULT_STORE_TYPE", "vault")
        store_connection = os.getenv("CERT_DEFAULT_STORE_CONNECTION")
        if store_connection:
            config_dict["certificate_stores"] = {
                "default": {
                    "type": store_type,
                    "connection_params": {"connection_string": store_connection},
                    "encryption_enabled": os.getenv("CERT_STORE_ENCRYPTION", "true").lower() == "true",
                }
            }
            config_dict["default_store"] = "default"

        return ConfigurationLoader.load_from_dict(config_dict)

    @staticmethod
    def get_default_config() -> CertificateManagementConfig:
        """
        Get default configuration for development/testing.

        Returns:
            Default configuration object
        """
        return CertificateManagementConfig(
            enabled=True,
            metrics_enabled=True,
            audit_enabled=True,
            security_policy="strict",
            expiry_monitoring=ExpiryNotificationConfig(
                enabled=True,
                check_interval_hours=24,
                notification_days=[30, 14, 7, 1],
                history_enabled=True,
                history_storage_type="file",
                max_history_age_days=365,
            ),
            certificate_stores={},
            certificate_authorities={},
            default_ca=None,
            default_store=None,
            parser_strict_mode=False,
            validate_certificate_chains=True,
            check_revocation_status=True,
        )


def validate_configuration(config: CertificateManagementConfig) -> list[str]:
    """
    Validate configuration and return list of errors.

    Args:
        config: Configuration to validate

    Returns:
        List of validation error messages
    """
    errors = []

    # Validate expiry monitoring configuration
    if config.expiry_monitoring.enabled:
        if config.expiry_monitoring.check_interval_hours <= 0:
            errors.append("Expiry monitoring check interval must be positive")

        if not config.expiry_monitoring.notification_days:
            errors.append("At least one notification day threshold must be specified")
        else:
            for days in config.expiry_monitoring.notification_days:
                if days <= 0:
                    errors.append(f"Notification days must be positive, got {days}")

    # Validate CA client configurations
    for ca_name, ca_config in config.certificate_authorities.items():
        if ca_config.connection_timeout_seconds <= 0:
            errors.append(f"CA client '{ca_name}' timeout must be positive")

        if ca_config.retry_attempts < 0:
            errors.append(f"CA client '{ca_name}' retry attempts must be non-negative")

    # Validate certificate store configurations
    for store_name, store_config in config.certificate_stores.items():
        if not store_config.connection_params:
            errors.append(f"Certificate store '{store_name}' missing connection parameters")

        if store_config.max_certificate_size_mb <= 0:
            errors.append(f"Certificate store '{store_name}' max certificate size must be positive")

    # Validate default references
    if config.default_ca and config.default_ca not in config.certificate_authorities:
        errors.append(f"Default CA '{config.default_ca}' not defined")

    if config.default_store and config.default_store not in config.certificate_stores:
        errors.append(f"Default certificate store '{config.default_store}' not defined")

    return errors
