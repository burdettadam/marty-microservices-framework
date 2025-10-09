"""
Service Mesh Integration and Orchestration Framework for Marty Microservices

This module provides comprehensive service mesh integration with Istio/Envoy support,
advanced traffic management, service discovery automation, and cross-service
communication patterns for microservices orchestration.
"""

import asyncio
import hashlib
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

# For networking and HTTP operations
import aiohttp


class ServiceMeshType(Enum):
    """Supported service mesh types."""

    ISTIO = "istio"
    LINKERD = "linkerd"
    CONSUL_CONNECT = "consul_connect"
    ENVOY = "envoy"
    CUSTOM = "custom"


class TrafficPolicy(Enum):
    """Traffic management policies."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONN = "least_conn"
    RANDOM = "random"
    CONSISTENT_HASH = "consistent_hash"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LOCALITY_AWARE = "locality_aware"


class CircuitBreakerPolicy(Enum):
    """Circuit breaker policies for service mesh."""

    CONSECUTIVE_ERRORS = "consecutive_errors"
    ERROR_RATE = "error_rate"
    SLOW_CALL_RATE = "slow_call_rate"
    COMBINED = "combined"


class SecurityPolicy(Enum):
    """Security policies for service communication."""

    MTLS_STRICT = "mtls_strict"
    MTLS_PERMISSIVE = "mtls_permissive"
    PLAINTEXT = "plaintext"
    CUSTOM_TLS = "custom_tls"


class ServiceDiscoveryProvider(Enum):
    """Service discovery providers."""

    KUBERNETES = "kubernetes"
    CONSUL = "consul"
    ETCD = "etcd"
    EUREKA = "eureka"
    CUSTOM = "custom"


@dataclass
class ServiceEndpoint:
    """Service endpoint configuration."""

    service_name: str
    host: str
    port: int
    protocol: str = "http"
    health_check_path: str = "/health"
    version: str = "v1"
    region: str = "default"
    zone: str = "default"
    metadata: dict[str, str] = field(default_factory=dict)
    weight: int = 100
    is_healthy: bool = True


@dataclass
class TrafficRule:
    """Traffic routing rule."""

    rule_id: str
    service_name: str
    match_conditions: list[dict[str, Any]]
    destination_rules: list[dict[str, Any]]
    weight: int = 100
    timeout: int | None = None
    retry_policy: dict[str, Any] | None = None
    fault_injection: dict[str, Any] | None = None


@dataclass
class ServiceMeshConfig:
    """Service mesh configuration."""

    mesh_type: ServiceMeshType
    cluster_name: str
    namespace: str
    mtls_enabled: bool = True
    telemetry_enabled: bool = True
    tracing_enabled: bool = True
    access_logging: bool = True
    ingress_gateway: str | None = None
    egress_gateway: str | None = None
    custom_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceDiscoveryConfig:
    """Service discovery configuration."""

    provider: ServiceDiscoveryProvider
    refresh_interval: int = 30  # seconds
    health_check_interval: int = 10  # seconds
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    endpoints: list[str] = field(default_factory=list)
    auth_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration for service mesh."""

    consecutive_errors: int = 5
    interval: int = 30  # seconds
    base_ejection_time: int = 30  # seconds
    max_ejection_percent: int = 50
    min_health_percent: int = 50
    split_external_errors: bool = True


@dataclass
class LoadBalancingConfig:
    """Load balancing configuration."""

    policy: TrafficPolicy = TrafficPolicy.ROUND_ROBIN
    hash_policy: dict[str, str] | None = None
    locality_lb_setting: dict[str, Any] | None = None
    outlier_detection: CircuitBreakerConfig | None = None


@dataclass
class ServiceCommunication:
    """Service-to-service communication tracking."""

    source_service: str
    destination_service: str
    protocol: str
    success_count: int = 0
    error_count: int = 0
    total_latency: float = 0.0
    last_communication: datetime | None = None
    circuit_breaker_state: str = "closed"


