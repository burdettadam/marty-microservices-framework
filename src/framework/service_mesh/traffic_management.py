"""
Traffic Management Components

Advanced traffic management features including virtual services,
destination rules, gateways, circuit breakers, and deployment strategies.
"""

import asyncio
import logging
import random
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

from .core import HealthStatus, LoadBalancingStrategy, ServiceEndpoint, ServiceMetadata

logger = logging.getLogger(__name__)


class TrafficSplitType(Enum):
    """Traffic split types for deployment strategies."""

    WEIGHT_BASED = "weight_based"
    HEADER_BASED = "header_based"
    COOKIE_BASED = "cookie_based"
    USER_BASED = "user_based"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class HTTPRoute:
    """HTTP route configuration."""

    match: Dict[str, Any] = field(default_factory=dict)
    destination: str = ""
    weight: int = 100
    headers: Dict[str, str] = field(default_factory=dict)

    # Advanced routing
    uri_prefix: Optional[str] = None
    uri_exact: Optional[str] = None
    uri_regex: Optional[str] = None
    method: Optional[str] = None

    # Fault injection
    fault_delay: Optional[timedelta] = None
    fault_abort_percent: float = 0.0
    fault_abort_status: int = 500

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "match": self.match,
            "destination": self.destination,
            "weight": self.weight,
            "headers": self.headers,
            "uri_prefix": self.uri_prefix,
            "uri_exact": self.uri_exact,
            "uri_regex": self.uri_regex,
            "method": self.method,
            "fault_delay": self.fault_delay.total_seconds()
            if self.fault_delay
            else None,
            "fault_abort_percent": self.fault_abort_percent,
            "fault_abort_status": self.fault_abort_status,
        }


@dataclass
class VirtualService:
    """Virtual service for traffic routing."""

    name: str
    namespace: str = "default"
    hosts: List[str] = field(default_factory=list)
    gateways: List[str] = field(default_factory=list)
    http_routes: List[HTTPRoute] = field(default_factory=list)

    # TCP/TLS routes
    tcp_routes: List[Dict[str, Any]] = field(default_factory=list)
    tls_routes: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def add_http_route(self, route: HTTPRoute) -> None:
        """Add HTTP route."""
        self.http_routes.append(route)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "hosts": self.hosts,
            "gateways": self.gateways,
            "http_routes": [route.to_dict() for route in self.http_routes],
            "tcp_routes": self.tcp_routes,
            "tls_routes": self.tls_routes,
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class ConnectionPool:
    """Connection pool settings."""

    # TCP settings
    max_connections: int = 100
    connect_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=10))
    tcp_keep_alive: bool = True

    # HTTP settings
    http1_max_pending_requests: int = 100
    http2_max_requests: int = 1000
    max_requests_per_connection: int = 10
    max_retries: int = 3
    idle_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_connections": self.max_connections,
            "connect_timeout": self.connect_timeout.total_seconds(),
            "tcp_keep_alive": self.tcp_keep_alive,
            "http1_max_pending_requests": self.http1_max_pending_requests,
            "http2_max_requests": self.http2_max_requests,
            "max_requests_per_connection": self.max_requests_per_connection,
            "max_retries": self.max_retries,
            "idle_timeout": self.idle_timeout.total_seconds(),
        }


@dataclass
class DestinationRule:
    """Destination rule for service configuration."""

    name: str
    host: str
    namespace: str = "default"

    # Traffic policy
    load_balancer: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    connection_pool: Optional[ConnectionPool] = None
    outlier_detection: Optional[Dict[str, Any]] = None

    # Subsets for version-based routing
    subsets: List[Dict[str, Any]] = field(default_factory=list)

    # TLS settings
    tls_mode: str = "ISTIO_MUTUAL"
    tls_client_certificate: Optional[str] = None
    tls_private_key: Optional[str] = None
    tls_ca_certificates: Optional[str] = None

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def add_subset(
        self, name: str, labels: Dict[str, str], traffic_policy: Dict[str, Any] = None
    ) -> None:
        """Add subset configuration."""
        subset = {
            "name": name,
            "labels": labels,
            "traffic_policy": traffic_policy or {},
        }
        self.subsets.append(subset)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "host": self.host,
            "namespace": self.namespace,
            "load_balancer": self.load_balancer.value,
            "connection_pool": self.connection_pool.to_dict()
            if self.connection_pool
            else None,
            "outlier_detection": self.outlier_detection,
            "subsets": self.subsets,
            "tls_mode": self.tls_mode,
            "tls_client_certificate": self.tls_client_certificate,
            "tls_private_key": self.tls_private_key,
            "tls_ca_certificates": self.tls_ca_certificates,
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class Gateway:
    """Gateway configuration for ingress/egress traffic."""

    name: str
    namespace: str = "default"
    selector: Dict[str, str] = field(default_factory=dict)
    servers: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def add_server(
        self,
        port: int,
        hosts: List[str],
        protocol: str = "HTTP",
        tls_mode: str = None,
        credential_name: str = None,
    ) -> None:
        """Add server configuration."""
        server = {
            "port": {
                "number": port,
                "name": f"{protocol.lower()}-{port}",
                "protocol": protocol,
            },
            "hosts": hosts,
        }

        if tls_mode:
            server["tls"] = {"mode": tls_mode, "credential_name": credential_name}

        self.servers.append(server)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "namespace": self.namespace,
            "selector": self.selector,
            "servers": self.servers,
            "labels": self.labels,
            "annotations": self.annotations,
        }


