"""
Service Discovery Patterns

Client-side and server-side discovery implementations with caching,
failover, and intelligent service resolution strategies.
"""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from .core import HealthStatus, ServiceInstance, ServiceRegistry, ServiceWatcher
from .load_balancing import (
    LoadBalancer,
    LoadBalancingConfig,
    LoadBalancingContext,
    create_load_balancer,
)

logger = logging.getLogger(__name__)


class DiscoveryPattern(Enum):
    """Service discovery pattern types."""

    CLIENT_SIDE = "client_side"
    SERVER_SIDE = "server_side"
    HYBRID = "hybrid"
    SERVICE_MESH = "service_mesh"


class CacheStrategy(Enum):
    """Cache strategy types."""

    NONE = "none"
    TTL = "ttl"
    REFRESH_AHEAD = "refresh_ahead"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"


@dataclass
class DiscoveryConfig:
    """Configuration for service discovery."""

    # Discovery pattern
    pattern: DiscoveryPattern = DiscoveryPattern.CLIENT_SIDE

    # Service resolution
    service_resolution_timeout: float = 5.0
    max_resolution_retries: int = 3
    resolution_retry_delay: float = 1.0

    # Caching configuration
    cache_strategy: CacheStrategy = CacheStrategy.TTL
    cache_ttl: float = 300.0  # 5 minutes
    cache_max_size: int = 1000
    refresh_ahead_factor: float = 0.8  # Refresh when 80% of TTL elapsed

    # Health checking
    health_check_enabled: bool = True
    health_check_interval: float = 30.0
    health_check_timeout: float = 5.0

    # Failover configuration
    enable_failover: bool = True
    failover_timeout: float = 10.0
    backup_registries: List[str] = field(default_factory=list)

    # Load balancing
    load_balancing_enabled: bool = True
    load_balancing_config: Optional[LoadBalancingConfig] = None

    # Metrics and monitoring
    enable_metrics: bool = True
    metrics_collection_interval: float = 60.0

    # Circuit breaker for registries
    registry_circuit_breaker_enabled: bool = True
    registry_failure_threshold: int = 5
    registry_recovery_timeout: float = 60.0

    # Zone and region awareness
    zone_aware: bool = False
    region_aware: bool = False
    prefer_local_zone: bool = True
    prefer_local_region: bool = True


@dataclass
class ServiceQuery:
    """Query parameters for service discovery."""

    service_name: str
    version: Optional[str] = None
    environment: Optional[str] = None
    zone: Optional[str] = None
    region: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    protocols: List[str] = field(default_factory=list)

    # Query options
    include_unhealthy: bool = False
    max_instances: Optional[int] = None
    prefer_zone: Optional[str] = None
    prefer_region: Optional[str] = None
    exclude_instances: Set[str] = field(default_factory=set)

    def matches_instance(self, instance: ServiceInstance) -> bool:
        """Check if instance matches query criteria."""

        # Basic service name match
        if instance.service_name != self.service_name:
            return False

        # Version match
        if self.version and instance.version != self.version:
            return False

        # Environment match
        if (
            self.environment
            and instance.metadata.get("environment") != self.environment
        ):
            return False

        # Zone match
        if self.zone and instance.zone != self.zone:
            return False

        # Region match
        if self.region and instance.region != self.region:
            return False

        # Exclude specific instances
        if instance.instance_id in self.exclude_instances:
            return False

        # Health check
        if not self.include_unhealthy and not instance.is_healthy():
            return False

        # Tag matching
        for key, value in self.tags.items():
            if instance.tags.get(key) != value:
                return False

        # Label matching
        for key, value in self.labels.items():
            if instance.labels.get(key) != value:
                return False

        # Protocol matching
        if self.protocols:
            instance_protocols = instance.metadata.get("protocols", [])
            if not any(protocol in instance_protocols for protocol in self.protocols):
                return False

        return True


