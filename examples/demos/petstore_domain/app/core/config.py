"""
Configuration management for PetstoreDomain Service

This module provides structured configuration management following the Marty framework patterns.
Configuration is loaded from environment variables and YAML files with environment-specific overrides.
"""
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class PetstoreDomainConfig(BaseSettings):
    """
    Configuration class for PetstoreDomain Service.

    Uses Pydantic BaseSettings for automatic environment variable loading
    and validation. Configuration follows the Marty framework patterns.
    """

    # Service identification
    service_name: str = Field(default="petstore-domain", description="Service name")
    service_version: str = Field(default="1.0.0", description="Service version")
    environment: str = Field(default="development", description="Environment (development, staging, production)")

    # Server configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")

    # Logging configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json, text)")
    enable_audit_logging: bool = Field(default=True, description="Enable audit logging")

    # Database configuration (if needed)
    database_url: Optional[str] = Field(default=None, description="Database connection URL")
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_timeout: int = Field(default=30, description="Database connection timeout")

    # Cache configuration (if needed)
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL")
    cache_ttl: int = Field(default=3600, description="Default cache TTL in seconds")

    # External service configuration
    external_api_base_url: Optional[str] = Field(default=None, description="External API base URL")
    external_api_timeout: int = Field(default=30, description="External API timeout in seconds")
    external_api_retries: int = Field(default=3, description="External API retry attempts")

    # Security configuration
    secret_key: str = Field(default="dev-secret-key-change-in-production", description="Secret key for signing")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration time")

    # Enhanced Security Configuration
    # Authentication settings
    enable_authentication: bool = Field(default=True, description="Enable authentication middleware")
    require_https: bool = Field(default=False, description="Require HTTPS for all requests")
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_secret_key: Optional[str] = Field(default=None, description="JWT signing secret key")

    # Authorization settings
    enable_authorization: bool = Field(default=True, description="Enable authorization policies")
    default_policy_engine: str = Field(default="builtin", description="Default policy engine (builtin, opa, oso)")
    policy_file_path: Optional[str] = Field(default="config/policies", description="Path to policy files")

    # HashiCorp Vault configuration
    vault_enabled: bool = Field(default=False, description="Enable HashiCorp Vault integration")
    vault_url: Optional[str] = Field(default="http://localhost:8200", description="Vault server URL")
    vault_token: Optional[str] = Field(default=None, description="Vault authentication token")
    vault_auth_method: str = Field(default="token", description="Vault auth method (token, kubernetes, aws)")
    vault_role: Optional[str] = Field(default="petstore-domain", description="Vault role for Kubernetes auth")
    vault_namespace: Optional[str] = Field(default=None, description="Vault namespace")
    vault_mount_point: str = Field(default="secret", description="Vault secret mount point")

    # OPA (Open Policy Agent) configuration
    opa_enabled: bool = Field(default=False, description="Enable OPA policy engine")
    opa_url: Optional[str] = Field(default="http://localhost:8181", description="OPA server URL")
    opa_policy_path: str = Field(default="authz/allow", description="OPA policy evaluation path")
    opa_timeout: int = Field(default=5, description="OPA request timeout in seconds")

    # Oso configuration
    oso_enabled: bool = Field(default=False, description="Enable Oso policy engine")
    oso_policy_file: Optional[str] = Field(default="config/policies/authorization.polar", description="Oso policy file path")

    # mTLS configuration
    mtls_enabled: bool = Field(default=False, description="Enable mutual TLS")
    mtls_ca_cert_path: Optional[str] = Field(default=None, description="mTLS CA certificate path")
    mtls_client_cert_path: Optional[str] = Field(default=None, description="mTLS client certificate path")
    mtls_client_key_path: Optional[str] = Field(default=None, description="mTLS client private key path")

    # Certificate management
    cert_auto_rotate: bool = Field(default=True, description="Enable automatic certificate rotation")
    cert_rotation_days: int = Field(default=30, description="Certificate rotation interval in days")
    cert_common_name: str = Field(default="petstore-domain.local", description="Certificate common name")

    # Security headers
    security_headers_enabled: bool = Field(default=True, description="Enable security headers")
    hsts_enabled: bool = Field(default=True, description="Enable HSTS header")
    content_security_policy: str = Field(
        default="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
        description="Content Security Policy header"
    )

    # API security
    api_key_enabled: bool = Field(default=True, description="Enable API key authentication")
    api_rate_limiting: bool = Field(default=True, description="Enable API rate limiting")
    api_cors_enabled: bool = Field(default=True, description="Enable CORS for APIs")

    # Audit and logging
    security_audit_enabled: bool = Field(default=True, description="Enable security audit logging")
    audit_log_level: str = Field(default="INFO", description="Audit log level")
    audit_log_format: str = Field(default="json", description="Audit log format")
    sensitive_data_masking: bool = Field(default=True, description="Enable sensitive data masking in logs")

    # Monitoring and observability
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=8080, description="Metrics endpoint port")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    jaeger_endpoint: Optional[str] = Field(default=None, description="Jaeger tracing endpoint")

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=100, description="Requests per minute per client")

    # CORS configuration
    cors_origins: list = Field(default=["*"], description="CORS allowed origins")
    cors_methods: list = Field(default=["*"], description="CORS allowed methods")
    cors_headers: list = Field(default=["*"], description="CORS allowed headers")

    # Business logic specific configuration
    # Add your service-specific configuration here
    max_concurrent_operations: int = Field(default=10, description="Maximum concurrent business operations")
    operation_timeout: int = Field(default=300, description="Business operation timeout in seconds")
    enable_async_processing: bool = Field(default=True, description="Enable asynchronous processing")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Environment variable prefixes
        env_prefix = "PETSTORE_DOMAIN_"

        @classmethod
        def customise_sources(
            cls,
            init_settings,
            env_settings,
            file_secret_settings
        ):
            """
            Customize configuration sources priority.
            Priority (highest to lowest):
            1. Environment variables
            2. .env file
            3. Init settings (defaults)
            """
            return (
                env_settings,
                init_settings,
                file_secret_settings,
            )

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration dictionary"""
        return {
            "url": self.database_url,
            "pool_size": self.database_pool_size,
            "timeout": self.database_timeout
        }

    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration dictionary"""
        return {
            "url": self.redis_url,
            "ttl": self.cache_ttl
        }

    def get_external_api_config(self) -> Dict[str, Any]:
        """Get external API configuration dictionary"""
        return {
            "base_url": self.external_api_base_url,
            "timeout": self.external_api_timeout,
            "retries": self.external_api_retries
        }

    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"

    def get_cors_config(self) -> Dict[str, Any]:
        """Get CORS configuration dictionary"""
        return {
            "allow_origins": self.cors_origins,
            "allow_methods": self.cors_methods,
            "allow_headers": self.cors_headers,
            "allow_credentials": True
        }

    def get_security_config(self) -> Dict[str, Any]:
        """Get comprehensive security configuration"""
        return {
            "authentication": {
                "enabled": self.enable_authentication,
                "jwt_algorithm": self.jwt_algorithm,
                "token_expire_minutes": self.access_token_expire_minutes,
                "require_https": self.require_https
            },
            "authorization": {
                "enabled": self.enable_authorization,
                "default_engine": self.default_policy_engine,
                "policy_file_path": self.policy_file_path
            },
            "vault": {
                "enabled": self.vault_enabled,
                "url": self.vault_url,
                "auth_method": self.vault_auth_method,
                "role": self.vault_role,
                "namespace": self.vault_namespace,
                "mount_point": self.vault_mount_point
            },
            "opa": {
                "enabled": self.opa_enabled,
                "url": self.opa_url,
                "policy_path": self.opa_policy_path,
                "timeout": self.opa_timeout
            },
            "oso": {
                "enabled": self.oso_enabled,
                "policy_file": self.oso_policy_file
            },
            "mtls": {
                "enabled": self.mtls_enabled,
                "ca_cert_path": self.mtls_ca_cert_path,
                "client_cert_path": self.mtls_client_cert_path,
                "client_key_path": self.mtls_client_key_path
            },
            "certificates": {
                "auto_rotate": self.cert_auto_rotate,
                "rotation_days": self.cert_rotation_days,
                "common_name": self.cert_common_name
            },
            "headers": {
                "security_headers_enabled": self.security_headers_enabled,
                "hsts_enabled": self.hsts_enabled,
                "content_security_policy": self.content_security_policy
            },
            "api": {
                "api_key_enabled": self.api_key_enabled,
                "rate_limiting": self.api_rate_limiting,
                "cors_enabled": self.api_cors_enabled
            },
            "audit": {
                "enabled": self.security_audit_enabled,
                "log_level": self.audit_log_level,
                "log_format": self.audit_log_format,
                "sensitive_data_masking": self.sensitive_data_masking
            }
        }

    def get_vault_config(self) -> Dict[str, Any]:
        """Get HashiCorp Vault configuration"""
        return {
            "enabled": self.vault_enabled,
            "url": self.vault_url,
            "auth_method": self.vault_auth_method,
            "token": self.vault_token,
            "role": self.vault_role,
            "namespace": self.vault_namespace,
            "mount_point": self.vault_mount_point
        }

@lru_cache()
def get_settings() -> PetstoreDomainConfig:
    """
    Get cached configuration instance.

    Uses lru_cache to ensure configuration is loaded only once
    and reused throughout the application lifecycle.

    Returns:
        Configuration instance
    """
    return PetstoreDomainConfig()

def get_config_summary() -> Dict[str, Any]:
    """
    Get configuration summary for debugging and monitoring.

    Returns:
        Dictionary with non-sensitive configuration values
    """
    settings = get_settings()

    return {
        "service_name": settings.service_name,
        "service_version": settings.service_version,
        "environment": settings.environment,
        "host": settings.host,
        "port": settings.port,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "enable_metrics": settings.enable_metrics,
        "enable_tracing": settings.enable_tracing,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "max_concurrent_operations": settings.max_concurrent_operations,
        "enable_async_processing": settings.enable_async_processing,
        # Don't include sensitive values like secret_key, database_url, etc.
    }