@dataclass
class ServiceEntry:
    """Service entry for external services."""

    name: str
    hosts: List[str]
    namespace: str = "default"
    location: str = "MESH_EXTERNAL"  # MESH_EXTERNAL or MESH_INTERNAL
    resolution: str = "DNS"  # DNS, STATIC, or NONE

    # Endpoints for static resolution
    endpoints: List[Dict[str, Any]] = field(default_factory=list)

    # Ports
    ports: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    def add_port(self, number: int, name: str, protocol: str = "HTTP") -> None:
        """Add port configuration."""
        port = {"number": number, "name": name, "protocol": protocol}
        self.ports.append(port)

    def add_endpoint(self, address: str, ports: Dict[str, int] = None) -> None:
        """Add endpoint for static resolution."""
        endpoint = {"address": address, "ports": ports or {}}
        self.endpoints.append(endpoint)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "hosts": self.hosts,
            "namespace": self.namespace,
            "location": self.location,
            "resolution": self.resolution,
            "endpoints": self.endpoints,
            "ports": self.ports,
            "labels": self.labels,
            "annotations": self.annotations,
        }


class CircuitBreaker:
    """Circuit breaker implementation."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: timedelta = timedelta(seconds=60),
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise Exception("Circuit breaker is OPEN")

            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise Exception("Circuit breaker is HALF_OPEN - max calls exceeded")
                self.half_open_calls += 1

        try:
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure()
            raise e

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED

            self.failure_count = 0
            self.last_failure_time = None

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if self.last_failure_time is None:
            return True

        return datetime.utcnow() - self.last_failure_time >= self.recovery_timeout

    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time.isoformat()
            if self.last_failure_time
            else None,
            "half_open_calls": self.half_open_calls
            if self.state == CircuitBreakerState.HALF_OPEN
            else 0,
        }


@dataclass
class RetryPolicy:
    """Retry policy configuration."""

    attempts: int = 3
    per_try_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=5))
    retry_on: List[str] = field(
        default_factory=lambda: ["5xx", "gateway-error", "connect-failure"]
    )
    backoff_base_interval: timedelta = field(
        default_factory=lambda: timedelta(seconds=1)
    )
    backoff_max_interval: timedelta = field(
        default_factory=lambda: timedelta(seconds=10)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attempts": self.attempts,
            "per_try_timeout": self.per_try_timeout.total_seconds(),
            "retry_on": self.retry_on,
            "backoff_base_interval": self.backoff_base_interval.total_seconds(),
            "backoff_max_interval": self.backoff_max_interval.total_seconds(),
        }


@dataclass
class TimeoutPolicy:
    """Timeout policy configuration."""

    request_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    idle_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_timeout": self.request_timeout.total_seconds(),
            "idle_timeout": self.idle_timeout.total_seconds(),
        }


@dataclass
class TrafficPolicy:
    """Comprehensive traffic policy."""

    load_balancer: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    connection_pool: Optional[ConnectionPool] = None
    circuit_breaker: Optional[CircuitBreaker] = None
    retry_policy: Optional[RetryPolicy] = None
    timeout_policy: Optional[TimeoutPolicy] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "load_balancer": self.load_balancer.value,
            "connection_pool": self.connection_pool.to_dict()
            if self.connection_pool
            else None,
            "circuit_breaker": self.circuit_breaker.get_state()
            if self.circuit_breaker
            else None,
            "retry_policy": self.retry_policy.to_dict() if self.retry_policy else None,
            "timeout_policy": self.timeout_policy.to_dict()
            if self.timeout_policy
            else None,
        }


class LoadBalancer:
    """Load balancer implementation."""

    def __init__(
        self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    ):
        self.strategy = strategy
        self._round_robin_index = 0
        self._lock = asyncio.Lock()

    async def select_endpoint(
        self, endpoints: List[ServiceEndpoint], request_context: Dict[str, Any] = None
    ) -> Optional[ServiceEndpoint]:
        """Select endpoint based on load balancing strategy."""
        healthy_endpoints = [ep for ep in endpoints if ep.is_healthy()]

        if not healthy_endpoints:
            return None

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return await self._round_robin_selection(healthy_endpoints)
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(healthy_endpoints)
        elif self.strategy == LoadBalancingStrategy.LEAST_REQUESTS:
            return min(healthy_endpoints, key=lambda ep: ep.active_requests)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED:
            return await self._weighted_selection(healthy_endpoints)
        elif self.strategy == LoadBalancingStrategy.CONSISTENT_HASH:
            return await self._consistent_hash_selection(
                healthy_endpoints, request_context
            )
        else:
            return healthy_endpoints[0]

    async def _round_robin_selection(
        self, endpoints: List[ServiceEndpoint]
    ) -> ServiceEndpoint:
        """Round robin selection."""
        async with self._lock:
            endpoint = endpoints[self._round_robin_index % len(endpoints)]
            self._round_robin_index += 1
            return endpoint

    async def _weighted_selection(
        self, endpoints: List[ServiceEndpoint]
    ) -> ServiceEndpoint:
        """Weighted random selection."""
        total_weight = sum(ep.weight for ep in endpoints)
        if total_weight == 0:
            return random.choice(endpoints)

        target = random.randint(1, total_weight)
        current_weight = 0

        for endpoint in endpoints:
            current_weight += endpoint.weight
            if current_weight >= target:
                return endpoint

        return endpoints[-1]

    async def _consistent_hash_selection(
        self, endpoints: List[ServiceEndpoint], request_context: Dict[str, Any]
    ) -> ServiceEndpoint:
        """Consistent hash selection."""
        if not request_context:
            return endpoints[0]

        # Simple hash based on request context
        hash_key = str(
            request_context.get("user_id", "")
            + request_context.get("session_id", "")
            + request_context.get("client_ip", "")
        )

        hash_value = hash(hash_key) % len(endpoints)
        return endpoints[hash_value]


class CanaryDeployment:
    """Canary deployment strategy."""

    def __init__(self, service_name: str, namespace: str = "default"):
        self.service_name = service_name
        self.namespace = namespace
        self.canary_weight = 0
        self.stable_weight = 100
        self.virtual_service: Optional[VirtualService] = None

    def create_traffic_split(
        self, canary_version: str, stable_version: str, canary_weight: int
    ) -> VirtualService:
        """Create virtual service for canary deployment."""
        self.canary_weight = canary_weight
        self.stable_weight = 100 - canary_weight

        # Stable route
        stable_route = HTTPRoute(
            destination=f"{self.service_name}-{stable_version}",
            weight=self.stable_weight,
        )

        # Canary route
        canary_route = HTTPRoute(
            destination=f"{self.service_name}-{canary_version}",
            weight=self.canary_weight,
        )

        virtual_service = VirtualService(
            name=f"{self.service_name}-canary",
            namespace=self.namespace,
            hosts=[self.service_name],
            http_routes=[stable_route, canary_route],
        )

        self.virtual_service = virtual_service
        return virtual_service

    def update_traffic_weight(self, canary_weight: int) -> None:
        """Update canary traffic weight."""
        if not self.virtual_service or len(self.virtual_service.http_routes) < 2:
            raise ValueError("Virtual service not configured for canary deployment")

        self.canary_weight = canary_weight
        self.stable_weight = 100 - canary_weight

        # Update weights
        self.virtual_service.http_routes[0].weight = self.stable_weight  # Stable
        self.virtual_service.http_routes[1].weight = self.canary_weight  # Canary

    def promote_canary(self) -> None:
        """Promote canary to 100% traffic."""
        self.update_traffic_weight(100)

    def rollback_canary(self) -> None:
        """Rollback canary to 0% traffic."""
        self.update_traffic_weight(0)


class BlueGreenDeployment:
    """Blue-green deployment strategy."""

    def __init__(self, service_name: str, namespace: str = "default"):
        self.service_name = service_name
        self.namespace = namespace
        self.active_version = "blue"
        self.virtual_service: Optional[VirtualService] = None

    def setup_deployment(self, blue_version: str, green_version: str) -> VirtualService:
        """Setup blue-green deployment."""
        # Initially route all traffic to blue
        route = HTTPRoute(destination=f"{self.service_name}-{blue_version}", weight=100)

        virtual_service = VirtualService(
            name=f"{self.service_name}-bluegreen",
            namespace=self.namespace,
            hosts=[self.service_name],
            http_routes=[route],
        )

        self.virtual_service = virtual_service
        return virtual_service

    def switch_to_green(self, green_version: str) -> None:
        """Switch traffic to green version."""
        if not self.virtual_service:
            raise ValueError("Virtual service not configured")

        self.virtual_service.http_routes[
            0
        ].destination = f"{self.service_name}-{green_version}"
        self.active_version = "green"

    def switch_to_blue(self, blue_version: str) -> None:
        """Switch traffic to blue version."""
        if not self.virtual_service:
            raise ValueError("Virtual service not configured")

        self.virtual_service.http_routes[
            0
        ].destination = f"{self.service_name}-{blue_version}"
        self.active_version = "blue"


class TrafficManager:
    """Comprehensive traffic management."""

    def __init__(self):
        self._virtual_services: Dict[str, VirtualService] = {}
        self._destination_rules: Dict[str, DestinationRule] = {}
        self._gateways: Dict[str, Gateway] = {}
        self._service_entries: Dict[str, ServiceEntry] = {}
        self._load_balancers: Dict[str, LoadBalancer] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    async def create_virtual_service(self, virtual_service: VirtualService) -> None:
        """Create virtual service."""
        key = f"{virtual_service.namespace}/{virtual_service.name}"
        self._virtual_services[key] = virtual_service
        logger.info(f"Created virtual service: {key}")

    async def create_destination_rule(self, destination_rule: DestinationRule) -> None:
        """Create destination rule."""
        key = f"{destination_rule.namespace}/{destination_rule.name}"
        self._destination_rules[key] = destination_rule
        logger.info(f"Created destination rule: {key}")

    async def create_gateway(self, gateway: Gateway) -> None:
        """Create gateway."""
        key = f"{gateway.namespace}/{gateway.name}"
        self._gateways[key] = gateway
        logger.info(f"Created gateway: {key}")

    async def create_service_entry(self, service_entry: ServiceEntry) -> None:
        """Create service entry."""
        key = f"{service_entry.namespace}/{service_entry.name}"
        self._service_entries[key] = service_entry
        logger.info(f"Created service entry: {key}")

    async def get_traffic_configuration(self, namespace: str = None) -> Dict[str, Any]:
        """Get traffic configuration."""
        config = {
            "virtual_services": {},
            "destination_rules": {},
            "gateways": {},
            "service_entries": {},
        }

        for key, vs in self._virtual_services.items():
            if namespace is None or vs.namespace == namespace:
                config["virtual_services"][key] = vs.to_dict()

        for key, dr in self._destination_rules.items():
            if namespace is None or dr.namespace == namespace:
                config["destination_rules"][key] = dr.to_dict()

        for key, gw in self._gateways.items():
            if namespace is None or gw.namespace == namespace:
                config["gateways"][key] = gw.to_dict()

        for key, se in self._service_entries.items():
            if namespace is None or se.namespace == namespace:
                config["service_entries"][key] = se.to_dict()

        return config


# Utility functions


def create_http_route(
    destination: str,
    weight: int = 100,
    uri_prefix: str = None,
    headers: Dict[str, str] = None,
) -> HTTPRoute:
    """Create HTTP route."""
    return HTTPRoute(
        destination=destination,
        weight=weight,
        uri_prefix=uri_prefix,
        headers=headers or {},
    )


def create_connection_pool(
    max_connections: int = 100, connect_timeout: timedelta = timedelta(seconds=10)
) -> ConnectionPool:
    """Create connection pool."""
    return ConnectionPool(
        max_connections=max_connections, connect_timeout=connect_timeout
    )


def create_retry_policy(
    attempts: int = 3, per_try_timeout: timedelta = timedelta(seconds=5)
) -> RetryPolicy:
    """Create retry policy."""
    return RetryPolicy(attempts=attempts, per_try_timeout=per_try_timeout)
