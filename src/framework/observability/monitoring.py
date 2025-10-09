"""
Service health monitoring and metrics collection infrastructure.

Provides comprehensive monitoring capabilities including health checks, metrics collection,
centralized logging, and alerting for all microservices.
"""

from __future__ import annotations

import builtins
import logging
import socket
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, dict, list

import psutil

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthCheck:
    """Health check definition."""

    name: str
    check_func: Callable[[], bool]
    timeout: float = 5.0
    interval: float = 30.0
    enabled: bool = True
    last_run: datetime | None = None
    last_status: HealthStatus = HealthStatus.UNKNOWN
    failure_count: int = 0
    max_failures: int = 3


@dataclass
class Metric:
    """Metric data point."""

    name: str
    value: float
    type: MetricType
    labels: builtins.dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    help_text: str = ""


@dataclass
class Alert:
    """Alert definition."""

    id: str
    name: str
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    labels: builtins.dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and manages metrics."""

    def __init__(self):
        self._metrics: builtins.dict[str, Metric] = {}
        self._counters: builtins.dict[str, float] = defaultdict(float)
        self._gauges: builtins.dict[str, float] = {}
        self._histograms: builtins.dict[str, builtins.list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: builtins.dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Value to add (default 1.0)
            labels: Optional labels
        """
        labels = labels or {}
        key = f"{name}:{self._serialize_labels(labels)}"

        with self._lock:
            self._counters[key] += value
            self._metrics[key] = Metric(
                name=name,
                value=self._counters[key],
                type=MetricType.COUNTER,
                labels=labels,
            )

    def gauge(
        self, name: str, value: float, labels: builtins.dict[str, str] | None = None
    ) -> None:
        """Set a gauge metric.

        Args:
            name: Metric name
            value: Current value
            labels: Optional labels
        """
        labels = labels or {}
        key = f"{name}:{self._serialize_labels(labels)}"

        with self._lock:
            self._gauges[key] = value
            self._metrics[key] = Metric(
                name=name,
                value=value,
                type=MetricType.GAUGE,
                labels=labels,
            )

    def histogram(
        self, name: str, value: float, labels: builtins.dict[str, str] | None = None
    ) -> None:
        """Add a value to a histogram metric.

        Args:
            name: Metric name
            value: Value to add
            labels: Optional labels
        """
        labels = labels or {}
        key = f"{name}:{self._serialize_labels(labels)}"

        with self._lock:
            self._histograms[key].append(value)
            # Keep last 1000 values
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]

            # Create metric with summary stats
            values = self._histograms[key]
            self._metrics[key] = Metric(
                name=name,
                value=sum(values) / len(values),  # Average
                type=MetricType.HISTOGRAM,
                labels={**labels, "count": str(len(values))},
            )

    def get_metrics(self) -> builtins.list[Metric]:
        """Get all current metrics.

        Returns:
            List of current metrics
        """
        with self._lock:
            return list(self._metrics.values())

    def get_metric(
        self, name: str, labels: builtins.dict[str, str] | None = None
    ) -> Metric | None:
        """Get a specific metric.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Metric if found, None otherwise
        """
        labels = labels or {}
        key = f"{name}:{self._serialize_labels(labels)}"

        with self._lock:
            return self._metrics.get(key)

    def clear_metrics(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    @staticmethod
    def _serialize_labels(labels: builtins.dict[str, str]) -> str:
        """Serialize labels to a string key."""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


class HealthChecker:
    """Manages health checks."""

    def __init__(self):
        self._checks: builtins.dict[str, HealthCheck] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def register_check(self, health_check: HealthCheck) -> None:
        """Register a health check.

        Args:
            health_check: Health check to register
        """
        self._checks[health_check.name] = health_check
        logger.info("Registered health check: %s", health_check.name)

    def unregister_check(self, name: str) -> None:
        """Unregister a health check.

        Args:
            name: Name of health check to remove
        """
        if name in self._checks:
            del self._checks[name]
            logger.info("Unregistered health check: %s", name)

    def run_check(self, name: str) -> HealthStatus:
        """Run a specific health check.

        Args:
            name: Name of health check to run

        Returns:
            Health status result
        """
        if name not in self._checks:
            return HealthStatus.UNKNOWN

        check = self._checks[name]
        if not check.enabled:
            return HealthStatus.UNKNOWN

        try:
            # Run check with timeout
            result = self._run_with_timeout(check.check_func, check.timeout)

            if result:
                check.last_status = HealthStatus.HEALTHY
                check.failure_count = 0
            else:
                check.failure_count += 1
                if check.failure_count >= check.max_failures:
                    check.last_status = HealthStatus.UNHEALTHY
                else:
                    check.last_status = HealthStatus.DEGRADED

            check.last_run = datetime.now(timezone.utc)
            return check.last_status

        except Exception as e:
            logger.error("Health check %s failed: %s", name, e)
            check.failure_count += 1
            check.last_status = HealthStatus.UNHEALTHY
            check.last_run = datetime.now(timezone.utc)
            return HealthStatus.UNHEALTHY

    def run_all_checks(self) -> builtins.dict[str, HealthStatus]:
        """Run all registered health checks.

        Returns:
            Dictionary of check names to status
        """
        results = {}
        for name in self._checks:
            results[name] = self.run_check(name)
        return results

    def get_overall_status(self) -> HealthStatus:
        """Get overall health status.

        Returns:
            Overall health status based on all checks
        """
        results = self.run_all_checks()

        if not results:
            return HealthStatus.UNKNOWN

        if any(status == HealthStatus.UNHEALTHY for status in results.values()):
            return HealthStatus.UNHEALTHY
        if any(status == HealthStatus.DEGRADED for status in results.values()):
            return HealthStatus.DEGRADED
        if all(status == HealthStatus.HEALTHY for status in results.values()):
            return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN

    def start_periodic_checks(self) -> None:
        """Start periodic health check execution."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._periodic_check_loop, daemon=True)
        self._thread.start()
        logger.info("Started periodic health checks")

    def stop_periodic_checks(self) -> None:
        """Stop periodic health check execution."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5.0)

        logger.info("Stopped periodic health checks")

    def _periodic_check_loop(self) -> None:
        """Main loop for periodic health checks."""
        while self._running and not self._stop_event.is_set():
            try:
                current_time = datetime.now(timezone.utc)

                for check in self._checks.values():
                    if not check.enabled:
                        continue

                    # Check if it's time to run this check
                    if (
                        check.last_run is None
                        or (current_time - check.last_run).total_seconds()
                        >= check.interval
                    ):
                        self.run_check(check.name)

                # Sleep for a short interval
                self._stop_event.wait(timeout=5.0)

            except Exception as e:
                logger.error("Error in periodic health check loop: %s", e)
                self._stop_event.wait(timeout=10.0)

    @staticmethod
    def _run_with_timeout(func: Callable[[], bool], timeout: float) -> bool:
        """Run a function with timeout."""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                logger.warning("Health check timed out after %s seconds", timeout)
                return False


class SystemMetrics:
    """Collects system-level metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self._hostname = socket.gethostname()

    def collect_cpu_metrics(self) -> None:
        """Collect CPU metrics."""
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics.gauge(
            "system_cpu_usage_percent", cpu_percent, {"hostname": self._hostname}
        )

        # Per-core metrics
        cpu_percents = psutil.cpu_percent(percpu=True)
        for i, percent in enumerate(cpu_percents):
            self.metrics.gauge(
                "system_cpu_core_usage_percent",
                percent,
                {"hostname": self._hostname, "core": str(i)},
            )

    def collect_memory_metrics(self) -> None:
        """Collect memory metrics."""
        memory = psutil.virtual_memory()

        self.metrics.gauge(
            "system_memory_total_bytes", memory.total, {"hostname": self._hostname}
        )
        self.metrics.gauge(
            "system_memory_used_bytes", memory.used, {"hostname": self._hostname}
        )
        self.metrics.gauge(
            "system_memory_available_bytes",
            memory.available,
            {"hostname": self._hostname},
        )
        self.metrics.gauge(
            "system_memory_usage_percent", memory.percent, {"hostname": self._hostname}
        )

    def collect_disk_metrics(self) -> None:
        """Collect disk metrics."""
        disk = psutil.disk_usage("/")

        self.metrics.gauge(
            "system_disk_total_bytes", disk.total, {"hostname": self._hostname}
        )
        self.metrics.gauge(
            "system_disk_used_bytes", disk.used, {"hostname": self._hostname}
        )
        self.metrics.gauge(
            "system_disk_free_bytes", disk.free, {"hostname": self._hostname}
        )
        self.metrics.gauge(
            "system_disk_usage_percent",
            (disk.used / disk.total) * 100,
            {"hostname": self._hostname},
        )

    def collect_network_metrics(self) -> None:
        """Collect network metrics."""
        network = psutil.net_io_counters()

        self.metrics.counter(
            "system_network_bytes_sent",
            network.bytes_sent,
            {"hostname": self._hostname},
        )
        self.metrics.counter(
            "system_network_bytes_recv",
            network.bytes_recv,
            {"hostname": self._hostname},
        )
        self.metrics.counter(
            "system_network_packets_sent",
            network.packets_sent,
            {"hostname": self._hostname},
        )
        self.metrics.counter(
            "system_network_packets_recv",
            network.packets_recv,
            {"hostname": self._hostname},
        )

    def collect_all_metrics(self) -> None:
        """Collect all system metrics."""
        try:
            self.collect_cpu_metrics()
            self.collect_memory_metrics()
            self.collect_disk_metrics()
            self.collect_network_metrics()
        except Exception as e:
            logger.error("Error collecting system metrics: %s", e)


class ServiceMonitor:
    """Main service monitoring coordinator."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics = MetricsCollector()
        self.health_checker = HealthChecker()
        self.system_metrics = SystemMetrics(self.metrics)
        self.alerts: builtins.list[Alert] = []

        # Register default health checks
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """Register default health checks."""

        # Basic connectivity check
        def basic_check() -> bool:
            return True

        self.health_checker.register_check(
            HealthCheck(
                name="basic",
                check_func=basic_check,
                interval=10.0,
            )
        )

        # Memory usage check
        def memory_check() -> bool:
            memory = psutil.virtual_memory()
            return memory.percent < 90.0

        self.health_checker.register_check(
            HealthCheck(
                name="memory",
                check_func=memory_check,
                interval=30.0,
            )
        )

        # Disk usage check
        def disk_check() -> bool:
            disk = psutil.disk_usage("/")
            usage_percent = (disk.used / disk.total) * 100
            return usage_percent < 90.0

        self.health_checker.register_check(
            HealthCheck(
                name="disk",
                check_func=disk_check,
                interval=60.0,
            )
        )

    def start_monitoring(self) -> None:
        """Start all monitoring components."""
        self.health_checker.start_periodic_checks()
        logger.info("Service monitoring started for %s", self.service_name)

    def stop_monitoring(self) -> None:
        """Stop all monitoring components."""
        self.health_checker.stop_periodic_checks()
        logger.info("Service monitoring stopped for %s", self.service_name)

    def get_health_status(self) -> builtins.dict[str, Any]:
        """Get comprehensive health status.

        Returns:
            Health status dictionary
        """
        overall_status = self.health_checker.get_overall_status()
        check_results = self.health_checker.run_all_checks()

        return {
            "service": self.service_name,
            "status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {name: status.value for name, status in check_results.items()},
        }

    def get_metrics_summary(self) -> builtins.dict[str, Any]:
        """Get metrics summary.

        Returns:
            Metrics summary dictionary
        """
        # Collect current system metrics
        self.system_metrics.collect_all_metrics()

        metrics = self.metrics.get_metrics()

        return {
            "service": self.service_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics_count": len(metrics),
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "type": m.type.value,
                    "labels": m.labels,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in metrics
            ],
        }


# Timing context manager
@contextmanager
def time_operation(
    metrics_collector: MetricsCollector,
    operation_name: str,
    labels: builtins.dict[str, str] | None = None,
):
    """Context manager to time operations.

    Args:
        metrics_collector: Metrics collector instance
        operation_name: Name of the operation
        labels: Optional labels

    Example:
        with time_operation(metrics, "database_query", {"table": "users"}):
            # Database operation
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics_collector.histogram(
            f"{operation_name}_duration_seconds", duration, labels
        )


# Default health check functions
def database_health_check(connection_func: Callable[[], bool]) -> Callable[[], bool]:
    """Create a database health check.

    Args:
        connection_func: Function that tests database connectivity

    Returns:
        Health check function
    """

    def check() -> bool:
        try:
            return connection_func()
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return False

    return check


def external_service_health_check(url: str, timeout: float = 5.0) -> Callable[[], bool]:
    """Create an external service health check.

    Args:
        url: URL to check
        timeout: Request timeout

    Returns:
        Health check function
    """

    def check() -> bool:
        try:
            import requests

            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            logger.error("External service health check failed for %s: %s", url, e)
            return False

    return check