class ServiceRegistry:
    """Service registry for service discovery and management."""

    def __init__(self, config: ServiceDiscoveryConfig):
        """Initialize service registry."""
        self.config = config

        # Service storage
        self.services: dict[str, list[ServiceEndpoint]] = defaultdict(list)
        self.service_metadata: dict[str, dict[str, Any]] = {}

        # Health tracking
        self.health_status: dict[str, dict[str, Any]] = defaultdict(dict)
        self.health_check_tasks: dict[str, asyncio.Task] = {}

        # Service watchers and callbacks
        self.service_watchers: list[Callable] = []

        # Thread safety
        self._lock = threading.RLock()

    def register_service(self, service: ServiceEndpoint) -> bool:
        """Register a service endpoint."""
        try:
            with self._lock:
                # Add to service list
                self.services[service.service_name].append(service)

                # Initialize health status
                endpoint_key = f"{service.host}:{service.port}"
                self.health_status[service.service_name][endpoint_key] = {
                    "healthy": service.is_healthy,
                    "last_check": datetime.now(timezone.utc),
                    "consecutive_failures": 0,
                    "consecutive_successes": 0,
                }

                # Start health checking if not already running
                if service.service_name not in self.health_check_tasks:
                    task = asyncio.create_task(
                        self._health_check_loop(service.service_name)
                    )
                    self.health_check_tasks[service.service_name] = task

                # Notify watchers
                self._notify_watchers("service_registered", service)

                logging.info(
                    f"Registered service: {service.service_name} at {service.host}:{service.port}"
                )
                return True

        except Exception as e:
            logging.exception(f"Failed to register service {service.service_name}: {e}")
            return False

    def deregister_service(self, service_name: str, host: str, port: int) -> bool:
        """Deregister a service endpoint."""
        try:
            with self._lock:
                if service_name in self.services:
                    # Remove the specific endpoint
                    self.services[service_name] = [
                        s
                        for s in self.services[service_name]
                        if not (s.host == host and s.port == port)
                    ]

                    # Remove health status
                    endpoint_key = f"{host}:{port}"
                    self.health_status[service_name].pop(endpoint_key, None)

                    # Stop health checking if no endpoints left
                    if (
                        not self.services[service_name]
                        and service_name in self.health_check_tasks
                    ):
                        self.health_check_tasks[service_name].cancel()
                        del self.health_check_tasks[service_name]

                    # Notify watchers
                    self._notify_watchers(
                        "service_deregistered",
                        {"service_name": service_name, "host": host, "port": port},
                    )

                    logging.info(
                        f"Deregistered service: {service_name} at {host}:{port}"
                    )
                    return True

        except Exception as e:
            logging.exception(f"Failed to deregister service {service_name}: {e}")
            return False

    def discover_services(
        self, service_name: str, healthy_only: bool = True
    ) -> list[ServiceEndpoint]:
        """Discover available service endpoints."""
        with self._lock:
            if service_name not in self.services:
                return []

            endpoints = self.services[service_name].copy()

            if healthy_only:
                # Filter only healthy endpoints
                healthy_endpoints = []
                for endpoint in endpoints:
                    endpoint_key = f"{endpoint.host}:{endpoint.port}"
                    health_info = self.health_status[service_name].get(endpoint_key, {})
                    if health_info.get("healthy", False):
                        healthy_endpoints.append(endpoint)
                endpoints = healthy_endpoints

            return endpoints

    def get_service_metadata(self, service_name: str) -> dict[str, Any]:
        """Get service metadata."""
        return self.service_metadata.get(service_name, {})

    def set_service_metadata(self, service_name: str, metadata: dict[str, Any]):
        """Set service metadata."""
        self.service_metadata[service_name] = metadata

    def add_service_watcher(self, callback: Callable):
        """Add service change watcher."""
        self.service_watchers.append(callback)

    def remove_service_watcher(self, callback: Callable):
        """Remove service change watcher."""
        if callback in self.service_watchers:
            self.service_watchers.remove(callback)

    async def _health_check_loop(self, service_name: str):
        """Health check loop for a service."""
        while True:
            try:
                await self._perform_health_checks(service_name)
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception(f"Health check error for {service_name}: {e}")
                await asyncio.sleep(self.config.health_check_interval)

    async def _perform_health_checks(self, service_name: str):
        """Perform health checks for service endpoints."""
        endpoints = self.services.get(service_name, [])

        for endpoint in endpoints:
            endpoint_key = f"{endpoint.host}:{endpoint.port}"

            try:
                # Perform health check
                health_url = f"{endpoint.protocol}://{endpoint.host}:{endpoint.port}{endpoint.health_check_path}"

                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as session:
                    async with session.get(health_url) as response:
                        is_healthy = response.status == 200

                # Update health status
                with self._lock:
                    health_info = self.health_status[service_name][endpoint_key]
                    health_info["last_check"] = datetime.now(timezone.utc)

                    if is_healthy:
                        health_info["consecutive_successes"] += 1
                        health_info["consecutive_failures"] = 0

                        # Mark as healthy if it reaches threshold
                        if (
                            health_info["consecutive_successes"]
                            >= self.config.healthy_threshold
                        ):
                            if not health_info["healthy"]:
                                health_info["healthy"] = True
                                self._notify_watchers("endpoint_healthy", endpoint)
                    else:
                        health_info["consecutive_failures"] += 1
                        health_info["consecutive_successes"] = 0

                        # Mark as unhealthy if it reaches threshold
                        if (
                            health_info["consecutive_failures"]
                            >= self.config.unhealthy_threshold
                        ):
                            if health_info["healthy"]:
                                health_info["healthy"] = False
                                self._notify_watchers("endpoint_unhealthy", endpoint)

            except Exception:
                # Health check failed
                with self._lock:
                    health_info = self.health_status[service_name][endpoint_key]
                    health_info["consecutive_failures"] += 1
                    health_info["consecutive_successes"] = 0
                    health_info["last_check"] = datetime.now(timezone.utc)

                    if (
                        health_info["consecutive_failures"]
                        >= self.config.unhealthy_threshold
                    ):
                        if health_info["healthy"]:
                            health_info["healthy"] = False
                            self._notify_watchers("endpoint_unhealthy", endpoint)

    def _notify_watchers(self, event_type: str, data: Any):
        """Notify service watchers of changes."""
        for watcher in self.service_watchers:
            try:
                if asyncio.iscoroutinefunction(watcher):
                    asyncio.create_task(watcher(event_type, data))
                else:
                    watcher(event_type, data)
            except Exception as e:
                logging.exception(f"Service watcher error: {e}")

    def get_registry_status(self) -> dict[str, Any]:
        """Get service registry status."""
        with self._lock:
            total_services = len(self.services)
            total_endpoints = sum(
                len(endpoints) for endpoints in self.services.values()
            )

            healthy_endpoints = 0
            for service_name, endpoints in self.services.items():
                for endpoint in endpoints:
                    endpoint_key = f"{endpoint.host}:{endpoint.port}"
                    if (
                        self.health_status[service_name]
                        .get(endpoint_key, {})
                        .get("healthy", False)
                    ):
                        healthy_endpoints += 1

            return {
                "provider": self.config.provider.value,
                "total_services": total_services,
                "total_endpoints": total_endpoints,
                "healthy_endpoints": healthy_endpoints,
                "unhealthy_endpoints": total_endpoints - healthy_endpoints,
                "health_check_interval": self.config.health_check_interval,
                "services": list(self.services.keys()),
            }


