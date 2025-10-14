"""
Configuration management for example-service.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Basic settings
    service_name: str = "example-service"
    version: str = "1.0.0"
    debug: bool = False

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080

    # Plugin settings
    plugin_enabled: bool = True
    plugin_name: str = "example_business"

    # Database settings (if needed)
    database_url: str = "sqlite:///./test.db"

    # TODO: Add your configuration variables here
    # Example:
    # api_key: str = "your-api-key"
    # external_service_url: str = "https://api.example.com"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
