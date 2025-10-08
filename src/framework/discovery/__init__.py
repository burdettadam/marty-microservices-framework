"""
Service Discovery & Load Balancing Framework

Enterprise-grade service discovery and load balancing framework providing
dynamic service registration, health monitoring, intelligent routing,
and adaptive load balancing strategies.

Key Components:
- Service Registry: Central registry for service instances with metadata
- Health Monitoring: Continuous health checks and availability tracking
- Load Balancing: Multiple algorithms (round-robin, weighted, least-connections, etc.)
- Service Discovery: Client-side and server-side discovery patterns
- Circuit Breaker Integration: Fault tolerance with circuit breaker patterns
- Dynamic Configuration: Runtime updates and adaptive behaviors
- Metrics & Monitoring: Comprehensive observability and performance tracking

Usage:
    from framework.discovery import ServiceRegistry, LoadBalancer, ServiceDiscovery
    from framework.discovery import ServiceInstance, HealthCheck, LoadBalancingStrategy

    # Create service registry
    registry = ServiceRegistry()

    # Register service instance
    instance = ServiceInstance(
        name="user-service",
        host="localhost",
        port=8080,
        health_check_url="/health"
    )
    await registry.register(instance)

    # Create load balancer
    load_balancer = LoadBalancer(
        strategy=LoadBalancingStrategy.ROUND_ROBIN,
        health_check_enabled=True
    )

    # Discover and route to services
    discovery = ServiceDiscovery(registry, load_balancer)
    target = await discovery.discover("user-service")
"""

# Circuit breaker integration
from .circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitBreakerState,
    ServiceCircuitBreaker,
)

# Core service discovery components
from .core import (
    HealthCheck,
    HealthStatus,
    ServiceInstance,
    ServiceMetadata,
    ServiceRegistryConfig,
)

# Service discovery patterns
from .discovery import (
    ClientSideDiscovery,
    DiscoveryPattern,
    ServerSideDiscovery,
    ServiceDiscovery,
    ServiceDiscoveryConfig,
)

# Health monitoring and checks
from .health import (
    CustomHealthCheck,
    HealthCheckConfig,
    HealthCheckResult,
    HealthCheckType,
    HealthMetrics,
    HealthMonitor,
    HTTPHealthCheck,
    TCPHealthCheck,
)

# Load balancing strategies and algorithms
from .load_balancing import (
    AdaptiveBalancer,
    ConsistentHashBalancer,
    HealthBasedBalancer,
    LeastConnectionsBalancer,
    LoadBalancer,
    LoadBalancingConfig,
    LoadBalancingStrategy,
    RandomBalancer,
    RoundRobinBalancer,
    WeightedLeastConnectionsBalancer,
    WeightedRoundRobinBalancer,
)

# Management and orchestration
from .manager import DiscoveryManagerState
from .manager import ServiceDiscoveryConfig as ManagerConfig
from .manager import ServiceDiscoveryManager

# Service mesh integration
from .mesh import (
    RoutingRule,
    SecurityPolicy,
    ServiceMesh,
    ServiceMeshConfig,
    TrafficPolicy,
)

# Monitoring and metrics
from .monitoring import (
    DiscoveryMetrics,
    LoadBalancingMetrics,
    MetricsCollector,
    ServiceMetrics,
)

# Service registry implementations
from .registry import (
    ConsulServiceRegistry,
    EtcdServiceRegistry,
    InMemoryServiceRegistry,
    KubernetesServiceRegistry,
    ServiceRegistry,
)

__all__ = [
    # Core components
    "ServiceInstance",
    "ServiceMetadata",
    "HealthStatus",
    "HealthCheck",
    "ServiceRegistryConfig",
    # Service registry
    "ServiceRegistry",
    "InMemoryServiceRegistry",
    "ConsulServiceRegistry",
    "EtcdServiceRegistry",
    "KubernetesServiceRegistry",
    # Load balancing
    "LoadBalancer",
    "LoadBalancingStrategy",
    "LoadBalancingConfig",
    "RoundRobinBalancer",
    "WeightedRoundRobinBalancer",
    "LeastConnectionsBalancer",
    "WeightedLeastConnectionsBalancer",
    "ConsistentHashBalancer",
    "RandomBalancer",
    "HealthBasedBalancer",
    "AdaptiveBalancer",
    # Service discovery
    "ServiceDiscovery",
    "ClientSideDiscovery",
    "ServerSideDiscovery",
    "ServiceDiscoveryConfig",
    "DiscoveryPattern",
    # Health monitoring
    "HealthMonitor",
    "HealthCheckConfig",
    "HealthCheckType",
    "HTTPHealthCheck",
    "TCPHealthCheck",
    "CustomHealthCheck",
    "HealthCheckResult",
    "HealthMetrics",
    # Circuit breaker
    "ServiceCircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerState",
    "CircuitBreakerMetrics",
    # Service mesh
    "ServiceMesh",
    "ServiceMeshConfig",
    "TrafficPolicy",
    "RoutingRule",
    "SecurityPolicy",
    # Monitoring
    "DiscoveryMetrics",
    "LoadBalancingMetrics",
    "ServiceMetrics",
    "MetricsCollector",
    # Management
    "ServiceDiscoveryManager",
    "ManagerConfig",
    "DiscoveryManagerState",
]