class LoadBalancer:
    """Advanced load balancer with multiple policies."""

    def __init__(self, config: LoadBalancingConfig):
        """Initialize load balancer."""
        self.config = config

        # Load balancing state
        self.current_index: dict[str, int] = defaultdict(int)
        self.connection_counts: dict[str, int] = defaultdict(int)

        # Statistics
        self.request_counts: dict[str, int] = defaultdict(int)
        self.response_times: dict[str, list[float]] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

    def select_endpoint(
        self,
        service_name: str,
        endpoints: list[ServiceEndpoint],
        request_context: dict[str, Any] = None,
    ) -> ServiceEndpoint | None:
        """Select an endpoint using the configured policy."""
        if not endpoints:
            return None

        request_context = request_context or {}

        with self._lock:
            if self.config.policy == TrafficPolicy.ROUND_ROBIN:
                return self._round_robin_select(service_name, endpoints)
            if self.config.policy == TrafficPolicy.WEIGHTED_ROUND_ROBIN:
                return self._weighted_round_robin_select(service_name, endpoints)
            if self.config.policy == TrafficPolicy.LEAST_CONN:
                return self._least_conn_select(endpoints)
            if self.config.policy == TrafficPolicy.RANDOM:
                return self._random_select(endpoints)
            if self.config.policy == TrafficPolicy.CONSISTENT_HASH:
                return self._consistent_hash_select(endpoints, request_context)
            if self.config.policy == TrafficPolicy.LOCALITY_AWARE:
                return self._locality_aware_select(endpoints, request_context)
            return self._round_robin_select(service_name, endpoints)

    def _round_robin_select(
        self, service_name: str, endpoints: list[ServiceEndpoint]
    ) -> ServiceEndpoint:
        """Round-robin endpoint selection."""
        index = self.current_index[service_name] % len(endpoints)
        self.current_index[service_name] = (index + 1) % len(endpoints)
        return endpoints[index]

    def _weighted_round_robin_select(
        self, service_name: str, endpoints: list[ServiceEndpoint]
    ) -> ServiceEndpoint:
        """Weighted round-robin endpoint selection."""
        # Calculate total weight
        total_weight = sum(endpoint.weight for endpoint in endpoints)

        # Create weighted list
        weighted_endpoints = []
        for endpoint in endpoints:
            count = max(1, (endpoint.weight * 100) // total_weight)
            weighted_endpoints.extend([endpoint] * count)

        if not weighted_endpoints:
            return endpoints[0]

        index = self.current_index[service_name] % len(weighted_endpoints)
        self.current_index[service_name] = (index + 1) % len(weighted_endpoints)
        return weighted_endpoints[index]

    def _least_conn_select(self, endpoints: list[ServiceEndpoint]) -> ServiceEndpoint:
        """Least connections endpoint selection."""
        min_connections = float("inf")
        selected_endpoint = endpoints[0]

        for endpoint in endpoints:
            endpoint_key = f"{endpoint.host}:{endpoint.port}"
            connections = self.connection_counts[endpoint_key]

            if connections < min_connections:
                min_connections = connections
                selected_endpoint = endpoint

        return selected_endpoint

    def _random_select(self, endpoints: list[ServiceEndpoint]) -> ServiceEndpoint:
        """Random endpoint selection."""
        import random

        return random.choice(endpoints)

    def _consistent_hash_select(
        self, endpoints: list[ServiceEndpoint], request_context: dict[str, Any]
    ) -> ServiceEndpoint:
        """Consistent hash endpoint selection."""
        if not self.config.hash_policy:
            return self._round_robin_select("default", endpoints)

        # Get hash key from request context
        hash_key = ""
        for header_field in self.config.hash_policy.get("header_fields", []):
            hash_key += request_context.get("headers", {}).get(header_field, "")

        for query_field in self.config.hash_policy.get("query_parameters", []):
            hash_key += request_context.get("query_params", {}).get(query_field, "")

        if "cookie" in self.config.hash_policy:
            cookie_name = self.config.hash_policy["cookie"]
            hash_key += request_context.get("cookies", {}).get(cookie_name, "")

        # Calculate hash
        hash_value = int(hashlib.sha256(hash_key.encode()).hexdigest()[:8], 16)
        index = hash_value % len(endpoints)

        return endpoints[index]

    def _locality_aware_select(
        self, endpoints: list[ServiceEndpoint], request_context: dict[str, Any]
    ) -> ServiceEndpoint:
        """Locality-aware endpoint selection."""
        client_region = request_context.get("client_region", "default")
        client_zone = request_context.get("client_zone", "default")

        # Prefer endpoints in same zone
        same_zone_endpoints = [e for e in endpoints if e.zone == client_zone]
        if same_zone_endpoints:
            return self._round_robin_select("zone", same_zone_endpoints)

        # Then prefer endpoints in same region
        same_region_endpoints = [e for e in endpoints if e.region == client_region]
        if same_region_endpoints:
            return self._round_robin_select("region", same_region_endpoints)

        # Fallback to any endpoint
        return self._round_robin_select("fallback", endpoints)

    def record_request_start(self, endpoint: ServiceEndpoint):
        """Record the start of a request to an endpoint."""
        endpoint_key = f"{endpoint.host}:{endpoint.port}"
        with self._lock:
            self.connection_counts[endpoint_key] += 1
            self.request_counts[endpoint_key] += 1

    def record_request_end(self, endpoint: ServiceEndpoint, response_time: float):
        """Record the end of a request to an endpoint."""
        endpoint_key = f"{endpoint.host}:{endpoint.port}"
        with self._lock:
            self.connection_counts[endpoint_key] = max(
                0, self.connection_counts[endpoint_key] - 1
            )

            # Track response times (keep last 1000)
            if len(self.response_times[endpoint_key]) >= 1000:
                self.response_times[endpoint_key] = self.response_times[endpoint_key][
                    -500:
                ]
            self.response_times[endpoint_key].append(response_time)

    def get_load_balancer_stats(self) -> dict[str, Any]:
        """Get load balancer statistics."""
        with self._lock:
            stats = {
                "policy": self.config.policy.value,
                "total_requests": sum(self.request_counts.values()),
                "active_connections": sum(self.connection_counts.values()),
                "endpoint_stats": {},
            }

            for endpoint_key in self.request_counts:
                response_times = self.response_times[endpoint_key]
                avg_response_time = (
                    sum(response_times) / len(response_times) if response_times else 0
                )

                stats["endpoint_stats"][endpoint_key] = {
                    "total_requests": self.request_counts[endpoint_key],
                    "active_connections": self.connection_counts[endpoint_key],
                    "avg_response_time": avg_response_time,
                    "recent_requests": len(response_times),
                }

            return stats


class TrafficManager:
    """Advanced traffic management for service mesh."""

    def __init__(self, mesh_config: ServiceMeshConfig):
        """Initialize traffic manager."""
        self.mesh_config = mesh_config

        # Traffic rules
        self.traffic_rules: dict[str, list[TrafficRule]] = defaultdict(list)
        self.active_rules: set[str] = set()

        # Traffic splitting
        self.traffic_splits: dict[str, dict[str, float]] = {}

        # Fault injection
        self.fault_injection_rules: dict[str, dict[str, Any]] = {}

        # Circuit breakers
        self.circuit_breakers: dict[str, dict[str, Any]] = {}

        # Metrics
        self.traffic_metrics: deque = deque(maxlen=10000)

    def add_traffic_rule(self, rule: TrafficRule) -> bool:
        """Add a traffic routing rule."""
        try:
            self.traffic_rules[rule.service_name].append(rule)
            self.active_rules.add(rule.rule_id)

            logging.info(
                f"Added traffic rule {rule.rule_id} for service {rule.service_name}"
            )
            return True

        except Exception as e:
            logging.exception(f"Failed to add traffic rule: {e}")
            return False

    def remove_traffic_rule(self, rule_id: str) -> bool:
        """Remove a traffic routing rule."""
        try:
            for service_name, rules in self.traffic_rules.items():
                self.traffic_rules[service_name] = [
                    r for r in rules if r.rule_id != rule_id
                ]

            self.active_rules.discard(rule_id)

            logging.info(f"Removed traffic rule {rule_id}")
            return True

        except Exception as e:
            logging.exception(f"Failed to remove traffic rule: {e}")
            return False

    def configure_traffic_split(
        self, service_name: str, version_weights: dict[str, float]
    ) -> bool:
        """Configure traffic splitting between service versions."""
        try:
            # Normalize weights to sum to 1.0
            total_weight = sum(version_weights.values())
            if total_weight > 0:
                normalized_weights = {
                    version: weight / total_weight
                    for version, weight in version_weights.items()
                }
                self.traffic_splits[service_name] = normalized_weights

            logging.info(
                f"Configured traffic split for {service_name}: {normalized_weights}"
            )
            return True

        except Exception as e:
            logging.exception(f"Failed to configure traffic split: {e}")
            return False

    def inject_fault(self, service_name: str, fault_config: dict[str, Any]) -> bool:
        """Configure fault injection for a service."""
        try:
            self.fault_injection_rules[service_name] = fault_config

            logging.info(
                f"Configured fault injection for {service_name}: {fault_config}"
            )
            return True

        except Exception as e:
            logging.exception(f"Failed to configure fault injection: {e}")
            return False

    def configure_circuit_breaker(
        self, service_name: str, config: CircuitBreakerConfig
    ) -> bool:
        """Configure circuit breaker for a service."""
        try:
            self.circuit_breakers[service_name] = {
                "consecutive_errors": config.consecutive_errors,
                "interval": config.interval,
                "base_ejection_time": config.base_ejection_time,
                "max_ejection_percent": config.max_ejection_percent,
                "min_health_percent": config.min_health_percent,
                "split_external_errors": config.split_external_errors,
                "state": "closed",
                "error_count": 0,
                "last_failure": None,
            }

            logging.info(f"Configured circuit breaker for {service_name}")
            return True

        except Exception as e:
            logging.exception(f"Failed to configure circuit breaker: {e}")
            return False

    def should_route_request(
        self, service_name: str, request_context: dict[str, Any]
    ) -> bool:
        """Determine if request should be routed based on traffic rules."""
        # Check fault injection
        if service_name in self.fault_injection_rules:
            fault_config = self.fault_injection_rules[service_name]
            if self._should_inject_fault(fault_config):
                return False

        # Check circuit breaker
        if service_name in self.circuit_breakers:
            if self._is_circuit_breaker_open(service_name):
                return False

        return True

    def select_service_version(
        self, service_name: str, request_context: dict[str, Any]
    ) -> str | None:
        """Select service version based on traffic splitting rules."""
        if service_name not in self.traffic_splits:
            return None

        version_weights = self.traffic_splits[service_name]

        # Use user ID for consistent routing if available
        user_id = request_context.get("user_id", "anonymous")
        hash_value = int(
            hashlib.sha256(f"{service_name}:{user_id}".encode()).hexdigest()[:8], 16
        )
        random_value = (hash_value % 10000) / 10000.0

        # Select version based on weights
        cumulative_weight = 0.0
        for version, weight in version_weights.items():
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                return version

        # Fallback to first version
        return list(version_weights.keys())[0] if version_weights else None

    def _should_inject_fault(self, fault_config: dict[str, Any]) -> bool:
        """Determine if fault should be injected."""
        import random

        # Check delay injection
        if "delay" in fault_config:
            delay_config = fault_config["delay"]
            if random.random() < delay_config.get("percentage", 0):
                return True

        # Check abort injection
        if "abort" in fault_config:
            abort_config = fault_config["abort"]
            if random.random() < abort_config.get("percentage", 0):
                return True

        return False

    def _is_circuit_breaker_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for a service."""
        if service_name not in self.circuit_breakers:
            return False

        cb_config = self.circuit_breakers[service_name]

        if cb_config["state"] == "open":
            # Check if we should attempt to close
            if cb_config["last_failure"]:
                elapsed = time.time() - cb_config["last_failure"]
                if elapsed > cb_config["base_ejection_time"]:
                    cb_config["state"] = "half_open"
                    cb_config["error_count"] = 0
                    return False
            return True

        return False

    def record_request_result(
        self, service_name: str, success: bool, response_time: float
    ):
        """Record request result for circuit breaker and metrics."""
        # Update circuit breaker state
        if service_name in self.circuit_breakers:
            cb_config = self.circuit_breakers[service_name]

            if success:
                if cb_config["state"] == "half_open":
                    cb_config["state"] = "closed"
                cb_config["error_count"] = 0
            else:
                cb_config["error_count"] += 1
                cb_config["last_failure"] = time.time()

                if cb_config["error_count"] >= cb_config["consecutive_errors"]:
                    cb_config["state"] = "open"

        # Record metrics
        self.traffic_metrics.append(
            {
                "service_name": service_name,
                "success": success,
                "response_time": response_time,
                "timestamp": datetime.now(timezone.utc),
            }
        )

    def get_traffic_stats(self) -> dict[str, Any]:
        """Get traffic management statistics."""
        # Calculate service-level statistics
        service_stats = defaultdict(
            lambda: {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "avg_response_time": 0.0,
                "circuit_breaker_state": "closed",
            }
        )

        for metric in self.traffic_metrics:
            service_name = metric["service_name"]
            stats = service_stats[service_name]

            stats["total_requests"] += 1
            if metric["success"]:
                stats["successful_requests"] += 1
            else:
                stats["failed_requests"] += 1

            # Update average response time
            total_time = stats["avg_response_time"] * (stats["total_requests"] - 1)
            stats["avg_response_time"] = (total_time + metric["response_time"]) / stats[
                "total_requests"
            ]

        # Add circuit breaker states
        for service_name, cb_config in self.circuit_breakers.items():
            if service_name in service_stats:
                service_stats[service_name]["circuit_breaker_state"] = cb_config[
                    "state"
                ]

        return {
            "total_rules": sum(len(rules) for rules in self.traffic_rules.values()),
            "active_traffic_splits": len(self.traffic_splits),
            "active_fault_injections": len(self.fault_injection_rules),
            "circuit_breakers": len(self.circuit_breakers),
            "service_stats": dict(service_stats),
        }


class ServiceMeshOrchestrator:
    """Main service mesh orchestration engine."""

    def __init__(self, config: ServiceMeshConfig):
        """Initialize service mesh orchestrator."""
        self.config = config

        # Core components
        self.service_registry = None
        self.load_balancer = None
        self.traffic_manager = TrafficManager(config)

        # Service communication tracking
        self.service_communications: dict[str, ServiceCommunication] = {}

        # Mesh status
        self.mesh_status = "initializing"
        self.connected_services: set[str] = set()

        # Configuration management
        self.mesh_configurations: dict[str, Any] = {}

        # Event tracking
        self.mesh_events: deque = deque(maxlen=10000)

    def initialize_service_discovery(self, discovery_config: ServiceDiscoveryConfig):
        """Initialize service discovery."""
        self.service_registry = ServiceRegistry(discovery_config)
        self.mesh_status = "service_discovery_ready"

        # Add service watcher for mesh events
        self.service_registry.add_service_watcher(self._handle_service_event)

        logging.info(
            f"Initialized service discovery with {discovery_config.provider.value}"
        )

    def initialize_load_balancing(self, lb_config: LoadBalancingConfig):
        """Initialize load balancing."""
        self.load_balancer = LoadBalancer(lb_config)
        self.mesh_status = "load_balancing_ready"

        logging.info(f"Initialized load balancing with {lb_config.policy.value}")

    def register_service(self, service: ServiceEndpoint) -> bool:
        """Register a service with the mesh."""
        if not self.service_registry:
            logging.error("Service registry not initialized")
            return False

        success = self.service_registry.register_service(service)

        if success:
            self.connected_services.add(service.service_name)
            self._log_mesh_event(
                "service_registered",
                {
                    "service_name": service.service_name,
                    "endpoint": f"{service.host}:{service.port}",
                },
            )

        return success

    def deregister_service(self, service_name: str, host: str, port: int) -> bool:
        """Deregister a service from the mesh."""
        if not self.service_registry:
            return False

        success = self.service_registry.deregister_service(service_name, host, port)

        if success:
            # Check if this was the last endpoint for the service
            remaining_endpoints = self.service_registry.discover_services(
                service_name, healthy_only=False
            )
            if not remaining_endpoints:
                self.connected_services.discard(service_name)

            self._log_mesh_event(
                "service_deregistered",
                {"service_name": service_name, "endpoint": f"{host}:{port}"},
            )

        return success

    async def route_request(
        self, source_service: str, target_service: str, request_context: dict[str, Any]
    ) -> ServiceEndpoint | None:
        """Route a request through the service mesh."""
        if not all([self.service_registry, self.load_balancer, self.traffic_manager]):
            logging.error("Service mesh not fully initialized")
            return None

        try:
            # Check if request should be routed
            if not self.traffic_manager.should_route_request(
                target_service, request_context
            ):
                self._log_mesh_event(
                    "request_blocked",
                    {
                        "source": source_service,
                        "target": target_service,
                        "reason": "fault_injection_or_circuit_breaker",
                    },
                )
                return None

            # Select service version based on traffic rules
            target_version = self.traffic_manager.select_service_version(
                target_service, request_context
            )

            # Discover available endpoints
            endpoints = self.service_registry.discover_services(
                target_service, healthy_only=True
            )

            # Filter by version if specified
            if target_version:
                endpoints = [e for e in endpoints if e.version == target_version]

            if not endpoints:
                self._log_mesh_event(
                    "no_endpoints_available",
                    {
                        "source": source_service,
                        "target": target_service,
                        "version": target_version,
                    },
                )
                return None

            # Select endpoint using load balancing
            selected_endpoint = self.load_balancer.select_endpoint(
                target_service, endpoints, request_context
            )

            if selected_endpoint:
                # Record load balancing
                self.load_balancer.record_request_start(selected_endpoint)

                # Track service communication
                self._track_service_communication(source_service, target_service)

                self._log_mesh_event(
                    "request_routed",
                    {
                        "source": source_service,
                        "target": target_service,
                        "endpoint": f"{selected_endpoint.host}:{selected_endpoint.port}",
                        "version": selected_endpoint.version,
                    },
                )

            return selected_endpoint

        except Exception as e:
            logging.exception(f"Request routing error: {e}")
            return None

    def record_request_completion(
        self,
        source_service: str,
        target_service: str,
        endpoint: ServiceEndpoint,
        success: bool,
        response_time: float,
    ):
        """Record request completion for metrics and load balancing."""
        # Update load balancer
        if self.load_balancer:
            self.load_balancer.record_request_end(endpoint, response_time)

        # Update traffic manager
        self.traffic_manager.record_request_result(
            target_service, success, response_time
        )

        # Update service communication tracking
        comm_key = f"{source_service}->{target_service}"
        if comm_key in self.service_communications:
            comm = self.service_communications[comm_key]
            if success:
                comm.success_count += 1
            else:
                comm.error_count += 1
            comm.total_latency += response_time
            comm.last_communication = datetime.now(timezone.utc)

        self._log_mesh_event(
            "request_completed",
            {
                "source": source_service,
                "target": target_service,
                "success": success,
                "response_time": response_time,
            },
        )

    def configure_traffic_policies(self, policies: dict[str, Any]) -> bool:
        """Configure traffic management policies."""
        try:
            for service_name, policy_config in policies.items():
                # Configure traffic splitting
                if "traffic_split" in policy_config:
                    self.traffic_manager.configure_traffic_split(
                        service_name, policy_config["traffic_split"]
                    )

                # Configure fault injection
                if "fault_injection" in policy_config:
                    self.traffic_manager.inject_fault(
                        service_name, policy_config["fault_injection"]
                    )

                # Configure circuit breaker
                if "circuit_breaker" in policy_config:
                    cb_config = CircuitBreakerConfig(**policy_config["circuit_breaker"])
                    self.traffic_manager.configure_circuit_breaker(
                        service_name, cb_config
                    )

            self._log_mesh_event(
                "traffic_policies_configured", {"services": list(policies.keys())}
            )

            return True

        except Exception as e:
            logging.exception(f"Failed to configure traffic policies: {e}")
            return False

    def apply_security_policies(self, security_policies: dict[str, Any]) -> bool:
        """Apply security policies to the mesh."""
        try:
            # Store security configurations
            self.mesh_configurations["security"] = security_policies

            # In a real implementation, this would:
            # - Configure mTLS certificates
            # - Set up authentication policies
            # - Configure authorization rules
            # - Apply network policies

            self._log_mesh_event(
                "security_policies_applied",
                {"policies": list(security_policies.keys())},
            )

            return True

        except Exception as e:
            logging.exception(f"Failed to apply security policies: {e}")
            return False

    def generate_mesh_configuration(self) -> dict[str, Any]:
        """Generate service mesh configuration for deployment."""
        if self.config.mesh_type == ServiceMeshType.ISTIO:
            return self._generate_istio_config()
        if self.config.mesh_type == ServiceMeshType.LINKERD:
            return self._generate_linkerd_config()
        if self.config.mesh_type == ServiceMeshType.CONSUL_CONNECT:
            return self._generate_consul_config()
        return self._generate_generic_config()

    def _generate_istio_config(self) -> dict[str, Any]:
        """Generate Istio service mesh configuration."""
        configs = {}

        # Virtual Services
        virtual_services = []
        for service_name, rules in self.traffic_manager.traffic_rules.items():
            for rule in rules:
                virtual_service = {
                    "apiVersion": "networking.istio.io/v1beta1",
                    "kind": "VirtualService",
                    "metadata": {
                        "name": f"{service_name}-vs",
                        "namespace": self.config.namespace,
                    },
                    "spec": {
                        "hosts": [service_name],
                        "http": [
                            {
                                "match": rule.match_conditions,
                                "route": rule.destination_rules,
                                "timeout": f"{rule.timeout}s"
                                if rule.timeout
                                else "30s",
                                "retries": rule.retry_policy,
                            }
                        ],
                    },
                }
                virtual_services.append(virtual_service)

        configs["virtual_services"] = virtual_services

        # Destination Rules
        destination_rules = []
        for service_name in self.connected_services:
            if service_name in self.traffic_manager.circuit_breakers:
                cb_config = self.traffic_manager.circuit_breakers[service_name]
                destination_rule = {
                    "apiVersion": "networking.istio.io/v1beta1",
                    "kind": "DestinationRule",
                    "metadata": {
                        "name": f"{service_name}-dr",
                        "namespace": self.config.namespace,
                    },
                    "spec": {
                        "host": service_name,
                        "trafficPolicy": {
                            "outlierDetection": {
                                "consecutiveErrors": cb_config["consecutive_errors"],
                                "interval": f"{cb_config['interval']}s",
                                "baseEjectionTime": f"{cb_config['base_ejection_time']}s",
                                "maxEjectionPercent": cb_config["max_ejection_percent"],
                                "minHealthPercent": cb_config["min_health_percent"],
                            }
                        },
                    },
                }
                destination_rules.append(destination_rule)

        configs["destination_rules"] = destination_rules

        # Service Entries for external services
        configs["service_entries"] = []

        return configs

    def _generate_linkerd_config(self) -> dict[str, Any]:
        """Generate Linkerd service mesh configuration."""
        # Simplified Linkerd configuration
        return {
            "traffic_splits": self.traffic_manager.traffic_splits,
            "service_profiles": {},
            "tap_configs": {},
        }

    def _generate_consul_config(self) -> dict[str, Any]:
        """Generate Consul Connect configuration."""
        # Simplified Consul Connect configuration
        return {"service_configs": {}, "proxy_configs": {}, "intentions": {}}

    def _generate_generic_config(self) -> dict[str, Any]:
        """Generate generic service mesh configuration."""
        return {
            "services": list(self.connected_services),
            "traffic_rules": self.traffic_manager.traffic_rules,
            "load_balancing": self.load_balancer.config.policy.value
            if self.load_balancer
            else None,
            "security_config": self.mesh_configurations.get("security", {}),
        }

    def _track_service_communication(self, source: str, target: str):
        """Track service-to-service communication."""
        comm_key = f"{source}->{target}"

        if comm_key not in self.service_communications:
            self.service_communications[comm_key] = ServiceCommunication(
                source_service=source,
                destination_service=target,
                protocol="http",  # Default, could be configured
            )

    def _handle_service_event(self, event_type: str, data: Any):
        """Handle service registry events."""
        self._log_mesh_event(f"service_discovery_{event_type}", data)

    def _log_mesh_event(self, event_type: str, details: dict[str, Any]):
        """Log mesh events."""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc),
            "details": details,
        }

        self.mesh_events.append(event)
        logging.info(f"Mesh event: {event_type} - {details}")

    def get_mesh_status(self) -> dict[str, Any]:
        """Get comprehensive mesh status."""
        registry_status = (
            self.service_registry.get_registry_status() if self.service_registry else {}
        )
        lb_stats = (
            self.load_balancer.get_load_balancer_stats() if self.load_balancer else {}
        )
        traffic_stats = self.traffic_manager.get_traffic_stats()

        # Service communication summary
        comm_summary = {}
        for comm_key, comm in self.service_communications.items():
            total_requests = comm.success_count + comm.error_count
            avg_latency = (
                comm.total_latency / total_requests if total_requests > 0 else 0
            )
            error_rate = comm.error_count / total_requests if total_requests > 0 else 0

            comm_summary[comm_key] = {
                "total_requests": total_requests,
                "success_rate": comm.success_count / total_requests
                if total_requests > 0
                else 0,
                "error_rate": error_rate,
                "avg_latency": avg_latency,
                "last_communication": comm.last_communication.isoformat()
                if comm.last_communication
                else None,
            }

        return {
            "mesh_type": self.config.mesh_type.value,
            "mesh_status": self.mesh_status,
            "cluster_name": self.config.cluster_name,
            "namespace": self.config.namespace,
            "connected_services": list(self.connected_services),
            "service_discovery": registry_status,
            "load_balancing": lb_stats,
            "traffic_management": traffic_stats,
            "service_communications": comm_summary,
            "recent_events": len(self.mesh_events),
            "mtls_enabled": self.config.mtls_enabled,
            "telemetry_enabled": self.config.telemetry_enabled,
        }


def create_service_mesh_orchestrator(
    config: ServiceMeshConfig,
) -> ServiceMeshOrchestrator:
    """Create service mesh orchestrator instance."""
    return ServiceMeshOrchestrator(config)
