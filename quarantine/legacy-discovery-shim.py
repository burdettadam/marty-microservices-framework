from __future__ import annotations

"""
Compatibility layer for service discovery components.

The legacy `discovery` module grew to more than a thousand lines and was exempt
from important lint checks. The implementation now lives in focused modules
(`config`, `cache`, `clients`, `factory`, `results`) and this file simply
re-exports the public API so existing imports keep working.
"""

from .cache import CacheEntry, ServiceCache
from .clients import (
    ClientSideDiscovery,
    HybridDiscovery,
    MockKubernetesClient,
    ServerSideDiscovery,
    ServiceDiscoveryClient,
    ServiceMeshDiscovery,
)
from .config import CacheStrategy, DiscoveryConfig, DiscoveryPattern, ServiceQuery
from .factory import create_discovery_client
from .results import DiscoveryResult

__all__ = [
    "CacheEntry",
    "CacheStrategy",
    "ClientSideDiscovery",
    "DiscoveryConfig",
    "DiscoveryPattern",
    "DiscoveryResult",
    "HybridDiscovery",
    "MockKubernetesClient",
    "ServerSideDiscovery",
    "ServiceCache",
    "ServiceDiscoveryClient",
    "ServiceMeshDiscovery",
    "ServiceQuery",
    "create_discovery_client",
]
