"""
Custom Metrics Plugin Example.

This plugin demonstrates how to implement custom metrics
collection using the metrics plugin interface.
"""

import asyncio
import time
from typing import Any

import psutil

from ..decorators import metrics_collector, plugin
from ..interfaces import IMetricsPlugin, PluginContext, PluginMetadata


@plugin(
    name="custom-metrics",
    version="1.0.0",
    description="Custom metrics collection plugin for system and application metrics",
    author="Marty Team",
    provides=["metrics", "system-metrics", "performance"],
)
class CustomMetricsPlugin(IMetricsPlugin):
    """
    Custom metrics collection plugin.

    This plugin demonstrates:
    - Metrics collection implementation
    - System metrics gathering
    - Custom metric definitions
    - Periodic collection
    """

    def __init__(self):
        super().__init__()
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.collection_interval = 30  # seconds
        self._collection_task: asyncio.Task = None

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the metrics plugin."""
        await super().initialize(context)

        # Get configuration
        self.collection_interval = context.get_config("metrics_collection_interval", 30)

        # Register metrics service
        if context.service_registry:
            context.service_registry.register_service(
                "custom-metrics",
                {
                    "type": "metrics",
                    "plugin": self.plugin_metadata.name,
                    "metrics": list(self.get_metric_definitions().keys()),
                    "tags": ["metrics", "monitoring", "system"],
                },
            )

        # Subscribe to events for request tracking
        if context.event_bus:
            context.event_bus.subscribe("request.completed", self._on_request_completed)
            context.event_bus.subscribe("request.failed", self._on_request_failed)

        self.logger.info("Custom metrics plugin initialized")

    async def start(self) -> None:
        """Start the metrics plugin."""
        await super().start()

        # Start periodic collection
        self._collection_task = asyncio.create_task(self._periodic_collection())

        self.logger.info("Custom metrics collection started")

    async def stop(self) -> None:
        """Stop the metrics plugin."""
        await super().stop()

        # Stop periodic collection
        if self._collection_task and not self._collection_task.done():
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Custom metrics collection stopped")

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="custom-metrics",
            version="1.0.0",
            description="Custom metrics collection plugin for system and application metrics",
            author="Marty Team",
            provides=["metrics", "system-metrics", "performance"],
        )

    async def collect_metrics(self) -> dict[str, Any]:
        """
        Collect all metrics.

        Returns:
            Dict containing all metric values
        """
        metrics = {}

        # Application metrics
        metrics.update(await self._collect_application_metrics())

        # System metrics
        metrics.update(await self._collect_system_metrics())

        # Plugin metrics
        metrics.update(await self._collect_plugin_metrics())

        return metrics

    def get_metric_definitions(self) -> dict[str, dict[str, Any]]:
        """
        Return metric definitions.

        Returns:
            Dict mapping metric names to their definitions
        """
        return {
            "app_uptime_seconds": {
                "type": "gauge",
                "description": "Application uptime in seconds",
                "unit": "seconds",
            },
            "app_requests_total": {
                "type": "counter",
                "description": "Total number of requests processed",
                "unit": "requests",
            },
            "app_errors_total": {
                "type": "counter",
                "description": "Total number of errors occurred",
                "unit": "errors",
            },
            "system_cpu_usage_percent": {
                "type": "gauge",
                "description": "CPU usage percentage",
                "unit": "percent",
            },
            "system_memory_usage_percent": {
                "type": "gauge",
                "description": "Memory usage percentage",
                "unit": "percent",
            },
            "system_memory_usage_bytes": {
                "type": "gauge",
                "description": "Memory usage in bytes",
                "unit": "bytes",
            },
            "system_disk_usage_percent": {
                "type": "gauge",
                "description": "Disk usage percentage",
                "unit": "percent",
            },
            "plugin_collection_duration_seconds": {
                "type": "histogram",
                "description": "Time taken to collect metrics",
                "unit": "seconds",
            },
        }

    async def _collect_application_metrics(self) -> dict[str, Any]:
        """Collect application-specific metrics."""
        uptime = time.time() - self.start_time

        return {
            "app_uptime_seconds": uptime,
            "app_requests_total": self.request_count,
            "app_errors_total": self.error_count,
        }

    async def _collect_system_metrics(self) -> dict[str, Any]:
        """Collect system metrics using psutil."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used = memory.used

            # Disk metrics
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100

            return {
                "system_cpu_usage_percent": cpu_percent,
                "system_memory_usage_percent": memory_percent,
                "system_memory_usage_bytes": memory_used,
                "system_disk_usage_percent": disk_percent,
            }

        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return {}

    async def _collect_plugin_metrics(self) -> dict[str, Any]:
        """Collect plugin-specific metrics."""
        collection_start = time.time()

        # Simulate collection work
        await asyncio.sleep(0.001)

        collection_duration = time.time() - collection_start

        return {"plugin_collection_duration_seconds": collection_duration}

    async def _periodic_collection(self) -> None:
        """Periodic metrics collection task."""
        while True:
            try:
                await asyncio.sleep(self.collection_interval)

                # Collect metrics
                metrics = await self.collect_metrics()

                # Publish metrics collected event
                if self.context and self.context.event_bus:
                    await self.context.event_bus.publish(
                        "metrics.collected",
                        {
                            "plugin": self.plugin_metadata.name,
                            "metrics": metrics,
                            "timestamp": time.time(),
                        },
                        source=self.plugin_metadata.name,
                    )

                self.logger.debug(f"Collected {len(metrics)} metrics")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in periodic metrics collection: {e}")

    async def _on_request_completed(self, message) -> None:
        """Handle request completed event."""
        self.request_count += 1

    async def _on_request_failed(self, message) -> None:
        """Handle request failed event."""
        self.error_count += 1

    async def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        health = await super().health_check()

        # Add metrics-specific health information
        health["details"] = {
            "collection_interval": self.collection_interval,
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "uptime": time.time() - self.start_time,
            "collection_task_running": self._collection_task
            and not self._collection_task.done(),
        }

        return health

    @metrics_collector("custom_plugin_status", "gauge")
    async def get_plugin_status_metric(self) -> int:
        """Example of metric collector decorator usage."""
        return 1 if self.state.value == "started" else 0
