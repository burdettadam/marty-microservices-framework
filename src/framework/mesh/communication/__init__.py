"""
Communication package for Marty Microservices Framework

This package provides comprehensive service communication functionality including:
- Communication models and protocols
- Health checking for services
- Service-to-service communication management
- Service dependency management
- Advanced service discovery
"""

from .health_checker import ServiceHealthChecker
from .models import (
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
