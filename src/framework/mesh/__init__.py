"""
Service Mesh and Orchestration Patterns for Marty Microservices Framework

This module re-exports all classes from the decomposed mesh modules to maintain
backward compatibility while improving code organization.
"""

# Re-export all classes from decomposed modules

# Load balancing
from .load_balancing import LoadBalancer, LoadBalancingAlgorithm, TrafficSplitter

# Service discovery
from .service_discovery import (
    ServiceDiscoveryClient,
    ServiceHealthChecker,
    ServiceRegistry,
)

# Service mesh configuration
from .service_mesh import (
    LoadBalancingConfig,
    ServiceEndpoint,
    ServiceMeshType,
    TrafficPolicy,
)

# Traffic management
from .traffic_management import RouteMatch, TrafficManager, TrafficSplit

# Maintain compatibility with original import structure
__all__ = [
    # Service mesh
    "ServiceMeshType",
    "TrafficPolicy",
    "ServiceEndpoint",
    "LoadBalancingConfig",

    # Service discovery
    "ServiceRegistry",
    "ServiceDiscoveryClient",
    "ServiceHealthChecker",

    # Load balancing
    "LoadBalancer",
    "TrafficSplitter",
    "LoadBalancingAlgorithm",

    # Traffic management
    "TrafficManager",
    "RouteMatch",
    "TrafficSplit",
]
