"""
Performance Monitoring Plugin Example.

This plugin demonstrates performance monitoring with timers,
resource usage tracking, and alerting capabilities.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

import psutil

from ..decorators import plugin
from ..interfaces import IMetricsPlugin, PluginContext, PluginMetadata


@plugin(
    name="performance-monitor",
    version="1.0.0",
    description="Performance monitoring plugin with timers and alerting",
    author="Marty Team",
    provides=["performance", "monitoring", "alerting"],
)
class PerformanceMonitorPlugin(IMetricsPlugin):
    """
    Performance monitoring plugin for demonstration.

    This plugin demonstrates:
    - System resource monitoring with timers
    - Performance threshold alerting
    - Historical performance tracking
    - Anomaly detection simulation
    - Custom performance metrics
    """

    def __init__(self):
        super().__init__()

        # Configuration
        self.monitoring_interval = 2.0  # seconds
        self.history_size = 100  # number of samples to keep
        self.enable_alerting = True

        # Thresholds for alerting
        self.cpu_threshold = 80.0  # percent
        self.memory_threshold = 85.0  # percent
        self.disk_threshold = 90.0  # percent
        self.response_time_threshold = 5.0  # seconds

        # Performance history
        self.performance_history: List[Dict[str, Any]] = []
        self.alert_history: List[Dict[str, Any]] = []

        # Monitoring state
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_alert_times: Dict[str, float] = {}
        self.alert_cooldown = 30.0  # seconds between similar alerts

        # Custom metrics
        self.request_times: List[float] = []
        self.error_count = 0
        self.alert_count = 0

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the performance monitoring plugin."""
        await super().initialize(context)

        # Get configuration
        self.monitoring_interval = context.get_config("monitoring_interval", 2.0)
        self.history_size = context.get_config("history_size", 100)
        self.enable_alerting = context.get_config("enable_alerting", True)

        # Get thresholds
        thresholds = context.get_config("thresholds", {})
        self.cpu_threshold = thresholds.get("cpu", 80.0)
        self.memory_threshold = thresholds.get("memory", 85.0)
        self.disk_threshold = thresholds.get("disk", 90.0)
        self.response_time_threshold = thresholds.get("response_time", 5.0)
        self.alert_cooldown = thresholds.get("alert_cooldown", 30.0)

        # Register monitoring service
        if context.service_registry:
            context.service_registry.register_service(
                "performance-monitor",
                {
                    "type": "monitoring",
                    "plugin": self.plugin_metadata.name,
                    "methods": [
                        "get_current_performance",
                        "get_performance_history",
                        "get_alerts",
                    ],
                    "tags": ["performance", "monitoring", "alerting"],
                },
            )

        self.logger.info("Performance monitoring plugin initialized")

    async def start(self) -> None:
        """Start the performance monitoring plugin."""
        await super().start()

        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitor_performance())

        # Subscribe to events for request time tracking
        if self.context and self.context.event_bus:
            self.context.event_bus.subscribe(
                "request.completed", self._on_request_completed
            )
            self.context.event_bus.subscribe("request.failed", self._on_request_failed)

        self.logger.info("Performance monitoring started")

    async def stop(self) -> None:
        """Stop the performance monitoring plugin."""
        await super().stop()

        # Stop monitoring task
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Performance monitoring stopped")

    @property
    def plugin_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="performance-monitor",
            version="1.0.0",
            description="Performance monitoring plugin with timers and alerting",
            author="Marty Team",
            provides=["performance", "monitoring", "alerting"],
        )

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics."""
        current_perf = await self._collect_current_performance()

        # Calculate derived metrics
        avg_response_time = (
            sum(self.request_times) / len(self.request_times)
            if self.request_times
            else 0
        )
        recent_cpu = [p["cpu_percent"] for p in self.performance_history[-10:]]
        avg_recent_cpu = sum(recent_cpu) / len(recent_cpu) if recent_cpu else 0

        return {
            # Current metrics
            "cpu_percent": current_perf["cpu_percent"],
            "memory_percent": current_perf["memory_percent"],
            "disk_percent": current_perf["disk_percent"],
            "load_average": current_perf["load_average"],
            # Derived metrics
            "average_response_time": avg_response_time,
            "average_recent_cpu": avg_recent_cpu,
            "error_count": self.error_count,
            "alert_count": self.alert_count,
            # Status metrics
            "monitoring_active": self._monitoring_task
            and not self._monitoring_task.done(),
            "history_entries": len(self.performance_history),
            "active_alerts": len(
                [a for a in self.alert_history if time.time() - a["timestamp"] < 300]
            ),  # 5 minutes
        }

    def get_metric_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Return metric definitions."""
        return {
            "cpu_percent": {
                "type": "gauge",
                "description": "Current CPU usage percentage",
                "unit": "percent",
            },
            "memory_percent": {
                "type": "gauge",
                "description": "Current memory usage percentage",
                "unit": "percent",
            },
            "disk_percent": {
                "type": "gauge",
                "description": "Current disk usage percentage",
                "unit": "percent",
            },
            "load_average": {
                "type": "gauge",
                "description": "System load average (1 minute)",
                "unit": "load",
            },
            "average_response_time": {
                "type": "gauge",
                "description": "Average response time for requests",
                "unit": "seconds",
            },
            "error_count": {
                "type": "counter",
                "description": "Total number of errors detected",
                "unit": "errors",
            },
            "alert_count": {
                "type": "counter",
                "description": "Total number of alerts generated",
                "unit": "alerts",
            },
        }

    async def get_current_performance(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return await self._collect_current_performance()

    async def get_performance_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get performance history."""
        return self.performance_history[-limit:]

    async def get_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        return self.alert_history[-limit:]

    async def _monitor_performance(self) -> None:
        """Main monitoring loop."""
        while True:
            try:
                await asyncio.sleep(self.monitoring_interval)

                # Collect performance data
                perf_data = await self._collect_current_performance()

                # Add to history
                self.performance_history.append(perf_data)

                # Trim history if needed
                if len(self.performance_history) > self.history_size:
                    self.performance_history = self.performance_history[
                        -self.history_size :
                    ]

                # Check for alerts
                if self.enable_alerting:
                    await self._check_alerts(perf_data)

                # Publish performance update event
                if self.context and self.context.event_bus:
                    await self.context.event_bus.publish(
                        "performance.update",
                        perf_data,
                        source=self.plugin_metadata.name,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in performance monitoring: {e}")
                self.error_count += 1

    async def _collect_current_performance(self) -> Dict[str, Any]:
        """Collect current system performance metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)

            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Disk metrics
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100

            # Load average (Unix-like systems)
            try:
                load_avg = psutil.getloadavg()[0]  # 1-minute average
            except (AttributeError, OSError):
                load_avg = 0.0  # Not available on all systems

            # Network I/O (simple metric)
            net_io = psutil.net_io_counters()

            return {
                "timestamp": time.time(),
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_used_gb": memory.used / (1024**3),
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk_percent,
                "disk_used_gb": disk.used / (1024**3),
                "disk_free_gb": disk.free / (1024**3),
                "load_average": load_avg,
                "network_bytes_sent": net_io.bytes_sent,
                "network_bytes_recv": net_io.bytes_recv,
            }

        except Exception as e:
            self.logger.error(f"Error collecting performance metrics: {e}")
            self.error_count += 1
            return {
                "timestamp": time.time(),
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_percent": 0.0,
                "load_average": 0.0,
                "error": str(e),
            }

    async def _check_alerts(self, perf_data: Dict[str, Any]) -> None:
        """Check performance data against thresholds and generate alerts."""
        current_time = time.time()

        # CPU alert
        if perf_data["cpu_percent"] > self.cpu_threshold:
            await self._generate_alert(
                "high_cpu",
                f"High CPU usage: {perf_data['cpu_percent']:.1f}% (threshold: {self.cpu_threshold}%)",
                {
                    "cpu_percent": perf_data["cpu_percent"],
                    "threshold": self.cpu_threshold,
                },
                current_time,
            )

        # Memory alert
        if perf_data["memory_percent"] > self.memory_threshold:
            await self._generate_alert(
                "high_memory",
                f"High memory usage: {perf_data['memory_percent']:.1f}% (threshold: {self.memory_threshold}%)",
                {
                    "memory_percent": perf_data["memory_percent"],
                    "threshold": self.memory_threshold,
                },
                current_time,
            )

        # Disk alert
        if perf_data["disk_percent"] > self.disk_threshold:
            await self._generate_alert(
                "high_disk",
                f"High disk usage: {perf_data['disk_percent']:.1f}% (threshold: {self.disk_threshold}%)",
                {
                    "disk_percent": perf_data["disk_percent"],
                    "threshold": self.disk_threshold,
                },
                current_time,
            )

        # Response time alert (if we have recent request data)
        if self.request_times:
            recent_requests = self.request_times[-10:]  # Last 10 requests
            avg_response_time = sum(recent_requests) / len(recent_requests)

            if avg_response_time > self.response_time_threshold:
                await self._generate_alert(
                    "slow_response",
                    f"Slow response time: {avg_response_time:.2f}s (threshold: {self.response_time_threshold}s)",
                    {
                        "avg_response_time": avg_response_time,
                        "threshold": self.response_time_threshold,
                    },
                    current_time,
                )

    async def _generate_alert(
        self, alert_type: str, message: str, data: Dict[str, Any], timestamp: float
    ) -> None:
        """Generate an alert if not in cooldown period."""
        # Check cooldown
        last_alert_time = self._last_alert_times.get(alert_type, 0)
        if timestamp - last_alert_time < self.alert_cooldown:
            return  # Still in cooldown

        # Generate alert
        alert = {
            "type": alert_type,
            "message": message,
            "data": data,
            "timestamp": timestamp,
            "severity": self._get_alert_severity(alert_type, data),
        }

        self.alert_history.append(alert)
        self.alert_count += 1
        self._last_alert_times[alert_type] = timestamp

        # Publish alert event
        if self.context and self.context.event_bus:
            await self.context.event_bus.publish(
                "performance.alert", alert, source=self.plugin_metadata.name
            )

        self.logger.warning(f"Performance alert: {message}")

    def _get_alert_severity(self, alert_type: str, data: Dict[str, Any]) -> str:
        """Determine alert severity based on type and values."""
        if alert_type == "high_cpu":
            cpu = data.get("cpu_percent", 0)
            if cpu > 95:
                return "critical"
            elif cpu > 90:
                return "high"
            else:
                return "medium"

        elif alert_type == "high_memory":
            memory = data.get("memory_percent", 0)
            if memory > 95:
                return "critical"
            elif memory > 90:
                return "high"
            else:
                return "medium"

        elif alert_type == "high_disk":
            disk = data.get("disk_percent", 0)
            if disk > 98:
                return "critical"
            elif disk > 95:
                return "high"
            else:
                return "medium"

        elif alert_type == "slow_response":
            response_time = data.get("avg_response_time", 0)
            if response_time > 10:
                return "critical"
            elif response_time > 7:
                return "high"
            else:
                return "medium"

        return "medium"

    async def _on_request_completed(self, message) -> None:
        """Handle request completed event."""
        # Extract processing time if available
        processing_time = getattr(message, "processing_time", None)
        if processing_time:
            self.request_times.append(processing_time)

            # Keep only recent requests
            if len(self.request_times) > 100:
                self.request_times = self.request_times[-100:]

    async def _on_request_failed(self, message) -> None:
        """Handle request failed event."""
        self.error_count += 1

        # Also track response time for failed requests
        processing_time = getattr(message, "processing_time", None)
        if processing_time:
            self.request_times.append(processing_time)

            # Keep only recent requests
            if len(self.request_times) > 100:
                self.request_times = self.request_times[-100:]

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check with monitoring status."""
        health = await super().health_check()

        # Add monitoring-specific health information
        recent_alerts = [
            a for a in self.alert_history if time.time() - a["timestamp"] < 300
        ]
        critical_alerts = [a for a in recent_alerts if a.get("severity") == "critical"]

        health["details"] = {
            "monitoring_active": self._monitoring_task
            and not self._monitoring_task.done(),
            "monitoring_interval": self.monitoring_interval,
            "history_entries": len(self.performance_history),
            "recent_alerts": len(recent_alerts),
            "critical_alerts": len(critical_alerts),
            "error_count": self.error_count,
            "request_samples": len(self.request_times),
        }

        # Health status based on critical alerts
        health["healthy"] = len(critical_alerts) == 0 and (
            self._monitoring_task and not self._monitoring_task.done()
        )

        return health