@dataclass
class DiscoveryResult:
    """Result of service discovery operation."""

    instances: List[ServiceInstance]
    query: ServiceQuery
    source: str  # Registry source
    cached: bool = False
    cache_age: float = 0.0
    resolution_time: float = 0.0

    # Selection information
    selected_instance: Optional[ServiceInstance] = None
    load_balancer_used: bool = False

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class CacheEntry:
    """Cache entry for service discovery results."""

    def __init__(
        self,
        instances: List[ServiceInstance],
        ttl: float,
        refresh_callback: Optional[Callable] = None,
    ):
        self.instances = instances
        self.created_at = time.time()
        self.ttl = ttl
        self.last_accessed = time.time()
        self.access_count = 0
        self.refresh_callback = refresh_callback
        self._refreshing = False

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.created_at > self.ttl

    def should_refresh(self, refresh_ahead_factor: float = 0.8) -> bool:
        """Check if cache entry should be refreshed ahead of expiration."""
        age = time.time() - self.created_at
        return age > (self.ttl * refresh_ahead_factor)

    def access(self) -> List[ServiceInstance]:
        """Access cache entry and update statistics."""
        self.last_accessed = time.time()
        self.access_count += 1
        return self.instances.copy()

    async def refresh_if_needed(self, refresh_ahead_factor: float = 0.8):
        """Refresh cache entry if needed (refresh-ahead strategy)."""
        if (
            self.refresh_callback
            and self.should_refresh(refresh_ahead_factor)
            and not self._refreshing
        ):
            self._refreshing = True
            try:
                new_instances = await self.refresh_callback()
                if new_instances:
                    self.instances = new_instances
                    self.created_at = time.time()
            except Exception as e:
                logger.warning("Failed to refresh cache entry: %s", e)
            finally:
                self._refreshing = False


class ServiceCache:
    """Service discovery cache with multiple strategies."""

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = {"hits": 0, "misses": 0, "refreshes": 0, "evictions": 0}

    def _generate_cache_key(self, query: ServiceQuery) -> str:
        """Generate cache key for service query."""
        key_parts = [
            query.service_name,
            query.version or "*",
            query.environment or "*",
            query.zone or "*",
            query.region or "*",
        ]

        # Add sorted tags and labels
        if query.tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(query.tags.items()))
            key_parts.append(f"tags:{tag_str}")

        if query.labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(query.labels.items()))
            key_parts.append(f"labels:{label_str}")

        if query.protocols:
            proto_str = ",".join(sorted(query.protocols))
            key_parts.append(f"protocols:{proto_str}")

        return "|".join(key_parts)

    async def get(
        self, query: ServiceQuery, refresh_callback: Optional[Callable] = None
    ) -> Optional[List[ServiceInstance]]:
        """Get instances from cache."""

        if self.config.cache_strategy == CacheStrategy.NONE:
            return None

        cache_key = self._generate_cache_key(query)

        async with self._lock:
            entry = self._cache.get(cache_key)

            if not entry:
                self._stats["misses"] += 1
                return None

            # Check expiration
            if entry.is_expired():
                del self._cache[cache_key]
                self._stats["misses"] += 1
                return None

            # Handle refresh-ahead strategy
            if (
                self.config.cache_strategy == CacheStrategy.REFRESH_AHEAD
                and refresh_callback
            ):
                # Trigger async refresh if needed
                if entry.should_refresh(self.config.refresh_ahead_factor):
                    asyncio.create_task(
                        self._refresh_entry(cache_key, entry, refresh_callback)
                    )

            self._stats["hits"] += 1
            return entry.access()

    async def put(
        self,
        query: ServiceQuery,
        instances: List[ServiceInstance],
        refresh_callback: Optional[Callable] = None,
    ):
        """Put instances in cache."""

        if self.config.cache_strategy == CacheStrategy.NONE:
            return

        cache_key = self._generate_cache_key(query)

        async with self._lock:
            # Check cache size and evict if necessary
            if len(self._cache) >= self.config.cache_max_size:
                await self._evict_lru()

            # Create cache entry
            entry = CacheEntry(instances, self.config.cache_ttl, refresh_callback)
            self._cache[cache_key] = entry

    async def _refresh_entry(
        self, cache_key: str, entry: CacheEntry, refresh_callback: Callable
    ):
        """Refresh cache entry asynchronously."""
        try:
            new_instances = await refresh_callback()
            if new_instances:
                async with self._lock:
                    if cache_key in self._cache:  # Entry might have been evicted
                        entry.instances = new_instances
                        entry.created_at = time.time()
                        self._stats["refreshes"] += 1
        except Exception as e:
            logger.warning("Failed to refresh cache entry %s: %s", cache_key, e)

    async def _evict_lru(self):
        """Evict least recently used cache entry."""
        if not self._cache:
            return

        # Find LRU entry
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]
        self._stats["evictions"] += 1

    async def invalidate(self, service_name: str):
        """Invalidate cache entries for a service."""
        async with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys() if key.startswith(f"{service_name}|")
            ]

            for key in keys_to_remove:
                del self._cache[key]

    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache),
        }


