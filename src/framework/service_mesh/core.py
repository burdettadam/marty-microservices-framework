"""
Core Service Mesh Abstractions

Fundamental interfaces and classes for service mesh integration,
service discovery, and mesh management.
"""

import asyncio
import builtins
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, dict, list

logger = logging.getLogger(__name__)


class ServiceMeshProvider(Enum):
    """Supported service mesh providers."""

    ISTIO = "istio"
    LINKERD = "linkerd"
    CONSUL_CONNECT = "consul_connect"
    ENVOY = "envoy"
    KUMA = "kuma"
    OPEN_SERVICE_MESH = "osm"


class HealthStatus(Enum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    LEAST_REQUESTS = "least_requests"
    RANDOM = "random"
    WEIGHTED = "weighted"
    CONSISTENT_HASH = "consistent_hash"
    LEAST_CONNECTIONS = "least_connections"


@dataclass
class ServiceMetadata:
    """Service metadata for mesh configuration."""

    name: str
    namespace: str = "default"
    version: str = "v1"
    labels: builtins.dict[str, str] = field(default_factory=dict)
    annotations: builtins.dict[str, str] = field(default_factory=dict)

    # Service characteristics
    protocol: str = "http"
    port: int = 80
    target_port: int | None = None

    # Mesh-specific metadata
    mesh_id: str | None = None
    sidecar_injected: bool = True
    external_service: bool = False

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "version": self.version,
            "labels": self.labels,
            "annotations": self.annotations,
            "protocol": self.protocol,
            "port": self.port,
            "target_port": self.target_port,
            "mesh_id": self.mesh_id,
            "sidecar_injected": self.sidecar_injected,
            "external_service": self.external_service,
        }


@dataclass
class ServiceEndpoint:
    """Service endpoint information."""

    service_name: str
    host: str
    port: int
    protocol: str = "http"
    health_status: HealthStatus = HealthStatus.UNKNOWN

    # Endpoint metadata
    endpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    zone: str | None = None
    region: str | None = None
    weight: int = 100

    # Health check information
    last_health_check: datetime | None = None
    health_check_failures: int = 0

    # Load balancing
    active_requests: int = 0
    total_requests: int = 0

    # Metadata
    labels: builtins.dict[str, str] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def is_healthy(self) -> bool:
        """Check if endpoint is healthy."""
        return self.health_status == HealthStatus.HEALTHY

    def update_health_status(self, status: HealthStatus) -> None:
        """Update health status."""
        self.health_status = status
        self.last_health_check = datetime.utcnow()

        if status != HealthStatus.HEALTHY:
            self.health_check_failures += 1
        else:
            self.health_check_failures = 0


@dataclass
class ServiceMeshConfig:
    """Service mesh configuration."""

    mesh_id: str
    provider: ServiceMeshProvider
    namespace: str = "istio-system"

    # Core configuration
    sidecar_injection_enabled: bool = True
    mtls_enabled: bool = True
    tracing_enabled: bool = True
    metrics_enabled: bool = True

    # Traffic management
    default_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    default_retries: int = 3
    circuit_breaker_enabled: bool = True

    # Security
    security_enabled: bool = True
    rbac_enabled: bool = True
    jwt_validation_enabled: bool = False

    # Observability
    telemetry_v2_enabled: bool = True
    prometheus_enabled: bool = True
    jaeger_enabled: bool = True
    grafana_enabled: bool = True

    # Provider-specific configuration
    provider_config: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mesh_id": self.mesh_id,
            "provider": self.provider.value,
            "namespace": self.namespace,
            "sidecar_injection_enabled": self.sidecar_injection_enabled,
            "mtls_enabled": self.mtls_enabled,
            "tracing_enabled": self.tracing_enabled,
            "metrics_enabled": self.metrics_enabled,
            "default_timeout": self.default_timeout.total_seconds(),
            "default_retries": self.default_retries,
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
            "security_enabled": self.security_enabled,
            "rbac_enabled": self.rbac_enabled,
            "jwt_validation_enabled": self.jwt_validation_enabled,
            "telemetry_v2_enabled": self.telemetry_v2_enabled,
            "prometheus_enabled": self.prometheus_enabled,
            "jaeger_enabled": self.jaeger_enabled,
            "grafana_enabled": self.grafana_enabled,
            "provider_config": self.provider_config,
        }


