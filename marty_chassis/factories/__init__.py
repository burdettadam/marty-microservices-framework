"""
Service factories for the Marty Chassis.

This module provides factory functions to create different types of services
with all cross-cutting concerns automatically configured.
"""

from .fastapi_factory import (
    add_health_checks_to_app,
    add_metrics_to_app,
    add_security_to_app,
    create_fastapi_service,
)

__all__ = [
    "create_fastapi_service",
    "add_security_to_app",
    "add_metrics_to_app",
    "add_health_checks_to_app",
]
