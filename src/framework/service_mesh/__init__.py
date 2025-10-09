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
    "AlertManager",
    "AuthenticationPolicy",
    "AuthorizationPolicy",
    "BlueGreenDeployment",
    "CanaryDeployment",
    "CertificateManager",
    "CircuitBreaker",
    "CitadelClient",
    "ConfigSynchronizer",
    "DestinationRule",
    "DistributedTracing",
    "EnvoyCluster",
    "EnvoyConfig",
    "EnvoyExtension",
    "EnvoyFilter",
    "EnvoyListener",
    # Envoy
    "EnvoyProvider",
    "EnvoyProxy",
    "EnvoyRoute",
    "GalleyClient",
    "Gateway",
    "HealthStatus",
    "IstioConfigManager",
    "IstioOperator",
    "IstioPolicy",
    # Istio
    "IstioProvider",
    "IstioResource",
    "IstioServiceMesh",
    "JWTPolicy",
    "LoadBalancer",
    "LoadBalancingStrategy",
    "LoggingManager",
    "MeshConfigValidator",
    "MetricsCollector",
    "MetricsExporter",
    "ObservabilityConfiguration",
    # Observability
    "ObservabilityManager",
    "PeerAuthentication",
    "PilotClient",
    "PolicyConfiguration",
    "RBACPolicy",
    "RequestAuthentication",
    "RetryPolicy",
    "SecurityConfiguration",
    "SecurityContext",
    # Security
    "SecurityPolicyManager",
    "ServiceDiscovery",
    "ServiceEndpoint",
    "ServiceEntry",
    "ServiceMeshConfig",
    # Configuration
    "ServiceMeshConfiguration",
    # Factory
    "ServiceMeshFactory",
    # Core
    "ServiceMeshProvider",
    "ServiceMetadata",
    "ServiceMonitor",
    "ServiceRegistry",
    "TLSConfig",
    "Telemetry",
    "TimeoutPolicy",
    "TraceExporter",
    "TracingManager",
    "TrafficConfiguration",
    # Traffic Management
    "TrafficManager",
    "TrafficPolicy",
    "VirtualService",
    "create_envoy_proxy",
    "create_istio_mesh",
    "create_observability_manager",
    "create_security_manager",
    "create_traffic_manager",
    "xDSClient",
    "xDSServer",
]
