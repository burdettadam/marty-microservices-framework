"""
Service Mesh Integration Framework

Comprehensive service mesh integration with Istio/Envoy support,
traffic management, security policies, observability, and distributed tracing.
"""

# Configuration management
from .config import (
    ConfigSynchronizer,
    MeshConfigValidator,
    ObservabilityConfiguration,
    PolicyConfiguration,
    SecurityConfiguration,
    ServiceMeshConfiguration,
    TrafficConfiguration,
)

# Core service mesh abstractions
from .core import (
    HealthStatus,
    LoadBalancingStrategy,
    ServiceDiscovery,
    ServiceEndpoint,
    ServiceMeshConfig,
    ServiceMeshProvider,
    ServiceMetadata,
    ServiceRegistry,
)

# Envoy integration
from .envoy import (
    EnvoyCluster,
    EnvoyConfig,
    EnvoyExtension,
    EnvoyFilter,
    EnvoyListener,
    EnvoyProvider,
    EnvoyProxy,
    EnvoyRoute,
    xDSClient,
    xDSServer,
)

# Utilities and factories
from .factory import (
    ServiceMeshFactory,
    create_envoy_proxy,
    create_istio_mesh,
    create_observability_manager,
    create_security_manager,
    create_traffic_manager,
)

# Istio integration
from .istio import (
    CitadelClient,
    GalleyClient,
    IstioConfigManager,
    IstioOperator,
    IstioPolicy,
    IstioProvider,
    IstioResource,
    IstioServiceMesh,
    PilotClient,
)

# Observability and monitoring
from .observability import (
    AlertManager,
    DistributedTracing,
    LoggingManager,
    MetricsCollector,
    MetricsExporter,
    ObservabilityManager,
    ServiceMonitor,
    Telemetry,
    TraceExporter,
    TracingManager,
)

# Security policies
from .security import (
    AuthenticationPolicy,
    AuthorizationPolicy,
    CertificateManager,
    JWTPolicy,
    PeerAuthentication,
    RBACPolicy,
    RequestAuthentication,
    SecurityContext,
    SecurityPolicyManager,
    TLSConfig,
)

# Traffic management
from .traffic_management import (
    BlueGreenDeployment,
    CanaryDeployment,
    CircuitBreaker,
    DestinationRule,
    Gateway,
    LoadBalancer,
    RetryPolicy,
    ServiceEntry,
    TimeoutPolicy,
    TrafficManager,
    TrafficPolicy,
    VirtualService,
)

__all__ = [
    # Core
    "ServiceMeshProvider",
    "ServiceMeshConfig",
    "ServiceRegistry",
    "ServiceDiscovery",
    "ServiceEndpoint",
    "ServiceMetadata",
    "HealthStatus",
    "LoadBalancingStrategy",
    # Traffic Management
    "TrafficManager",
    "VirtualService",
    "DestinationRule",
    "Gateway",
    "ServiceEntry",
    "TrafficPolicy",
    "CircuitBreaker",
    "RetryPolicy",
    "TimeoutPolicy",
    "LoadBalancer",
    "CanaryDeployment",
    "BlueGreenDeployment",
    # Security
    "SecurityPolicyManager",
    "AuthenticationPolicy",
    "AuthorizationPolicy",
    "PeerAuthentication",
    "RequestAuthentication",
    "SecurityContext",
    "TLSConfig",
    "CertificateManager",
    "JWTPolicy",
    "RBACPolicy",
    # Observability
    "ObservabilityManager",
    "MetricsCollector",
    "TracingManager",
    "LoggingManager",
    "ServiceMonitor",
    "DistributedTracing",
    "Telemetry",
    "MetricsExporter",
    "TraceExporter",
    "AlertManager",
    # Istio
    "IstioProvider",
    "IstioConfigManager",
    "IstioServiceMesh",
    "PilotClient",
    "CitadelClient",
    "GalleyClient",
    "IstioOperator",
    "IstioResource",
    "IstioPolicy",
    # Envoy
    "EnvoyProvider",
    "EnvoyProxy",
    "EnvoyConfig",
    "EnvoyFilter",
    "EnvoyCluster",
    "EnvoyListener",
    "EnvoyRoute",
    "EnvoyExtension",
    "xDSServer",
    "xDSClient",
    # Configuration
    "ServiceMeshConfiguration",
    "PolicyConfiguration",
    "SecurityConfiguration",
    "ObservabilityConfiguration",
    "TrafficConfiguration",
    "MeshConfigValidator",
    "ConfigSynchronizer",
    # Factory
    "ServiceMeshFactory",
    "create_istio_mesh",
    "create_envoy_proxy",
    "create_traffic_manager",
    "create_security_manager",
    "create_observability_manager",
]