class ServiceDiscoveryClient(ABC):
    """Abstract service discovery client."""

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.cache = ServiceCache(config)
        self._load_balancer: Optional[LoadBalancer] = None

        # Initialize load balancer if enabled
        if config.load_balancing_enabled:
            lb_config = config.load_balancing_config or LoadBalancingConfig()
            self._load_balancer = create_load_balancer(lb_config)

        # Statistics
        self._stats = {
            "resolutions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "failures": 0,
            "average_resolution_time": 0.0,
            "total_resolution_time": 0.0,
        }

    @abstractmethod
    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover service instances."""
        pass

    async def resolve_service(
        self, query: ServiceQuery, context: Optional[LoadBalancingContext] = None
    ) -> Optional[ServiceInstance]:
        """Resolve service to a single instance using load balancing."""

        # Discover instances
        result = await self.discover_instances(query)

        if not result.instances:
            return None

        # Use load balancer if enabled and configured
        if self._load_balancer:
            await self._load_balancer.update_instances(result.instances)
            selected = await self._load_balancer.select_with_fallback(context)

            if selected:
                result.selected_instance = selected
                result.load_balancer_used = True
                return selected

        # Fallback to simple selection
        return self._simple_instance_selection(result.instances, query)

    def _simple_instance_selection(
        self, instances: List[ServiceInstance], query: ServiceQuery
    ) -> ServiceInstance:
        """Simple instance selection without load balancer."""

        # Apply zone/region preferences
        preferred_instances = instances

        if self.config.zone_aware and query.prefer_zone:
            zone_instances = [i for i in instances if i.zone == query.prefer_zone]
            if zone_instances:
                preferred_instances = zone_instances

        elif self.config.region_aware and query.prefer_region:
            region_instances = [i for i in instances if i.region == query.prefer_region]
            if region_instances:
                preferred_instances = region_instances

        # Apply max instances limit
        if query.max_instances and len(preferred_instances) > query.max_instances:
            preferred_instances = preferred_instances[: query.max_instances]

        # Random selection
        return random.choice(preferred_instances)

    def record_resolution(self, success: bool, resolution_time: float):
        """Record resolution statistics."""
        self._stats["resolutions"] += 1

        if success:
            self._stats["total_resolution_time"] += resolution_time
            self._stats["average_resolution_time"] = (
                self._stats["total_resolution_time"] / self._stats["resolutions"]
            )
        else:
            self._stats["failures"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get discovery client statistics."""
        cache_stats = self.cache.get_stats()

        failure_rate = 0.0
        if self._stats["resolutions"] > 0:
            failure_rate = self._stats["failures"] / self._stats["resolutions"]

        stats = {**self._stats, "failure_rate": failure_rate, "cache": cache_stats}

        if self._load_balancer:
            stats["load_balancer"] = self._load_balancer.get_stats()

        return stats


class ClientSideDiscovery(ServiceDiscoveryClient):
    """Client-side service discovery implementation."""

    def __init__(self, registry: ServiceRegistry, config: DiscoveryConfig):
        super().__init__(config)
        self.registry = registry
        self._watchers: Dict[str, ServiceWatcher] = {}

    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover instances using client-side discovery."""
        start_time = time.time()

        try:
            # Try cache first
            cached_instances = await self.cache.get(
                query, lambda: self._fetch_from_registry(query)
            )

            if cached_instances is not None:
                self._stats["cache_hits"] += 1
                resolution_time = time.time() - start_time

                return DiscoveryResult(
                    instances=cached_instances,
                    query=query,
                    source="cache",
                    cached=True,
                    cache_age=0.0,  # TODO: Calculate actual cache age
                    resolution_time=resolution_time,
                )

            # Fetch from registry
            self._stats["cache_misses"] += 1
            instances = await self._fetch_from_registry(query)

            # Cache the result
            await self.cache.put(
                query, instances, lambda: self._fetch_from_registry(query)
            )

            resolution_time = time.time() - start_time
            self.record_resolution(True, resolution_time)

            return DiscoveryResult(
                instances=instances,
                query=query,
                source="registry",
                cached=False,
                resolution_time=resolution_time,
            )

        except Exception as e:
            resolution_time = time.time() - start_time
            self.record_resolution(False, resolution_time)
            logger.error("Service discovery failed for %s: %s", query.service_name, e)
            raise

    async def _fetch_from_registry(self, query: ServiceQuery) -> List[ServiceInstance]:
        """Fetch instances from service registry."""
        all_instances = await self.registry.get_instances(query.service_name)

        # Filter instances based on query criteria
        filtered_instances = [
            instance for instance in all_instances if query.matches_instance(instance)
        ]

        return filtered_instances

    async def watch_service(
        self, service_name: str, callback: Callable[[List[ServiceInstance]], None]
    ):
        """Watch service for changes."""

        if service_name not in self._watchers:
            watcher = await self.registry.watch_service(service_name, callback)
            self._watchers[service_name] = watcher

        return self._watchers[service_name]

    async def stop_watching(self, service_name: str):
        """Stop watching service."""
        watcher = self._watchers.pop(service_name, None)
        if watcher:
            await watcher.stop()


class ServerSideDiscovery(ServiceDiscoveryClient):
    """Server-side service discovery implementation using discovery service."""

    def __init__(self, discovery_service_url: str, config: DiscoveryConfig):
        super().__init__(config)
        self.discovery_service_url = discovery_service_url
        # TODO: Add HTTP client for discovery service communication

    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover instances using server-side discovery service."""
        start_time = time.time()

        try:
            # Check cache first
            cached_instances = await self.cache.get(query)

            if cached_instances is not None:
                self._stats["cache_hits"] += 1
                resolution_time = time.time() - start_time

                return DiscoveryResult(
                    instances=cached_instances,
                    query=query,
                    source="cache",
                    cached=True,
                    resolution_time=resolution_time,
                )

            # Query discovery service
            self._stats["cache_misses"] += 1
            instances = await self._query_discovery_service(query)

            # Cache the result
            await self.cache.put(query, instances)

            resolution_time = time.time() - start_time
            self.record_resolution(True, resolution_time)

            return DiscoveryResult(
                instances=instances,
                query=query,
                source="discovery_service",
                cached=False,
                resolution_time=resolution_time,
            )

        except Exception as e:
            resolution_time = time.time() - start_time
            self.record_resolution(False, resolution_time)
            logger.error(
                "Server-side discovery failed for %s: %s", query.service_name, e
            )
            raise

    async def _query_discovery_service(
        self, query: ServiceQuery
    ) -> List[ServiceInstance]:
        """Query external discovery service."""
        # TODO: Implement HTTP client to query discovery service
        # This would make HTTP requests to discovery service API
        # For now, return empty list
        return []


