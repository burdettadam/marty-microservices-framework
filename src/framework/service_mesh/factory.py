"""
Service Mesh Factory and Utilities

Factory functions and utilities for creating and managing
service mesh components and configurations.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .core import (
    BasicServiceMeshManager,
    InMemoryServiceDiscovery,
    InMemoryServiceRegistry,
    ServiceDiscovery,
    ServiceEndpoint,
    ServiceMeshConfig,
    ServiceMeshManager,
    ServiceMeshProvider,
    ServiceMetadata,
    ServiceRegistry,
    create_service_endpoint,
    create_service_metadata,
)
from .observability import (
    AlertManager,
    LoggingManager,
    MetricsCollector,
    MetricsExporter,
    ObservabilityManager,
    ServiceMonitor,
    Telemetry,
    TraceExporter,
    TracingManager,
)
from .security import (
    AuthenticationPolicy,
    AuthorizationPolicy,
    CertificateManager,
    JWTPolicy,
    PeerAuthentication,
    RequestAuthentication,
    SecurityContext,
    SecurityPolicyManager,
    TLSConfig,
    create_security_context,
)
from .traffic_management import (
    BlueGreenDeployment,
    CanaryDeployment,
    CircuitBreaker,
    ConnectionPool,
    DestinationRule,
    Gateway,
    HTTPRoute,
    LoadBalancer,
    RetryPolicy,
    ServiceEntry,
    TimeoutPolicy,
    TrafficManager,
    VirtualService,
)

logger = logging.getLogger(__name__)


class ServiceMeshFactory:
    """Factory for creating service mesh components."""

    @staticmethod
    def create_mesh_config(
        mesh_id: str, provider: ServiceMeshProvider, **kwargs
    ) -> ServiceMeshConfig:
        """Create service mesh configuration."""
        return ServiceMeshConfig(mesh_id=mesh_id, provider=provider, **kwargs)

    @staticmethod
    def create_mesh_manager(config: ServiceMeshConfig) -> ServiceMeshManager:
        """Create service mesh manager."""
        return BasicServiceMeshManager(config)

    @staticmethod
    def create_service_registry() -> ServiceRegistry:
        """Create service registry."""
        return InMemoryServiceRegistry()

    @staticmethod
    def create_service_discovery(registry: ServiceRegistry) -> ServiceDiscovery:
        """Create service discovery."""
        return InMemoryServiceDiscovery(registry)

    @staticmethod
    def create_traffic_manager() -> TrafficManager:
        """Create traffic manager."""
        return TrafficManager()

    @staticmethod
    def create_security_manager() -> SecurityPolicyManager:
        """Create security policy manager."""
        return SecurityPolicyManager()

    @staticmethod
    def create_observability_manager() -> ObservabilityManager:
        """Create observability manager."""
        return ObservabilityManager()

    @staticmethod
    def create_load_balancer(strategy: str = "round_robin") -> LoadBalancer:
        """Create load balancer."""
        from .core import LoadBalancingStrategy

        strategy_enum = LoadBalancingStrategy(strategy)
        return LoadBalancer(strategy_enum)

    @staticmethod
    def create_circuit_breaker(
        failure_threshold: int = 5, recovery_timeout_seconds: int = 60
    ) -> CircuitBreaker:
        """Create circuit breaker."""
        from datetime import timedelta

        return CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=timedelta(seconds=recovery_timeout_seconds),
        )


class ServiceMeshBuilder:
    """Builder for comprehensive service mesh setup."""

    def __init__(self, mesh_id: str, provider: ServiceMeshProvider):
        self.config = ServiceMeshConfig(mesh_id=mesh_id, provider=provider)
        self.mesh_manager: Optional[ServiceMeshManager] = None
        self.traffic_manager: Optional[TrafficManager] = None
        self.security_manager: Optional[SecurityPolicyManager] = None
        self.observability_manager: Optional[ObservabilityManager] = None

        self._services: List[Dict[str, Any]] = []
        self._virtual_services: List[VirtualService] = []
        self._security_policies: List[Dict[str, Any]] = []

    def with_mtls(self, enabled: bool = True) -> "ServiceMeshBuilder":
        """Configure mTLS."""
        self.config.mtls_enabled = enabled
        return self

    def with_tracing(self, enabled: bool = True) -> "ServiceMeshBuilder":
        """Configure tracing."""
        self.config.tracing_enabled = enabled
        return self

    def with_metrics(self, enabled: bool = True) -> "ServiceMeshBuilder":
        """Configure metrics."""
        self.config.metrics_enabled = enabled
        return self

    def with_security(self, enabled: bool = True) -> "ServiceMeshBuilder":
        """Configure security."""
        self.config.security_enabled = enabled
        return self

    def add_service(
        self,
        name: str,
        namespace: str = "default",
        endpoints: List[str] = None,
        port: int = 80,
    ) -> "ServiceMeshBuilder":
        """Add service to mesh."""
        service_config = {
            "name": name,
            "namespace": namespace,
            "endpoints": endpoints or [],
            "port": port,
        }
        self._services.append(service_config)
        return self

    def add_traffic_routing(
        self, service_name: str, routes: List[Dict[str, Any]]
    ) -> "ServiceMeshBuilder":
        """Add traffic routing configuration."""
        http_routes = []
        for route_config in routes:
            route = HTTPRoute(
                destination=route_config.get("destination", service_name),
                weight=route_config.get("weight", 100),
                uri_prefix=route_config.get("uri_prefix"),
            )
            http_routes.append(route)

        virtual_service = VirtualService(
            name=f"{service_name}-vs", hosts=[service_name], http_routes=http_routes
        )
        self._virtual_services.append(virtual_service)
        return self

    def add_security_policy(self, policy_type: str, **kwargs) -> "ServiceMeshBuilder":
        """Add security policy."""
        policy_config = {"type": policy_type, **kwargs}
        self._security_policies.append(policy_config)
        return self

    async def build(self) -> Dict[str, Any]:
        """Build the service mesh."""
        # Create managers
        self.mesh_manager = ServiceMeshFactory.create_mesh_manager(self.config)
        self.traffic_manager = ServiceMeshFactory.create_traffic_manager()
        self.security_manager = ServiceMeshFactory.create_security_manager()
        self.observability_manager = ServiceMeshFactory.create_observability_manager()

        # Initialize mesh
        await self.mesh_manager.initialize()
        await self.observability_manager.initialize()

        # Register services
        for service_config in self._services:
            metadata = create_service_metadata(
                name=service_config["name"],
                namespace=service_config["namespace"],
                port=service_config["port"],
            )

            endpoints = []
            for endpoint_host in service_config["endpoints"]:
                endpoint = create_service_endpoint(
                    service_name=service_config["name"],
                    host=endpoint_host,
                    port=service_config["port"],
                )
                endpoints.append(endpoint)

            await self.mesh_manager.registry.register_service(metadata, endpoints)

        # Apply traffic routing
        for virtual_service in self._virtual_services:
            await self.traffic_manager.create_virtual_service(virtual_service)

        # Apply security policies
        for policy_config in self._security_policies:
            await self._apply_security_policy(policy_config)

        return {
            "mesh_manager": self.mesh_manager,
            "traffic_manager": self.traffic_manager,
            "security_manager": self.security_manager,
            "observability_manager": self.observability_manager,
            "config": self.config.to_dict(),
        }

    async def _apply_security_policy(self, policy_config: Dict[str, Any]) -> None:
        """Apply security policy."""
        policy_type = policy_config["type"]

        if policy_type == "peer_authentication":
            policy = PeerAuthentication(
                name=policy_config.get("name", "default-peer-auth"),
                namespace=policy_config.get("namespace", "default"),
            )
            await self.security_manager.create_peer_authentication(policy)

        elif policy_type == "authorization":
            policy = AuthorizationPolicy(
                name=policy_config.get("name", "default-authz"),
                namespace=policy_config.get("namespace", "default"),
            )
            await self.security_manager.create_authorization_policy(policy)


def create_istio_mesh(
    mesh_id: str, namespace: str = "istio-system"
) -> ServiceMeshBuilder:
    """Create Istio service mesh builder."""
    builder = ServiceMeshBuilder(mesh_id, ServiceMeshProvider.ISTIO)
    builder.config.namespace = namespace
    builder.config.mtls_enabled = True
    builder.config.tracing_enabled = True
    builder.config.metrics_enabled = True
    return builder


def create_envoy_proxy(service_name: str, **kwargs) -> Dict[str, Any]:
    """Create Envoy proxy configuration."""
    return {
        "service_name": service_name,
        "proxy_type": "envoy",
        "configuration": {
            "admin": {
                "access_log_path": "/tmp/admin_access.log",
                "address": {
                    "socket_address": {
                        "protocol": "TCP",
                        "address": "127.0.0.1",
                        "port_value": 9901,
                    }
                },
            },
            "static_resources": {"listeners": [], "clusters": []},
        },
        **kwargs,
    }


async def create_traffic_manager() -> TrafficManager:
    """Create configured traffic manager."""
    manager = TrafficManager()
    logger.info("Traffic manager created")
    return manager


async def create_security_manager() -> SecurityPolicyManager:
    """Create configured security manager."""
    manager = SecurityPolicyManager()

    # Initialize CA certificate
    manager.certificate_manager.generate_ca_certificate()

    logger.info("Security manager created with CA certificate")
    return manager


async def create_observability_manager() -> ObservabilityManager:
    """Create configured observability manager."""
    manager = ObservabilityManager()
    await manager.initialize()

    # Add default alerts
    from .observability import create_alert

    high_error_rate_alert = create_alert(
        name="high_error_rate",
        condition="error_rate",
        threshold=0.05,  # 5% error rate
        severity="critical",
    )
    manager.alert_manager.register_alert(high_error_rate_alert)

    high_latency_alert = create_alert(
        name="high_latency",
        condition="response_time",
        threshold=1000,  # 1 second
        severity="warning",
    )
    manager.alert_manager.register_alert(high_latency_alert)

    logger.info("Observability manager created with default alerts")
    return manager


class MeshTopology:
    """Service mesh topology management."""

    def __init__(self):
        self._services: Dict[str, ServiceMetadata] = {}
        self._connections: Dict[str, List[str]] = {}
        self._dependencies: Dict[str, List[str]] = {}

    def add_service(self, service: ServiceMetadata) -> None:
        """Add service to topology."""
        service_key = f"{service.namespace}/{service.name}"
        self._services[service_key] = service
        if service_key not in self._connections:
            self._connections[service_key] = []

    def add_connection(self, from_service: str, to_service: str) -> None:
        """Add service connection."""
        if from_service not in self._connections:
            self._connections[from_service] = []

        if to_service not in self._connections[from_service]:
            self._connections[from_service].append(to_service)

    def add_dependency(self, service: str, dependency: str) -> None:
        """Add service dependency."""
        if service not in self._dependencies:
            self._dependencies[service] = []

        if dependency not in self._dependencies[service]:
            self._dependencies[service].append(dependency)

    def get_topology(self) -> Dict[str, Any]:
        """Get mesh topology."""
        return {
            "services": {k: v.to_dict() for k, v in self._services.items()},
            "connections": self._connections,
            "dependencies": self._dependencies,
            "service_count": len(self._services),
            "connection_count": sum(len(conns) for conns in self._connections.values()),
        }

    def get_service_graph(self) -> Dict[str, List[str]]:
        """Get service dependency graph."""
        return self._dependencies.copy()


class MeshConfiguration:
    """Comprehensive mesh configuration management."""

    def __init__(self):
        self.global_config: Dict[str, Any] = {}
        self.service_configs: Dict[str, Dict[str, Any]] = {}
        self.policy_configs: Dict[str, Dict[str, Any]] = {}

    def set_global_config(self, key: str, value: Any) -> None:
        """Set global configuration."""
        self.global_config[key] = value

    def set_service_config(self, service: str, config: Dict[str, Any]) -> None:
        """Set service-specific configuration."""
        self.service_configs[service] = config

    def set_policy_config(self, policy_name: str, config: Dict[str, Any]) -> None:
        """Set policy configuration."""
        self.policy_configs[policy_name] = config

    def get_configuration(self) -> Dict[str, Any]:
        """Get complete configuration."""
        return {
            "global": self.global_config,
            "services": self.service_configs,
            "policies": self.policy_configs,
        }

    def apply_defaults(self) -> None:
        """Apply default configuration values."""
        defaults = {
            "mtls_mode": "STRICT",
            "tracing_enabled": True,
            "metrics_enabled": True,
            "default_timeout": 30,
            "retry_attempts": 3,
            "circuit_breaker_enabled": True,
        }

        for key, value in defaults.items():
            if key not in self.global_config:
                self.global_config[key] = value


# Utility functions for quick setup


async def quick_setup_mesh(
    mesh_id: str, services: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Quick setup for service mesh with services."""
    builder = create_istio_mesh(mesh_id)

    # Add services
    for service_config in services:
        builder.add_service(
            name=service_config["name"],
            namespace=service_config.get("namespace", "default"),
            endpoints=service_config.get("endpoints", []),
            port=service_config.get("port", 80),
        )

        # Add basic routing if specified
        if "routes" in service_config:
            builder.add_traffic_routing(
                service_config["name"], service_config["routes"]
            )

    # Add basic security
    builder.add_security_policy("peer_authentication", name="default-peer-auth")

    return await builder.build()


async def setup_canary_deployment(
    service_name: str, stable_version: str, canary_version: str, canary_weight: int = 10
) -> CanaryDeployment:
    """Setup canary deployment for service."""
    canary = CanaryDeployment(service_name)
    virtual_service = canary.create_traffic_split(
        canary_version=canary_version,
        stable_version=stable_version,
        canary_weight=canary_weight,
    )

    logger.info(
        f"Canary deployment setup for {service_name}: {canary_weight}% to {canary_version}"
    )
    return canary


async def setup_blue_green_deployment(
    service_name: str, blue_version: str, green_version: str
) -> BlueGreenDeployment:
    """Setup blue-green deployment for service."""
    blue_green = BlueGreenDeployment(service_name)
    virtual_service = blue_green.setup_deployment(blue_version, green_version)

    logger.info(
        f"Blue-green deployment setup for {service_name}: blue={blue_version}, green={green_version}"
    )
    return blue_green


def create_mesh_topology() -> MeshTopology:
    """Create mesh topology manager."""
    return MeshTopology()


def create_mesh_configuration() -> MeshConfiguration:
    """Create mesh configuration manager."""
    config = MeshConfiguration()
    config.apply_defaults()
    return config
