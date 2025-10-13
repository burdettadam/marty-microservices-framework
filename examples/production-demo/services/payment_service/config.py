"""
Configuration for payment-service service using DRY patterns.

This configuration automatically inherits all common patterns from FastAPIServiceConfig,
reducing configuration code by ~70% compared to traditional patterns.
"""

from marty_common.base_config import FastAPIServiceConfig


class PaymentServiceConfig(FastAPIServiceConfig):
    """
    Configuration for payment-service service.

    Inherits from FastAPIServiceConfig which provides:
    - Common service configuration (logging, debugging, etc.)
    - HTTP server configuration (host, port, CORS)
    - Security configuration (allowed hosts, TLS)
    - FastAPI configuration (docs, OpenAPI)
    - Database configuration (if needed)
    - Metrics and health check configuration
    """

    # Service-specific configuration fields
    # Add your custom configuration here
    # Example:
    # max_upload_size: int = Field(default=10485760, description="Maximum upload size in bytes")
    # cache_ttl_seconds: int = Field(default=3600, description="Cache TTL in seconds")
    # external_api_timeout: int = Field(default=30, description="External API timeout in seconds")

    class Config:
        """Pydantic configuration."""
        env_prefix = "PAYMENT_SERVICE_"


# Factory function for easy configuration creation
def create_payment_service_config(**kwargs) -> PaymentServiceConfig:
    """
    Create payment-service configuration with defaults.

    Args:
        **kwargs: Configuration overrides

    Returns:
        Configured PaymentServiceConfig instance
    """
    defaults = {
        "service_name": "payment-service",
        "title": "PaymentService API",
        "description": "Payment processing and transaction management service",
        "version": "1.0.0",
        "http_port": 8002,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }

    # Merge defaults with provided kwargs
    config_data = {**defaults, **kwargs}
    return PaymentServiceConfig(**config_data)