class HybridDiscovery(ServiceDiscoveryClient):
    """Hybrid discovery combining client-side and server-side approaches."""

    def __init__(
        self,
        client_side: ClientSideDiscovery,
        server_side: ServerSideDiscovery,
        config: DiscoveryConfig,
    ):
        super().__init__(config)
        self.client_side = client_side
        self.server_side = server_side
        self.prefer_client_side = True  # Configurable preference

    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover instances using hybrid approach."""

        primary = self.client_side if self.prefer_client_side else self.server_side
        fallback = self.server_side if self.prefer_client_side else self.client_side

        try:
            # Try primary discovery method
            return await primary.discover_instances(query)

        except Exception as e:
            logger.warning("Primary discovery failed, trying fallback: %s", e)

            try:
                # Try fallback method
                result = await fallback.discover_instances(query)
                result.metadata["fallback_used"] = True
                return result

            except Exception as fallback_error:
                logger.error("Both discovery methods failed: %s", fallback_error)
                raise


class ServiceMeshDiscovery(ServiceDiscoveryClient):
    """Service mesh integration for discovery."""

    def __init__(self, mesh_config: Dict[str, Any], config: DiscoveryConfig):
        super().__init__(config)
        self.mesh_config = mesh_config
        # TODO: Add service mesh integration (Istio, Linkerd, etc.)

    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover instances through service mesh."""
        # TODO: Implement service mesh discovery
        # This would integrate with service mesh control plane
        return DiscoveryResult(
            instances=[],
            query=query,
            source="service_mesh",
            cached=False,
            resolution_time=0.0,
        )


def create_discovery_client(
    pattern: DiscoveryPattern, config: DiscoveryConfig, **kwargs
) -> ServiceDiscoveryClient:
    """Factory function to create discovery client."""

    if pattern == DiscoveryPattern.CLIENT_SIDE:
        registry = kwargs.get("registry")
        if not registry:
            raise ValueError("Registry required for client-side discovery")
        return ClientSideDiscovery(registry, config)

    elif pattern == DiscoveryPattern.SERVER_SIDE:
        discovery_url = kwargs.get("discovery_service_url")
        if not discovery_url:
            raise ValueError("Discovery service URL required for server-side discovery")
        return ServerSideDiscovery(discovery_url, config)

    elif pattern == DiscoveryPattern.HYBRID:
        client_side = kwargs.get("client_side")
        server_side = kwargs.get("server_side")
        if not client_side or not server_side:
            raise ValueError(
                "Both client-side and server-side clients required for hybrid discovery"
            )
        return HybridDiscovery(client_side, server_side, config)

    elif pattern == DiscoveryPattern.SERVICE_MESH:
        mesh_config = kwargs.get("mesh_config", {})
        return ServiceMeshDiscovery(mesh_config, config)

    else:
        raise ValueError(f"Unsupported discovery pattern: {pattern}")
