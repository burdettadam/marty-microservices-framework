"""
Configuration for order-service service using DRY patterns.

This configuration automatically inherits all common patterns from FastAPIServiceConfig,
reducing configuration code by ~70% compared to traditional patterns.
"""

from marty_common.base_config import FastAPIServiceConfig


class OrderServiceConfig(FastAPIServiceConfig):
    """
    Configuration for order-service service.

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
        env_prefix = "ORDER_SERVICE_"


# Factory function for easy configuration creation
def create_order_service_config(**kwargs) -> OrderServiceConfig:
    """
    Create order-service configuration with defaults.

    Args:
        **kwargs: Configuration overrides

    Returns:
        Configured OrderServiceConfig instance
    """
    defaults = {
        "service_name": "order-service",
        "title": "OrderService API",
        "description": "Order processing and workflow management service",
        "version": "1.0.0",
        "http_port": 8001,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }

    # Merge defaults with provided kwargs
    config_data = {**defaults, **kwargs}
    return OrderServiceConfig(**config_data)
