"""Strongly typed application configuration."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime configuration loaded from environment variables and `.env` files."""

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", env_nested_delimiter="__"
    )

    service_name: str = Field(
        default="microservice-template", description="Service identifier"
    )
    environment: str = Field(default="local", description="Deployment environment name")
    grpc_host: str = Field(default="0.0.0.0", description="gRPC bind host")
    grpc_port: int = Field(default=50051, description="gRPC bind port")
    metrics_port: int = Field(default=9000, description="Prometheus metrics port")
    shutdown_grace_period: float = Field(
        default=30.0, description="Seconds to wait on shutdown", ge=1.0
    )
    tracing_enabled: bool = Field(
        default=True, description="Toggle OpenTelemetry tracing"
    )
    tracing_endpoint: str = Field(
        default="http://localhost:4317", description="OTLP collector endpoint"
    )
    log_level: str = Field(default="INFO", description="Application log level")
    version: str = Field(default="0.1.0", description="Service semantic version")

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "TRACE"}
        upper_value = value.upper()
        if upper_value not in allowed:
            msg = f"Invalid log level '{value}'. Choose one of: {', '.join(sorted(allowed))}."
            raise ValueError(msg)
        return upper_value

    @property
    def grpc_bind(self) -> str:
        """Return `host:port` string for gRPC bind."""
        return f"{self.grpc_host}:{self.grpc_port}"

    @property
    def metrics_bind(self) -> tuple[str, int]:
        """Return separate host/port for metrics server."""
        return self.grpc_host, self.metrics_port
