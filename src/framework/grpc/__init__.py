"""
gRPC infrastructure components for enterprise microservices.

This package provides:
- Service factory patterns for DRY gRPC service creation
- Service discovery and registration
- Health checking and monitoring
- Interceptors for cross-cutting concerns
"""

from .service_factory import (
    GRPCServiceFactory,
    ServiceDefinition,
    ServiceRegistry,
    grpc_service,
    run_grpc_service,
    service_registry,
)

__all__ = [
    "GRPCServiceFactory",
    "ServiceDefinition",
    "ServiceRegistry",
    "grpc_service",
    "run_grpc_service",
    "service_registry",
]
