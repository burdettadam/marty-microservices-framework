"""
Application configuration using Pydantic settings.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = "Marty Dashboard"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "production"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Security
    secret_key: str = Field(default="your-secret-key-change-in-production")
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    trusted_hosts: Optional[List[str]] = None

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/marty_dashboard"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Authentication
    jwt_secret: str = Field(default="jwt-secret-change-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # Frontend
    serve_frontend: bool = True
    frontend_url: str = "http://localhost:3000"

    # Service Discovery
    consul_host: str = "localhost"
    consul_port: int = 8500
    consul_scheme: str = "http"

    # Metrics
    prometheus_host: str = "localhost"
    prometheus_port: int = 9090
    metrics_collection_interval: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