class ServiceRegistry(ABC):
    """Abstract service registry interface."""

    @abstractmethod
    async def register_service(
        self, metadata: ServiceMetadata, endpoints: builtins.list[ServiceEndpoint]
    ) -> None:
        """Register service in the mesh."""
        raise NotImplementedError

    @abstractmethod
    async def deregister_service(
        self, service_name: str, namespace: str = "default"
    ) -> None:
        """Deregister service from the mesh."""
        raise NotImplementedError

    @abstractmethod
    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> ServiceMetadata | None:
        """Get service metadata."""
        raise NotImplementedError

    @abstractmethod
    async def list_services(
        self, namespace: str = None
    ) -> builtins.list[ServiceMetadata]:
        """List all registered services."""
        raise NotImplementedError

    @abstractmethod
    async def update_service_endpoints(
        self,
        service_name: str,
        endpoints: builtins.list[ServiceEndpoint],
        namespace: str = "default",
    ) -> None:
        """Update service endpoints."""
        raise NotImplementedError


class ServiceDiscovery(ABC):
    """Abstract service discovery interface."""

    @abstractmethod
    async def discover_services(
        self, namespace: str = None
    ) -> builtins.list[ServiceMetadata]:
        """Discover available services."""
        raise NotImplementedError

    @abstractmethod
    async def get_service_endpoints(
        self, service_name: str, namespace: str = "default"
    ) -> builtins.list[ServiceEndpoint]:
        """Get endpoints for a service."""
        raise NotImplementedError

    @abstractmethod
    async def watch_service_changes(
        self, callback: Callable[[str, ServiceMetadata], None], namespace: str = None
    ) -> None:
        """Watch for service changes."""
        raise NotImplementedError

    @abstractmethod
    async def health_check_endpoint(self, endpoint: ServiceEndpoint) -> HealthStatus:
        """Perform health check on endpoint."""
        raise NotImplementedError


class InMemoryServiceRegistry(ServiceRegistry):
    """In-memory service registry implementation."""

    def __init__(self):
        self._services: builtins.dict[
            str, builtins.dict[str, ServiceMetadata]
        ] = {}  # namespace -> service_name -> metadata
        self._endpoints: builtins.dict[
            str, builtins.dict[str, builtins.list[ServiceEndpoint]]
        ] = {}  # namespace -> service_name -> endpoints
        self._lock = asyncio.Lock()

    async def register_service(
        self, metadata: ServiceMetadata, endpoints: builtins.list[ServiceEndpoint]
    ) -> None:
        """Register service."""
        async with self._lock:
            if metadata.namespace not in self._services:
                self._services[metadata.namespace] = {}
                self._endpoints[metadata.namespace] = {}

            self._services[metadata.namespace][metadata.name] = metadata
            self._endpoints[metadata.namespace][metadata.name] = endpoints.copy()

    async def deregister_service(
        self, service_name: str, namespace: str = "default"
    ) -> None:
        """Deregister service."""
        async with self._lock:
            if (
                namespace in self._services
                and service_name in self._services[namespace]
            ):
                del self._services[namespace][service_name]

            if (
                namespace in self._endpoints
                and service_name in self._endpoints[namespace]
            ):
                del self._endpoints[namespace][service_name]

    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> ServiceMetadata | None:
        """Get service metadata."""
        async with self._lock:
            return self._services.get(namespace, {}).get(service_name)

    async def list_services(
        self, namespace: str = None
    ) -> builtins.list[ServiceMetadata]:
        """List services."""
        async with self._lock:
            if namespace:
                return list(self._services.get(namespace, {}).values())

            all_services = []
            for ns_services in self._services.values():
                all_services.extend(ns_services.values())

            return all_services

    async def update_service_endpoints(
        self,
        service_name: str,
        endpoints: builtins.list[ServiceEndpoint],
        namespace: str = "default",
    ) -> None:
        """Update service endpoints."""
        async with self._lock:
            if namespace not in self._endpoints:
                self._endpoints[namespace] = {}

            self._endpoints[namespace][service_name] = endpoints.copy()


