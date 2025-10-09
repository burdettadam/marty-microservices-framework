"""
Consul Service Discovery Plugin Example.

This plugin demonstrates how to implement service discovery
functionality using the service plugin interface.
"""

import asyncio
import json
from typing import Any, Dict, List

from ..decorators import plugin
from ..interfaces import IServicePlugin, PluginContext, PluginMetadata


@plugin(
    name="consul-service-discovery",
    version="1.0.0",
    description="Consul-based service discovery plugin",
    author="Marty Team",
    provides=["service-discovery", "consul", "health-checks"],
)
class ConsulServiceDiscoveryPlugin(IServicePlugin):
    """
    Consul service discovery plugin.

    This plugin demonstrates:
    - Service discovery implementation
    - External service integration
    - Health check propagation
    - Service registry hooks
    """

    def __init__(self):
        super().__init__()
        self.consul_host = "localhost"
        self.consul_port = 8500
        self.service_prefix = "marty"
        self.services_cache: Dict[str, Dict[str, Any]] = {}
        self.health_check_interval = 30
        self._health_check_task: asyncio.Task = None

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the Consul service discovery plugin."""
        await super().initialize(context)

        # Get configuration
        self.consul_host = context.get_config("consul_host", "localhost")
        self.consul_port = context.get_config("consul_port", 8500)
        self.service_prefix = context.get_config("service_prefix", "marty")
        self.health_check_interval = context.get_config("health_check_interval", 30)

        # Register our service discovery service
        if context.service_registry:
            context.service_registry.register_service(
                "service-discovery",
                {
                    "type": "consul",
                    "plugin": self.plugin_metadata.name,
                    "consul_host": self.consul_host,
                    "consul_port": self.consul_port,
                    "tags": ["discovery", "consul", "registry"],
                },
            )

        self.logger.info(
            f"Consul service discovery initialized (consul://{self.consul_host}:{self.consul_port})"
        )

    async def start(self) -> None:
        """Start the service discovery plugin."""
        await super().start()

        # Start health check task
        self._health_check_task = asyncio.create_task(self._periodic_health_checks())

        self.logger.info("Consul service discovery started")

    async def stop(self) -> None:
        """Stop the service discovery plugin."""
        await super().stop()

        # Stop health check task
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Consul service discovery stopped")

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="consul-service-discovery",
            version="1.0.0",
            description="Consul-based service discovery plugin",
            author="Marty Team",
            provides=["service-discovery", "consul", "health-checks"],
        )

    async def on_service_register(self, service_info: Dict[str, Any]) -> None:
        """
        Called when a service is being registered.

        Register the service with Consul.
        """
        service_name = service_info.get("name", "unknown")
        service_id = f"{self.service_prefix}-{service_name}-{service_info.get('instance_id', 'default')}"

        consul_service = {
            "ID": service_id,
            "Name": f"{self.service_prefix}-{service_name}",
            "Tags": service_info.get("tags", []),
            "Address": service_info.get("host", "localhost"),
            "Port": service_info.get("port", 8080),
            "Meta": {
                "plugin": self.plugin_metadata.name,
                "framework": "marty-chassis",
                **service_info.get("metadata", {}),
            },
        }

        # Add health check if specified
        if service_info.get("health_check_url"):
            consul_service["Check"] = {
                "HTTP": service_info["health_check_url"],
                "Interval": f"{self.health_check_interval}s",
            }

        # Simulate Consul registration (in real implementation, use Consul API)
        await self._register_with_consul(consul_service)

        # Cache the service
        self.services_cache[service_id] = consul_service

        self.logger.info(
            f"Registered service with Consul: {service_name} (ID: {service_id})"
        )

    async def on_service_unregister(self, service_info: Dict[str, Any]) -> None:
        """
        Called when a service is being unregistered.

        Unregister the service from Consul.
        """
        service_name = service_info.get("name", "unknown")
        service_id = f"{self.service_prefix}-{service_name}-{service_info.get('instance_id', 'default')}"

        # Simulate Consul deregistration
        await self._deregister_with_consul(service_id)

        # Remove from cache
        if service_id in self.services_cache:
            del self.services_cache[service_id]

        self.logger.info(
            f"Unregistered service from Consul: {service_name} (ID: {service_id})"
        )

    async def on_service_discovery(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Called during service discovery.

        Query Consul for matching services.
        """
        service_name = query.get("name")
        tags = query.get("tags", [])

        # Simulate Consul query (in real implementation, use Consul API)
        services = await self._query_consul_services(service_name, tags)

        self.logger.debug(f"Service discovery query returned {len(services)} services")

        return services

    async def _register_with_consul(self, service: Dict[str, Any]) -> None:
        """
        Register a service with Consul.

        In a real implementation, this would make HTTP calls to Consul API.
        """
        # Simulate network call delay
        await asyncio.sleep(0.01)

        self.logger.debug(f"Registering with Consul: {json.dumps(service, indent=2)}")

        # In real implementation:
        # async with aiohttp.ClientSession() as session:
        #     url = f"http://{self.consul_host}:{self.consul_port}/v1/agent/service/register"
        #     async with session.put(url, json=service) as response:
        #         if response.status != 200:
        #             raise Exception(f"Failed to register service: {response.status}")

    async def _deregister_with_consul(self, service_id: str) -> None:
        """
        Deregister a service from Consul.

        In a real implementation, this would make HTTP calls to Consul API.
        """
        # Simulate network call delay
        await asyncio.sleep(0.01)

        self.logger.debug(f"Deregistering from Consul: {service_id}")

        # In real implementation:
        # async with aiohttp.ClientSession() as session:
        #     url = f"http://{self.consul_host}:{self.consul_port}/v1/agent/service/deregister/{service_id}"
        #     async with session.put(url) as response:
        #         if response.status != 200:
        #             raise Exception(f"Failed to deregister service: {response.status}")

    async def _query_consul_services(
        self, service_name: str = None, tags: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query Consul for services.

        In a real implementation, this would make HTTP calls to Consul API.
        """
        # Simulate network call delay
        await asyncio.sleep(0.01)

        # Return cached services for demo (in real implementation, query Consul)
        matching_services = []

        for service_id, service in self.services_cache.items():
            # Check service name match
            if service_name and not service["Name"].endswith(f"-{service_name}"):
                continue

            # Check tags match
            if tags:
                service_tags = set(service.get("Tags", []))
                if not set(tags).issubset(service_tags):
                    continue

            # Convert to discovery format
            discovered_service = {
                "id": service_id,
                "name": service["Name"],
                "address": service["Address"],
                "port": service["Port"],
                "tags": service.get("Tags", []),
                "metadata": service.get("Meta", {}),
                "healthy": True,  # In real implementation, check health from Consul
            }

            matching_services.append(discovered_service)

        return matching_services

    async def _periodic_health_checks(self) -> None:
        """Periodic health check monitoring."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                # In real implementation, query Consul for health status
                healthy_services = len([s for s in self.services_cache.values()])

                # Publish health status event
                if self.context and self.context.event_bus:
                    await self.context.event_bus.publish(
                        "service_discovery.health_check",
                        {
                            "plugin": self.plugin_metadata.name,
                            "total_services": len(self.services_cache),
                            "healthy_services": healthy_services,
                            "timestamp": asyncio.get_event_loop().time(),
                        },
                        source=self.plugin_metadata.name,
                    )

                self.logger.debug(
                    f"Health check completed: {healthy_services}/{len(self.services_cache)} services healthy"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in periodic health check: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health = await super().health_check()

        # Add Consul-specific health information
        consul_healthy = await self._check_consul_health()

        health["details"] = {
            "consul_host": self.consul_host,
            "consul_port": self.consul_port,
            "consul_healthy": consul_healthy,
            "cached_services": len(self.services_cache),
            "service_prefix": self.service_prefix,
        }

        health["healthy"] = health["healthy"] and consul_healthy

        return health

    async def _check_consul_health(self) -> bool:
        """Check if Consul is healthy."""
        try:
            # Simulate Consul health check
            await asyncio.sleep(0.01)

            # In real implementation:
            # async with aiohttp.ClientSession() as session:
            #     url = f"http://{self.consul_host}:{self.consul_port}/v1/status/leader"
            #     async with session.get(url) as response:
            #         return response.status == 200

            return True  # Assume healthy for demo

        except Exception as e:
            self.logger.error(f"Consul health check failed: {e}")
            return False
