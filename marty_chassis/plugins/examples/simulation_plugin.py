"""
Simulation Plugin Example.

This plugin demonstrates simulated work with timers, error scenarios,
and observability features for testing and demonstration purposes.
"""

import asyncio
import random
import time
from typing import Any, Dict

from ..decorators import plugin
from ..interfaces import IServicePlugin, PluginContext, PluginMetadata


@plugin(
    name="simulation-service",
    version="1.0.0",
    description="Simulation service plugin with timers and error scenarios",
    author="Marty Team",
    provides=["simulation", "testing", "demo"],
)
class SimulationServicePlugin(IServicePlugin):
    """
    Simulation service plugin for demonstration and testing.

    This plugin demonstrates:
    - Simulated work with configurable delays
    - Random error generation for testing error handling
    - Periodic background tasks
    - Observability through metrics and events
    - Configuration-driven behavior
    """

    def __init__(self):
        super().__init__()
        self.work_simulation_enabled = True
        self.error_rate = 0.1  # 10% error rate by default
        self.min_work_delay = 0.1  # Minimum work delay in seconds
        self.max_work_delay = 2.0  # Maximum work delay in seconds
        self.background_task_interval = 5.0  # Background task interval

        # Metrics tracking
        self.work_requests = 0
        self.successful_work = 0
        self.failed_work = 0
        self.total_work_time = 0.0

        # Background task
        self._background_task: asyncio.Task = None

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the simulation plugin."""
        await super().initialize(context)

        # Get configuration
        self.work_simulation_enabled = context.get_config(
            "work_simulation_enabled", True
        )
        self.error_rate = context.get_config("error_rate", 0.1)
        self.min_work_delay = context.get_config("min_work_delay", 0.1)
        self.max_work_delay = context.get_config("max_work_delay", 2.0)
        self.background_task_interval = context.get_config(
            "background_task_interval", 5.0
        )

        # Register simulation service
        if context.service_registry:
            context.service_registry.register_service(
                "simulation",
                {
                    "type": "simulation",
                    "plugin": self.plugin_metadata.name,
                    "methods": ["simulate_work", "get_stats", "trigger_error"],
                    "tags": ["simulation", "testing", "demo"],
                },
            )

        self.logger.info(
            f"Simulation plugin initialized with error_rate={self.error_rate}"
        )

    async def start(self) -> None:
        """Start the simulation plugin."""
        await super().start()

        # Start background task
        if self.work_simulation_enabled:
            self._background_task = asyncio.create_task(
                self._background_work_simulation()
            )

        # Publish plugin started event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "simulation.plugin.started",
                {
                    "plugin": self.plugin_metadata.name,
                    "config": {
                        "error_rate": self.error_rate,
                        "work_delay_range": [self.min_work_delay, self.max_work_delay],
                        "background_interval": self.background_task_interval,
                    },
                },
                source=self.plugin_metadata.name,
            )

        self.logger.info("Simulation plugin started")

    async def stop(self) -> None:
        """Stop the simulation plugin."""
        await super().stop()

        # Stop background task
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Simulation plugin stopped")

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return self._plugin_metadata

    async def simulate_work(
        self, work_type: str = "default", complexity: int = 1
    ) -> Dict[str, Any]:
        """
        Simulate work with configurable delay and error scenarios.

        Args:
            work_type: Type of work being simulated
            complexity: Complexity multiplier for work duration

        Returns:
            Result of the simulated work

        Raises:
            Exception: Random errors based on configured error rate
        """
        start_time = time.time()
        self.work_requests += 1

        # Calculate work duration based on complexity
        base_delay = random.uniform(self.min_work_delay, self.max_work_delay)
        work_duration = base_delay * complexity

        self.logger.debug(
            f"Starting simulated work: {work_type} (complexity={complexity}, duration={work_duration:.2f}s)"
        )

        try:
            # Simulate work delay
            await asyncio.sleep(work_duration)

            # Random error generation
            if random.random() < self.error_rate:
                error_types = [
                    "NetworkTimeout",
                    "DatabaseConnectionError",
                    "ValidationError",
                    "ResourceNotFound",
                    "InternalServerError",
                ]
                error_type = random.choice(error_types)
                raise Exception(f"Simulated {error_type}: Work failed randomly")

            # Successful work
            actual_duration = time.time() - start_time
            self.successful_work += 1
            self.total_work_time += actual_duration

            result = {
                "success": True,
                "work_type": work_type,
                "complexity": complexity,
                "duration": actual_duration,
                "timestamp": time.time(),
                "request_id": f"sim-{self.work_requests}",
            }

            # Publish success event
            if self.context and self.context.event_bus:
                await self.context.event_bus.publish(
                    "simulation.work.completed",
                    result,
                    source=self.plugin_metadata.name,
                )

            self.logger.info(
                f"Simulated work completed: {work_type} in {actual_duration:.2f}s"
            )
            return result

        except Exception as e:
            # Error handling
            actual_duration = time.time() - start_time
            self.failed_work += 1

            error_result = {
                "success": False,
                "work_type": work_type,
                "complexity": complexity,
                "duration": actual_duration,
                "error": str(e),
                "timestamp": time.time(),
                "request_id": f"sim-{self.work_requests}",
            }

            # Publish error event
            if self.context and self.context.event_bus:
                await self.context.event_bus.publish(
                    "simulation.work.failed",
                    error_result,
                    source=self.plugin_metadata.name,
                )

            self.logger.error(f"Simulated work failed: {work_type} - {e}")
            raise

    async def get_stats(self) -> Dict[str, Any]:
        """Get simulation statistics."""
        total_requests = self.work_requests
        success_rate = (
            (self.successful_work / total_requests) if total_requests > 0 else 0
        )
        avg_duration = (
            (self.total_work_time / self.successful_work)
            if self.successful_work > 0
            else 0
        )

        return {
            "total_requests": total_requests,
            "successful_work": self.successful_work,
            "failed_work": self.failed_work,
            "success_rate": success_rate,
            "average_duration": avg_duration,
            "total_work_time": self.total_work_time,
            "configured_error_rate": self.error_rate,
            "work_delay_range": [self.min_work_delay, self.max_work_delay],
        }

    async def trigger_error(self, error_type: str = "manual") -> None:
        """Manually trigger an error for testing."""
        error_message = f"Manually triggered error: {error_type}"

        # Publish error event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "simulation.error.triggered",
                {
                    "error_type": error_type,
                    "message": error_message,
                    "timestamp": time.time(),
                },
                source=self.plugin_metadata.name,
            )

        self.logger.warning(f"Manual error triggered: {error_type}")
        raise Exception(error_message)

    async def _background_work_simulation(self) -> None:
        """Background task that simulates periodic work."""
        while True:
            try:
                await asyncio.sleep(self.background_task_interval)

                # Simulate background work
                work_types = [
                    "background_sync",
                    "health_check",
                    "cleanup",
                    "maintenance",
                ]
                work_type = random.choice(work_types)
                complexity = random.randint(1, 3)

                try:
                    await self.simulate_work(work_type, complexity)
                except Exception as e:
                    # Background work errors should not stop the background task
                    self.logger.debug(f"Background work failed (expected): {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in background work simulation: {e}")

    async def on_service_register(self, service_info: Dict[str, Any]) -> None:
        """Called when a service is being registered."""
        # Simulate service registration processing
        await asyncio.sleep(0.01)  # Small delay to simulate work
        self.logger.debug(f"Service registered: {service_info.get('name', 'unknown')}")

    async def on_service_unregister(self, service_info: Dict[str, Any]) -> None:
        """Called when a service is being unregistered."""
        # Simulate service unregistration processing
        await asyncio.sleep(0.01)  # Small delay to simulate work
        self.logger.debug(
            f"Service unregistered: {service_info.get('name', 'unknown')}"
        )

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check with simulation data."""
        health = await super().health_check()

        # Add simulation-specific health information
        stats = await self.get_stats()
        health["details"] = {
            "work_simulation_enabled": self.work_simulation_enabled,
            "background_task_running": self._background_task
            and not self._background_task.done(),
            "error_rate": self.error_rate,
            "total_requests": stats["total_requests"],
            "success_rate": stats["success_rate"],
            "average_duration": stats["average_duration"],
        }

        # Health status based on success rate
        if stats["total_requests"] > 10:  # Only evaluate after some requests
            health["healthy"] = (
                stats["success_rate"] > 0.5
            )  # Healthy if >50% success rate

        return health