class InMemoryServiceDiscovery(ServiceDiscovery):
    """In-memory service discovery implementation."""

    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self._watchers: builtins.list[Callable] = []

    async def discover_services(
        self, namespace: str = None
    ) -> builtins.list[ServiceMetadata]:
        """Discover services."""
        return await self.registry.list_services(namespace)

    async def get_service_endpoints(
        self, service_name: str, namespace: str = "default"
    ) -> builtins.list[ServiceEndpoint]:
        """Get service endpoints."""
        if isinstance(self.registry, InMemoryServiceRegistry):
            async with self.registry._lock:
                return self.registry._endpoints.get(namespace, {}).get(service_name, [])

        return []

    async def watch_service_changes(
        self, callback: Callable[[str, ServiceMetadata], None], namespace: str = None
    ) -> None:
        """Watch service changes."""
        self._watchers.append(callback)

    async def health_check_endpoint(self, endpoint: ServiceEndpoint) -> HealthStatus:
        """Basic health check (always returns healthy for in-memory implementation)."""
        endpoint.last_health_check = datetime.utcnow()
        return HealthStatus.HEALTHY


class ServiceMeshManager(ABC):
    """Abstract service mesh manager interface."""

    def __init__(self, config: ServiceMeshConfig):
        self.config = config
        self.registry: ServiceRegistry | None = None
        self.discovery: ServiceDiscovery | None = None

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service mesh."""
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the service mesh."""
        raise NotImplementedError

    @abstractmethod
    async def apply_configuration(self, config: builtins.dict[str, Any]) -> None:
        """Apply mesh configuration."""
        raise NotImplementedError

    @abstractmethod
    async def get_mesh_status(self) -> builtins.dict[str, Any]:
        """Get mesh status."""
        raise NotImplementedError


class BasicServiceMeshManager(ServiceMeshManager):
    """Basic service mesh manager implementation."""

    def __init__(self, config: ServiceMeshConfig):
        super().__init__(config)
        self.registry = InMemoryServiceRegistry()
        self.discovery = InMemoryServiceDiscovery(self.registry)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize mesh."""
        self._initialized = True
        logger.info(f"Service mesh {self.config.mesh_id} initialized")

    async def shutdown(self) -> None:
        """Shutdown mesh."""
        self._initialized = False
        logger.info(f"Service mesh {self.config.mesh_id} shutdown")

    async def apply_configuration(self, config: builtins.dict[str, Any]) -> None:
        """Apply configuration."""
        logger.info(f"Applied configuration to mesh {self.config.mesh_id}")

    async def get_mesh_status(self) -> builtins.dict[str, Any]:
        """Get mesh status."""
        services = await self.registry.list_services()

        return {
            "mesh_id": self.config.mesh_id,
            "provider": self.config.provider.value,
            "initialized": self._initialized,
            "services_count": len(services),
            "namespace": self.config.namespace,
            "mtls_enabled": self.config.mtls_enabled,
            "tracing_enabled": self.config.tracing_enabled,
            "metrics_enabled": self.config.metrics_enabled,
        }


class ServiceMeshError(Exception):
    """Service mesh related error."""


class ServiceRegistrationError(ServiceMeshError):
    """Service registration error."""


class ServiceDiscoveryError(ServiceMeshError):
    """Service discovery error."""


# Utility functions


def create_service_metadata(
    name: str,
    namespace: str = "default",
    version: str = "v1",
    port: int = 80,
    protocol: str = "http",
    **kwargs,
) -> ServiceMetadata:
    """Create service metadata."""
    return ServiceMetadata(
        name=name,
        namespace=namespace,
        version=version,
        port=port,
        protocol=protocol,
        **kwargs,
    )


def create_service_endpoint(
    service_name: str, host: str, port: int, protocol: str = "http", **kwargs
) -> ServiceEndpoint:
    """Create service endpoint."""
    return ServiceEndpoint(
        service_name=service_name, host=host, port=port, protocol=protocol, **kwargs
    )


def create_mesh_config(
    mesh_id: str, provider: ServiceMeshProvider, **kwargs
) -> ServiceMeshConfig:
    """Create service mesh configuration."""
    return ServiceMeshConfig(mesh_id=mesh_id, provider=provider, **kwargs)


async def register_service_with_endpoints(
    registry: ServiceRegistry,
    service_name: str,
    endpoints: builtins.list[str],
    namespace: str = "default",
    port: int = 80,
    protocol: str = "http",
) -> None:
    """Register service with multiple endpoints."""
    metadata = create_service_metadata(
        name=service_name, namespace=namespace, port=port, protocol=protocol
    )

    endpoint_objects = []
    for endpoint_host in endpoints:
        endpoint = create_service_endpoint(
            service_name=service_name, host=endpoint_host, port=port, protocol=protocol
        )
        endpoint_objects.append(endpoint)

    await registry.register_service(metadata, endpoint_objects)
