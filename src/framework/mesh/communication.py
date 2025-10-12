"""
Advanced Service Discovery and Communication Framework for Marty Microservices

This module has been decomposed into focused modules for better maintainability.
This file now serves as a compatibility shim that re-exports all classes from
the decomposed modules.

For new development, consider importing directly from the specific modules:
- communication/models.py: Communication protocols and data models
- communication/health_checker.py: Service health checking functionality
- communication/__init__.py: Complete communication system

Note: Some large classes (ServiceCommunicationManager, ServiceDependencyManager,
AdvancedServiceDiscovery) are still in the original file and need further decomposition.
"""

from .communication.health_checker import ServiceHealthChecker

# Re-export everything from the decomposed modules for backward compatibility
from .communication.models import (
    CommunicationMetrics,
    CommunicationProtocol,
    DependencyType,
    HealthStatus,
    ServiceContract,
    ServiceDependency,
    ServiceInstance,
    ServiceState,
    ServiceType,
)

__all__ = [
    # From decomposed modules
    "CommunicationProtocol",
    "ServiceType",
    "HealthStatus",
    "ServiceState",
    "DependencyType",
    "ServiceInstance",
    "ServiceDependency",
    "ServiceContract",
    "CommunicationMetrics",
    "ServiceHealthChecker",
]
