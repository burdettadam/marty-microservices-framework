"""
Advanced Service Discovery and Communication Framework for Marty Microservices

This module provides intelligent service discovery, cross-service communication patterns,
health monitoring, and service dependency management for microservices orchestration.
"""

import asyncio
import builtins
import logging
import random
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, dict, list, set

# For networking operations
import aiohttp


class CommunicationProtocol(Enum):
    """Service communication protocols."""

    HTTP = "http"
    HTTPS = "https"
    GRPC = "grpc"
    GRPC_WEB = "grpc_web"
    WEBSOCKET = "websocket"
    TCP = "tcp"
    UDP = "udp"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS = "redis"


class ServiceType(Enum):
    """Service types for discovery and routing."""

    WEB_SERVICE = "web_service"
    API_SERVICE = "api_service"
    BACKGROUND_SERVICE = "background_service"
    DATABASE_SERVICE = "database_service"
    CACHE_SERVICE = "cache_service"
    MESSAGE_BROKER = "message_broker"
    GATEWAY_SERVICE = "gateway_service"
    PROXY_SERVICE = "proxy_service"


class HealthStatus(Enum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


class ServiceState(Enum):
    """Service lifecycle state."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    MAINTENANCE = "maintenance"


class DependencyType(Enum):
    """Service dependency types."""

    HARD_DEPENDENCY = "hard_dependency"
    SOFT_DEPENDENCY = "soft_dependency"
    OPTIONAL_DEPENDENCY = "optional_dependency"
    CIRCULAR_DEPENDENCY = "circular_dependency"


@dataclass
class ServiceInstance:
    """Enhanced service instance representation."""

    instance_id: str
    service_name: str
    host: str
    port: int
    protocol: CommunicationProtocol = CommunicationProtocol.HTTP
    service_type: ServiceType = ServiceType.API_SERVICE
    version: str = "1.0.0"
    region: str = "default"
    zone: str = "default"
    datacenter: str = "default"

    # Health and status
    health_status: HealthStatus = HealthStatus.UNKNOWN
    service_state: ServiceState = ServiceState.STARTING
    last_health_check: datetime | None = None
    health_check_url: str = "/health"
    readiness_check_url: str = "/ready"

    # Capabilities and metadata
    capabilities: builtins.list[str] = field(default_factory=list)
    tags: builtins.dict[str, str] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    # Performance characteristics
    cpu_limit: float | None = None  # CPU cores
    memory_limit: int | None = None  # MB
    max_connections: int | None = None
    rate_limit: int | None = None  # requests per second

    # Networking
    ssl_enabled: bool = False
    certificate_info: builtins.dict[str, str] | None = None

    # Timestamps
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ServiceDependency:
    """Service dependency definition."""

    dependency_id: str
    source_service: str
    target_service: str
    dependency_type: DependencyType
    required_version: str | None = None
    fallback_service: str | None = None
    timeout: int = 30  # seconds
    retry_attempts: int = 3
    circuit_breaker_enabled: bool = True
    health_check_required: bool = True


@dataclass
class ServiceContract:
    """Service contract for API specifications."""

    contract_id: str
    service_name: str
    version: str
    contract_type: str  # "openapi", "grpc", "graphql", etc.
    schema: builtins.dict[str, Any]
    endpoints: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    breaking_changes: builtins.list[str] = field(default_factory=list)
    deprecated_endpoints: builtins.list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CommunicationMetrics:
    """Service communication metrics."""

    source_service: str
    target_service: str
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency: float = 0.0
    min_latency: float = float("inf")
    max_latency: float = 0.0
    last_request: datetime | None = None
    error_distribution: builtins.dict[str, int] = field(default_factory=dict)


class ServiceHealthChecker:
    """Advanced health checking for services."""

    def __init__(self, check_interval: int = 30, timeout: int = 5):
        """Initialize health checker."""
        self.check_interval = check_interval
        self.timeout = timeout

        # Health check tasks
        self.health_tasks: builtins.dict[str, asyncio.Task] = {}
        self.health_results: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Health check strategies
        self.check_strategies: builtins.dict[str, Callable] = {
            "http": self._http_health_check,
            "https": self._http_health_check,
            "tcp": self._tcp_health_check,
            "grpc": self._grpc_health_check,
            "custom": self._custom_health_check,
        }

        # Health check history
        self.health_history: builtins.dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )

    async def start_health_monitoring(self, service: ServiceInstance):
        """Start health monitoring for a service."""
        if service.instance_id in self.health_tasks:
            return  # Already monitoring

        task = asyncio.create_task(self._health_check_loop(service))
        self.health_tasks[service.instance_id] = task

        logging.info(
            f"Started health monitoring for {service.service_name}:{service.instance_id}"
        )

    async def stop_health_monitoring(self, instance_id: str):
        """Stop health monitoring for a service."""
        if instance_id in self.health_tasks:
            task = self.health_tasks[instance_id]
            task.cancel()
            del self.health_tasks[instance_id]

            logging.info(f"Stopped health monitoring for instance {instance_id}")

    async def _health_check_loop(self, service: ServiceInstance):
        """Health check loop for a service."""
        while True:
            try:
                await self._perform_health_check(service)
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception(f"Health check error for {service.instance_id}: {e}")
                await asyncio.sleep(self.check_interval)

    async def _perform_health_check(self, service: ServiceInstance):
        """Perform health check for a service."""
        protocol = service.protocol.value
        strategy = self.check_strategies.get(protocol, self._http_health_check)

        start_time = time.time()
        try:
            health_result = await strategy(service)
            response_time = time.time() - start_time

            # Update service health status
            service.health_status = (
                HealthStatus.HEALTHY
                if health_result["healthy"]
                else HealthStatus.UNHEALTHY
            )
            service.last_health_check = datetime.now(timezone.utc)
            service.last_seen = datetime.now(timezone.utc)

            # Store health result
            health_data = {
                "timestamp": datetime.now(timezone.utc),
                "healthy": health_result["healthy"],
                "response_time": response_time,
                "details": health_result.get("details", {}),
                "error": health_result.get("error"),
            }

            self.health_results[service.instance_id] = health_data
            self.health_history[service.instance_id].append(health_data)

        except Exception as e:
            response_time = time.time() - start_time
            service.health_status = HealthStatus.UNHEALTHY
            service.last_health_check = datetime.now(timezone.utc)

            error_data = {
                "timestamp": datetime.now(timezone.utc),
                "healthy": False,
                "response_time": response_time,
                "error": str(e),
            }

            self.health_results[service.instance_id] = error_data
            self.health_history[service.instance_id].append(error_data)

    async def _http_health_check(
        self, service: ServiceInstance
    ) -> builtins.dict[str, Any]:
        """HTTP/HTTPS health check."""
        scheme = "https" if service.ssl_enabled else "http"
        health_url = (
            f"{scheme}://{service.host}:{service.port}{service.health_check_url}"
        )

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(health_url) as response:
                body = await response.text()

                healthy = 200 <= response.status < 300

                return {
                    "healthy": healthy,
                    "details": {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": body[:1000],  # Limit body size
                    },
                }

    async def _tcp_health_check(
        self, service: ServiceInstance
    ) -> builtins.dict[str, Any]:
        """TCP health check."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(service.host, service.port),
                timeout=self.timeout,
            )

            writer.close()
            await writer.wait_closed()

            return {"healthy": True, "details": {"connection": "successful"}}

        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _grpc_health_check(
        self, service: ServiceInstance
    ) -> builtins.dict[str, Any]:
        """gRPC health check."""
        # Simplified gRPC health check
        # In practice, this would use the gRPC health checking protocol
        try:
            # For now, fall back to TCP check
            return await self._tcp_health_check(service)
        except Exception as e:
            return {"healthy": False, "error": str(e)}

    async def _custom_health_check(
        self, service: ServiceInstance
    ) -> builtins.dict[str, Any]:
        """Custom health check based on service configuration."""
        # Custom health check logic based on service metadata
        custom_check = service.metadata.get("health_check")

        if not custom_check:
            return await self._tcp_health_check(service)

        # Implement custom check based on configuration
        return {"healthy": True, "details": {"custom_check": "not_implemented"}}

    def get_health_status(self, instance_id: str) -> builtins.dict[str, Any] | None:
        """Get current health status for an instance."""
        return self.health_results.get(instance_id)

    def get_health_history(
        self, instance_id: str, limit: int = 50
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Get health check history for an instance."""
        history = self.health_history.get(instance_id, deque())
        return list(history)[-limit:]

    def calculate_availability(
        self, instance_id: str, window_minutes: int = 60
    ) -> float:
        """Calculate service availability over a time window."""
        history = self.health_history.get(instance_id, deque())

        if not history:
            return 0.0

        # Filter to time window
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        recent_checks = [
            check for check in history if check["timestamp"] >= cutoff_time
        ]

        if not recent_checks:
            return 0.0

        healthy_checks = sum(1 for check in recent_checks if check["healthy"])
        return healthy_checks / len(recent_checks)


class ServiceCommunicationManager:
    """Manages service-to-service communication patterns."""

    def __init__(self):
        """Initialize communication manager."""
        self.communication_metrics: builtins.dict[str, CommunicationMetrics] = {}
        self.active_connections: builtins.dict[str, builtins.set[str]] = defaultdict(
            set
        )
        self.connection_pools: builtins.dict[str, Any] = {}

        # Circuit breaker states
        self.circuit_breakers: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Communication patterns
        self.communication_patterns: builtins.dict[
            str, builtins.list[str]
        ] = defaultdict(list)

        # Request tracking
        self.active_requests: builtins.dict[str, builtins.dict[str, Any]] = {}

    async def establish_connection(
        self, source_service: str, target_service: str, target_instance: ServiceInstance
    ) -> bool:
        """Establish connection between services."""
        connection_key = f"{source_service}->{target_service}"
        instance_key = f"{target_instance.host}:{target_instance.port}"

        try:
            # Create connection pool if needed
            if connection_key not in self.connection_pools:
                self.connection_pools[
                    connection_key
                ] = await self._create_connection_pool(target_instance)

            # Track active connection
            self.active_connections[connection_key].add(instance_key)

            # Initialize metrics if not exists
            if connection_key not in self.communication_metrics:
                self.communication_metrics[connection_key] = CommunicationMetrics(
                    source_service=source_service, target_service=target_service
                )

            # Record communication pattern
            if target_service not in self.communication_patterns[source_service]:
                self.communication_patterns[source_service].append(target_service)

            logging.info(f"Established connection: {connection_key} -> {instance_key}")
            return True

        except Exception as e:
            logging.exception(f"Failed to establish connection {connection_key}: {e}")
            return False

    async def send_request(
        self,
        source_service: str,
        target_service: str,
        target_instance: ServiceInstance,
        request_data: builtins.dict[str, Any],
        timeout: int = 30,
    ) -> builtins.dict[str, Any]:
        """Send request to target service."""
        connection_key = f"{source_service}->{target_service}"
        request_id = str(uuid.uuid4())

        # Record request start
        start_time = time.time()
        self.active_requests[request_id] = {
            "source": source_service,
            "target": target_service,
            "instance": f"{target_instance.host}:{target_instance.port}",
            "start_time": start_time,
            "timeout": timeout,
        }

        try:
            # Check circuit breaker
            if self._is_circuit_breaker_open(connection_key):
                raise Exception("Circuit breaker is open")

            # Send request based on protocol
            if target_instance.protocol in [
                CommunicationProtocol.HTTP,
                CommunicationProtocol.HTTPS,
            ]:
                response = await self._send_http_request(
                    target_instance, request_data, timeout
                )
            elif target_instance.protocol == CommunicationProtocol.GRPC:
                response = await self._send_grpc_request(
                    target_instance, request_data, timeout
                )
            elif target_instance.protocol == CommunicationProtocol.WEBSOCKET:
                response = await self._send_websocket_request(
                    target_instance, request_data, timeout
                )
            else:
                raise Exception(f"Unsupported protocol: {target_instance.protocol}")

            # Record successful request
            response_time = time.time() - start_time
            self._record_request_success(connection_key, response_time)

            return {
                "success": True,
                "response": response,
                "response_time": response_time,
                "request_id": request_id,
            }

        except Exception as e:
            # Record failed request
            response_time = time.time() - start_time
            self._record_request_failure(connection_key, response_time, str(e))

            return {
                "success": False,
                "error": str(e),
                "response_time": response_time,
                "request_id": request_id,
            }

        finally:
            # Clean up request tracking
            self.active_requests.pop(request_id, None)

    async def _create_connection_pool(self, instance: ServiceInstance) -> Any:
        """Create connection pool for service instance."""
        if instance.protocol in [
            CommunicationProtocol.HTTP,
            CommunicationProtocol.HTTPS,
        ]:
            # HTTP connection pool
            connector = aiohttp.TCPConnector(
                limit=instance.max_connections or 100,
                limit_per_host=instance.max_connections or 100,
            )
            return aiohttp.ClientSession(connector=connector)
        # For other protocols, return a placeholder
        return {"protocol": instance.protocol.value, "instance": instance}

    async def _send_http_request(
        self,
        instance: ServiceInstance,
        request_data: builtins.dict[str, Any],
        timeout: int,
    ) -> builtins.dict[str, Any]:
        """Send HTTP request to service instance."""
        scheme = "https" if instance.ssl_enabled else "http"
        base_url = f"{scheme}://{instance.host}:{instance.port}"

        method = request_data.get("method", "GET")
        path = request_data.get("path", "/")
        headers = request_data.get("headers", {})
        body = request_data.get("body")
        query_params = request_data.get("query_params", {})

        url = f"{base_url}{path}"

        client_timeout = aiohttp.ClientTimeout(total=timeout)

        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.request(
                method=method,
                url=url,
                headers=headers,
                params=query_params,
                json=body if isinstance(body, dict) else None,
                data=body if isinstance(body, str | bytes) else None,
            ) as response:
                response_body = await response.text()

                return {
                    "status_code": response.status,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "content_type": response.content_type,
                }

    async def _send_grpc_request(
        self,
        instance: ServiceInstance,
        request_data: builtins.dict[str, Any],
        timeout: int,
    ) -> builtins.dict[str, Any]:
        """Send gRPC request to service instance."""
        # Simplified gRPC request
        # In practice, this would use grpcio library

        request_data.get("service_method")
        request_data.get("message", {})

        # Simulate gRPC call
        await asyncio.sleep(0.1)  # Simulate network delay

        return {
            "status": "OK",
            "response": {"message": "gRPC response simulation"},
            "metadata": {},
        }

    async def _send_websocket_request(
        self,
        instance: ServiceInstance,
        request_data: builtins.dict[str, Any],
        timeout: int,
    ) -> builtins.dict[str, Any]:
        """Send WebSocket message to service instance."""
        scheme = "wss" if instance.ssl_enabled else "ws"
        ws_url = f"{scheme}://{instance.host}:{instance.port}/ws"

        message = request_data.get("message", {})

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                await ws.send_json(message)
                response = await ws.receive_json()

                return {"type": "websocket", "response": response}

    def _record_request_success(self, connection_key: str, response_time: float):
        """Record successful request metrics."""
        if connection_key in self.communication_metrics:
            metrics = self.communication_metrics[connection_key]
            metrics.request_count += 1
            metrics.success_count += 1
            metrics.total_latency += response_time
            metrics.min_latency = min(metrics.min_latency, response_time)
            metrics.max_latency = max(metrics.max_latency, response_time)
            metrics.last_request = datetime.now(timezone.utc)

        # Reset circuit breaker on success
        if connection_key in self.circuit_breakers:
            self.circuit_breakers[connection_key]["failure_count"] = 0

    def _record_request_failure(
        self, connection_key: str, response_time: float, error: str
    ):
        """Record failed request metrics."""
        if connection_key in self.communication_metrics:
            metrics = self.communication_metrics[connection_key]
            metrics.request_count += 1
            metrics.error_count += 1
            metrics.total_latency += response_time
            metrics.last_request = datetime.now(timezone.utc)

            # Track error types
            error_type = type(Exception(error)).__name__
            metrics.error_distribution[error_type] = (
                metrics.error_distribution.get(error_type, 0) + 1
            )

        # Update circuit breaker
        self._update_circuit_breaker(connection_key)

    def _is_circuit_breaker_open(self, connection_key: str) -> bool:
        """Check if circuit breaker is open."""
        if connection_key not in self.circuit_breakers:
            self.circuit_breakers[connection_key] = {
                "state": "closed",
                "failure_count": 0,
                "last_failure_time": None,
                "failure_threshold": 5,
                "recovery_timeout": 60,  # seconds
            }
            return False

        cb = self.circuit_breakers[connection_key]

        if cb["state"] == "open":
            # Check if we should attempt recovery
            if cb["last_failure_time"]:
                elapsed = time.time() - cb["last_failure_time"]
                if elapsed > cb["recovery_timeout"]:
                    cb["state"] = "half_open"
                    return False
            return True

        return False

    def _update_circuit_breaker(self, connection_key: str):
        """Update circuit breaker state after failure."""
        if connection_key not in self.circuit_breakers:
            return

        cb = self.circuit_breakers[connection_key]
        cb["failure_count"] += 1
        cb["last_failure_time"] = time.time()

        if cb["failure_count"] >= cb["failure_threshold"]:
            cb["state"] = "open"

    def get_communication_stats(self) -> builtins.dict[str, Any]:
        """Get communication statistics."""
        stats = {
            "total_connections": len(self.communication_metrics),
            "active_requests": len(self.active_requests),
            "communication_patterns": dict(self.communication_patterns),
            "service_metrics": {},
        }

        for connection_key, metrics in self.communication_metrics.items():
            avg_latency = (
                metrics.total_latency / metrics.request_count
                if metrics.request_count > 0
                else 0
            )
            success_rate = (
                metrics.success_count / metrics.request_count
                if metrics.request_count > 0
                else 0
            )

            stats["service_metrics"][connection_key] = {
                "total_requests": metrics.request_count,
                "success_rate": success_rate,
                "error_rate": 1 - success_rate,
                "avg_latency": avg_latency,
                "min_latency": metrics.min_latency
                if metrics.min_latency != float("inf")
                else 0,
                "max_latency": metrics.max_latency,
                "error_distribution": metrics.error_distribution,
                "last_request": metrics.last_request.isoformat()
                if metrics.last_request
                else None,
            }

        return stats


class ServiceDependencyManager:
    """Manages service dependencies and dependency graphs."""

    def __init__(self):
        """Initialize dependency manager."""
        self.dependencies: builtins.dict[str, ServiceDependency] = {}
        self.dependency_graph: builtins.dict[str, builtins.set[str]] = defaultdict(set)
        self.reverse_dependency_graph: builtins.dict[
            str, builtins.set[str]
        ] = defaultdict(set)

        # Dependency health tracking
        self.dependency_health: builtins.dict[str, bool] = {}

        # Startup order
        self.startup_order: builtins.list[str] = []
        self.shutdown_order: builtins.list[str] = []

    def add_dependency(self, dependency: ServiceDependency) -> bool:
        """Add a service dependency."""
        try:
            self.dependencies[dependency.dependency_id] = dependency

            # Update dependency graphs
            self.dependency_graph[dependency.source_service].add(
                dependency.target_service
            )
            self.reverse_dependency_graph[dependency.target_service].add(
                dependency.source_service
            )

            # Check for circular dependencies
            if self._has_circular_dependency(
                dependency.source_service, dependency.target_service
            ):
                dependency.dependency_type = DependencyType.CIRCULAR_DEPENDENCY
                logging.warning(
                    f"Circular dependency detected: {dependency.source_service} -> {dependency.target_service}"
                )

            # Recalculate startup order
            self._calculate_startup_order()

            logging.info(
                f"Added dependency: {dependency.source_service} -> {dependency.target_service}"
            )
            return True

        except Exception as e:
            logging.exception(f"Failed to add dependency: {e}")
            return False

    def remove_dependency(self, dependency_id: str) -> bool:
        """Remove a service dependency."""
        try:
            if dependency_id not in self.dependencies:
                return False

            dependency = self.dependencies[dependency_id]

            # Update dependency graphs
            self.dependency_graph[dependency.source_service].discard(
                dependency.target_service
            )
            self.reverse_dependency_graph[dependency.target_service].discard(
                dependency.source_service
            )

            # Remove dependency
            del self.dependencies[dependency_id]

            # Recalculate startup order
            self._calculate_startup_order()

            logging.info(f"Removed dependency: {dependency_id}")
            return True

        except Exception as e:
            logging.exception(f"Failed to remove dependency: {e}")
            return False

    def get_dependencies(self, service_name: str) -> builtins.list[ServiceDependency]:
        """Get dependencies for a service."""
        return [
            dep
            for dep in self.dependencies.values()
            if dep.source_service == service_name
        ]

    def get_dependents(self, service_name: str) -> builtins.list[str]:
        """Get services that depend on this service."""
        return list(self.reverse_dependency_graph.get(service_name, set()))

    def check_dependency_health(self, service_name: str) -> builtins.dict[str, Any]:
        """Check health of service dependencies."""
        dependencies = self.get_dependencies(service_name)

        health_status = {
            "healthy_dependencies": 0,
            "unhealthy_dependencies": 0,
            "unknown_dependencies": 0,
            "dependency_details": {},
        }

        for dep in dependencies:
            dep_health = self.dependency_health.get(dep.target_service, None)

            if dep_health is True:
                health_status["healthy_dependencies"] += 1
                status = "healthy"
            elif dep_health is False:
                health_status["unhealthy_dependencies"] += 1
                status = "unhealthy"
            else:
                health_status["unknown_dependencies"] += 1
                status = "unknown"

            health_status["dependency_details"][dep.target_service] = {
                "dependency_type": dep.dependency_type.value,
                "health_status": status,
                "required": dep.dependency_type in [DependencyType.HARD_DEPENDENCY],
            }

        return health_status

    def can_start_service(
        self, service_name: str
    ) -> builtins.tuple[bool, builtins.list[str]]:
        """Check if service can start based on dependencies."""
        dependencies = self.get_dependencies(service_name)
        blocking_dependencies = []

        for dep in dependencies:
            if dep.dependency_type == DependencyType.HARD_DEPENDENCY:
                if not self.dependency_health.get(dep.target_service, False):
                    blocking_dependencies.append(dep.target_service)

        can_start = len(blocking_dependencies) == 0
        return can_start, blocking_dependencies

    def get_startup_order(self) -> builtins.list[str]:
        """Get recommended startup order for services."""
        return self.startup_order.copy()

    def get_shutdown_order(self) -> builtins.list[str]:
        """Get recommended shutdown order for services."""
        return self.shutdown_order.copy()

    def _has_circular_dependency(self, source: str, target: str) -> bool:
        """Check if adding dependency would create a circular dependency."""
        # Check if target already depends on source (directly or indirectly)
        visited = set()

        def has_path(current: str, destination: str) -> bool:
            if current == destination:
                return True

            if current in visited:
                return False

            visited.add(current)

            for next_service in self.dependency_graph.get(current, set()):
                if has_path(next_service, destination):
                    return True

            return False

        return has_path(target, source)

    def _calculate_startup_order(self):
        """Calculate optimal startup order using topological sort."""
        # Get all services
        all_services = set()
        for dep in self.dependencies.values():
            all_services.add(dep.source_service)
            all_services.add(dep.target_service)

        # Perform topological sort
        in_degree = dict.fromkeys(all_services, 0)

        # Calculate in-degrees (only for hard dependencies)
        for dep in self.dependencies.values():
            if dep.dependency_type == DependencyType.HARD_DEPENDENCY:
                in_degree[dep.source_service] += 1

        # Kahn's algorithm
        queue = [service for service, degree in in_degree.items() if degree == 0]
        startup_order = []

        while queue:
            service = queue.pop(0)
            startup_order.append(service)

            # Reduce in-degree for dependent services
            for dependent in self.reverse_dependency_graph.get(service, set()):
                # Check if this is a hard dependency
                dep = next(
                    (
                        d
                        for d in self.dependencies.values()
                        if d.source_service == dependent and d.target_service == service
                    ),
                    None,
                )

                if dep and dep.dependency_type == DependencyType.HARD_DEPENDENCY:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        self.startup_order = startup_order
        self.shutdown_order = startup_order[::-1]  # Reverse order for shutdown

    def update_dependency_health(self, service_name: str, is_healthy: bool):
        """Update health status for a service dependency."""
        self.dependency_health[service_name] = is_healthy

    def get_dependency_graph(self) -> builtins.dict[str, Any]:
        """Get dependency graph visualization data."""
        return {
            "nodes": list(
                set(
                    list(self.dependency_graph.keys())
                    + [
                        target
                        for targets in self.dependency_graph.values()
                        for target in targets
                    ]
                )
            ),
            "edges": [
                {
                    "source": dep.source_service,
                    "target": dep.target_service,
                    "type": dep.dependency_type.value,
                    "required": dep.dependency_type == DependencyType.HARD_DEPENDENCY,
                }
                for dep in self.dependencies.values()
            ],
            "startup_order": self.startup_order,
            "shutdown_order": self.shutdown_order,
        }


class AdvancedServiceDiscovery:
    """Advanced service discovery with intelligent routing."""

    def __init__(self):
        """Initialize advanced service discovery."""
        self.service_instances: builtins.dict[
            str, builtins.list[ServiceInstance]
        ] = defaultdict(list)
        self.service_contracts: builtins.dict[str, ServiceContract] = {}

        # Components
        self.health_checker = ServiceHealthChecker()
        self.communication_manager = ServiceCommunicationManager()
        self.dependency_manager = ServiceDependencyManager()

        # Service watchers
        self.service_watchers: builtins.list[Callable] = []

        # Discovery statistics
        self.discovery_metrics: builtins.dict[str, Any] = defaultdict(int)

        # Thread safety
        self._lock = threading.RLock()

    async def register_service_instance(self, instance: ServiceInstance) -> bool:
        """Register a service instance."""
        try:
            with self._lock:
                self.service_instances[instance.service_name].append(instance)
                self.discovery_metrics["total_registrations"] += 1

            # Start health monitoring
            await self.health_checker.start_health_monitoring(instance)

            # Notify watchers
            await self._notify_watchers("service_registered", instance)

            logging.info(
                f"Registered service instance: {instance.service_name}:{instance.instance_id}"
            )
            return True

        except Exception as e:
            logging.exception(f"Failed to register service instance: {e}")
            return False

    async def deregister_service_instance(
        self, service_name: str, instance_id: str
    ) -> bool:
        """Deregister a service instance."""
        try:
            with self._lock:
                instances = self.service_instances.get(service_name, [])
                self.service_instances[service_name] = [
                    inst for inst in instances if inst.instance_id != instance_id
                ]
                self.discovery_metrics["total_deregistrations"] += 1

            # Stop health monitoring
            await self.health_checker.stop_health_monitoring(instance_id)

            # Notify watchers
            await self._notify_watchers(
                "service_deregistered",
                {"service_name": service_name, "instance_id": instance_id},
            )

            logging.info(f"Deregistered service instance: {service_name}:{instance_id}")
            return True

        except Exception as e:
            logging.exception(f"Failed to deregister service instance: {e}")
            return False

    def discover_service_instances(
        self, service_name: str, filters: builtins.dict[str, Any] = None
    ) -> builtins.list[ServiceInstance]:
        """Discover service instances with advanced filtering."""
        with self._lock:
            instances = self.service_instances.get(service_name, []).copy()

        if not instances:
            return []

        # Apply filters
        if filters:
            instances = self._apply_filters(instances, filters)

        # Sort by preference (health, proximity, load, etc.)
        instances = self._sort_by_preference(instances, filters or {})

        self.discovery_metrics["discovery_requests"] += 1
        return instances

    def _apply_filters(
        self,
        instances: builtins.list[ServiceInstance],
        filters: builtins.dict[str, Any],
    ) -> builtins.list[ServiceInstance]:
        """Apply filters to service instances."""
        filtered_instances = instances

        # Health filter
        if filters.get("healthy_only", True):
            filtered_instances = [
                inst
                for inst in filtered_instances
                if inst.health_status == HealthStatus.HEALTHY
            ]

        # Version filter
        if "version" in filters:
            target_version = filters["version"]
            filtered_instances = [
                inst for inst in filtered_instances if inst.version == target_version
            ]

        # Region/Zone filter
        if "region" in filters:
            target_region = filters["region"]
            filtered_instances = [
                inst for inst in filtered_instances if inst.region == target_region
            ]

        if "zone" in filters:
            target_zone = filters["zone"]
            filtered_instances = [
                inst for inst in filtered_instances if inst.zone == target_zone
            ]

        # Tags filter
        if "tags" in filters:
            required_tags = filters["tags"]
            filtered_instances = [
                inst
                for inst in filtered_instances
                if all(inst.tags.get(k) == v for k, v in required_tags.items())
            ]

        # Capabilities filter
        if "capabilities" in filters:
            required_capabilities = filters["capabilities"]
            filtered_instances = [
                inst
                for inst in filtered_instances
                if all(cap in inst.capabilities for cap in required_capabilities)
            ]

        return filtered_instances

    def _sort_by_preference(
        self,
        instances: builtins.list[ServiceInstance],
        filters: builtins.dict[str, Any],
    ) -> builtins.list[ServiceInstance]:
        """Sort instances by preference criteria."""

        def preference_score(instance: ServiceInstance) -> float:
            score = 0.0

            # Health weight
            if instance.health_status == HealthStatus.HEALTHY:
                score += 100
            elif instance.health_status == HealthStatus.DEGRADED:
                score += 50

            # Proximity weight (prefer same zone, then region)
            client_zone = filters.get("client_zone")
            client_region = filters.get("client_region")

            if client_zone and instance.zone == client_zone:
                score += 20
            elif client_region and instance.region == client_region:
                score += 10

            # Load balancing (prefer instances with fewer connections)
            # This would be based on actual load metrics in practice
            score += random.uniform(0, 5)  # Random tie-breaker

            return score

        return sorted(instances, key=preference_score, reverse=True)

    def register_service_contract(self, contract: ServiceContract) -> bool:
        """Register service contract for API compatibility."""
        try:
            self.service_contracts[
                f"{contract.service_name}:{contract.version}"
            ] = contract

            logging.info(
                f"Registered service contract: {contract.service_name} v{contract.version}"
            )
            return True

        except Exception as e:
            logging.exception(f"Failed to register service contract: {e}")
            return False

    def get_service_contract(
        self, service_name: str, version: str
    ) -> ServiceContract | None:
        """Get service contract for compatibility checking."""
        return self.service_contracts.get(f"{service_name}:{version}")

    def check_compatibility(
        self, client_contract: ServiceContract, server_contract: ServiceContract
    ) -> builtins.dict[str, Any]:
        """Check API compatibility between service contracts."""
        compatibility_result = {
            "compatible": True,
            "breaking_changes": [],
            "warnings": [],
            "recommendations": [],
        }

        # Version compatibility
        if client_contract.version != server_contract.version:
            compatibility_result["warnings"].append(
                f"Version mismatch: client expects {client_contract.version}, "
                f"server provides {server_contract.version}"
            )

        # Check for breaking changes
        if server_contract.breaking_changes:
            compatibility_result["breaking_changes"].extend(
                server_contract.breaking_changes
            )
            compatibility_result["compatible"] = False

        # Check deprecated endpoints
        if server_contract.deprecated_endpoints:
            compatibility_result["warnings"].extend(
                [
                    f"Deprecated endpoint: {endpoint}"
                    for endpoint in server_contract.deprecated_endpoints
                ]
            )

        return compatibility_result

    async def _notify_watchers(self, event_type: str, data: Any):
        """Notify service discovery watchers."""
        for watcher in self.service_watchers:
            try:
                if asyncio.iscoroutinefunction(watcher):
                    await watcher(event_type, data)
                else:
                    watcher(event_type, data)
            except Exception as e:
                logging.exception(f"Service watcher error: {e}")

    def add_service_watcher(self, watcher: Callable):
        """Add service discovery watcher."""
        self.service_watchers.append(watcher)

    def remove_service_watcher(self, watcher: Callable):
        """Remove service discovery watcher."""
        if watcher in self.service_watchers:
            self.service_watchers.remove(watcher)

    def get_discovery_status(self) -> builtins.dict[str, Any]:
        """Get comprehensive discovery status."""
        with self._lock:
            total_instances = sum(
                len(instances) for instances in self.service_instances.values()
            )
            healthy_instances = 0

            for instances in self.service_instances.values():
                healthy_instances += sum(
                    1
                    for inst in instances
                    if inst.health_status == HealthStatus.HEALTHY
                )

        communication_stats = self.communication_manager.get_communication_stats()

        return {
            "total_services": len(self.service_instances),
            "total_instances": total_instances,
            "healthy_instances": healthy_instances,
            "unhealthy_instances": total_instances - healthy_instances,
            "service_contracts": len(self.service_contracts),
            "discovery_metrics": dict(self.discovery_metrics),
            "communication_stats": communication_stats,
            "dependency_graph": self.dependency_manager.get_dependency_graph(),
        }


def create_advanced_service_discovery() -> AdvancedServiceDiscovery:
    """Create advanced service discovery instance."""
    return AdvancedServiceDiscovery()
