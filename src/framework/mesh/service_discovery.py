"""
Service Discovery Implementation for Marty Microservices Framework

This module has been decomposed into focused modules for better maintainability.
This file now serves as a compatibility shim that re-exports all classes from
the decomposed modules.

For new development, consider importing directly from the specific modules:
- discovery/registry.py: Core service registry functionality
- discovery/health_checker.py: Health checking for service endpoints
- discovery/__init__.py: Complete service discovery system
"""

# Re-export everything from the decomposed modules for backward compatibility
from .discovery import (
    HealthChecker,
    ServiceDiscovery,
    ServiceDiscoveryConfig,
    ServiceEndpoint,
    ServiceRegistry,
)

__all__ = [
    "ServiceDiscovery",
    "ServiceRegistry",
    "HealthChecker",
    "ServiceEndpoint",
    "ServiceDiscoveryConfig",
]
