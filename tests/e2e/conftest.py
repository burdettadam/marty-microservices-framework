"""
End-to-End Test Configuration and Fixtures for Marty Framework

This module provides comprehensive testing infrastructure for performance
analysis, bottleneck detection, timeout monitoring, and auditability testing.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
import pytest
import pytest_asyncio
from marty_chassis.plugins.examples import (
    CircuitBreakerPlugin,
    DataProcessingPipelinePlugin,
    PerformanceMonitorPlugin,
    SimulationServicePlugin,
)
from marty_chassis.plugins.manager import PluginManager


@dataclass
class PerformanceMetrics:
    """Container for performance metrics during testing."""

    cpu_usage: List[float] = field(default_factory=list)
    memory_usage: List[float] = field(default_factory=list)
    response_times: List[float] = field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    timeout_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def avg_response_time(self) -> float:
        """Calculate average response time."""
        return (
            sum(self.response_times) / len(self.response_times)
            if self.response_times
            else 0.0
        )

    @property
    def p95_response_time(self) -> float:
        """Calculate 95th percentile response time."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[index] if index < len(sorted_times) else sorted_times[-1]

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        total = self.error_count + self.success_count
        return (self.error_count / total * 100) if total > 0 else 0.0


@dataclass
class BottleneckAnalysis:
    """Analysis results for bottleneck detection."""

    service_name: str
    bottleneck_type: str  # 'cpu', 'memory', 'response_time', 'error_rate'
    severity: str  # 'low', 'medium', 'high', 'critical'
    current_value: float
    threshold_value: float
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AuditEvent:
    """Audit event for tracking system behavior."""

    timestamp: datetime
    service: str
    event_type: str  # 'performance', 'error', 'security', 'business'
    severity: str  # 'info', 'warning', 'error', 'critical'
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    request_id: Optional[str] = None


class PerformanceAnalyzer:
    """Analyzes performance metrics and identifies bottlenecks."""

    def __init__(self):
        self.metrics_history: Dict[str, List[PerformanceMetrics]] = defaultdict(list)
        self.bottlenecks: List[BottleneckAnalysis] = []
        self.audit_events: List[AuditEvent] = []

        # Thresholds for bottleneck detection
        self.thresholds = {
            "cpu_usage": 80.0,  # 80% CPU usage
            "memory_usage": 85.0,  # 85% memory usage
            "avg_response_time": 2.0,  # 2 seconds
            "p95_response_time": 5.0,  # 5 seconds
            "error_rate": 5.0,  # 5% error rate
        }

    def collect_metrics(self, service_name: str) -> PerformanceMetrics:
        """Collect current performance metrics."""
        process = psutil.Process()

        metrics = PerformanceMetrics(
            cpu_usage=[psutil.cpu_percent(interval=0.1)],
            memory_usage=[process.memory_percent()],
        )

        self.metrics_history[service_name].append(metrics)
        return metrics

    def analyze_bottlenecks(
        self, service_name: str, metrics: PerformanceMetrics
    ) -> List[BottleneckAnalysis]:
        """Analyze metrics for bottlenecks."""
        bottlenecks = []

        # CPU bottleneck analysis
        if metrics.cpu_usage and max(metrics.cpu_usage) > self.thresholds["cpu_usage"]:
            bottlenecks.append(
                BottleneckAnalysis(
                    service_name=service_name,
                    bottleneck_type="cpu",
                    severity="high" if max(metrics.cpu_usage) > 90 else "medium",
                    current_value=max(metrics.cpu_usage),
                    threshold_value=self.thresholds["cpu_usage"],
                    recommendations=[
                        "Consider horizontal scaling",
                        "Optimize CPU-intensive operations",
                        "Implement caching for computational results",
                    ],
                )
            )

        # Memory bottleneck analysis
        if (
            metrics.memory_usage
            and max(metrics.memory_usage) > self.thresholds["memory_usage"]
        ):
            bottlenecks.append(
                BottleneckAnalysis(
                    service_name=service_name,
                    bottleneck_type="memory",
                    severity="critical" if max(metrics.memory_usage) > 95 else "high",
                    current_value=max(metrics.memory_usage),
                    threshold_value=self.thresholds["memory_usage"],
                    recommendations=[
                        "Investigate memory leaks",
                        "Optimize data structures",
                        "Implement memory pooling",
                    ],
                )
            )

        # Response time bottleneck analysis
        if metrics.avg_response_time > self.thresholds["avg_response_time"]:
            bottlenecks.append(
                BottleneckAnalysis(
                    service_name=service_name,
                    bottleneck_type="response_time",
                    severity="high" if metrics.avg_response_time > 3.0 else "medium",
                    current_value=metrics.avg_response_time,
                    threshold_value=self.thresholds["avg_response_time"],
                    recommendations=[
                        "Optimize database queries",
                        "Implement response caching",
                        "Consider async processing for heavy operations",
                    ],
                )
            )

        # Error rate bottleneck analysis
        if metrics.error_rate > self.thresholds["error_rate"]:
            bottlenecks.append(
                BottleneckAnalysis(
                    service_name=service_name,
                    bottleneck_type="error_rate",
                    severity="critical" if metrics.error_rate > 15.0 else "high",
                    current_value=metrics.error_rate,
                    threshold_value=self.thresholds["error_rate"],
                    recommendations=[
                        "Investigate error root causes",
                        "Implement better error handling",
                        "Add circuit breaker patterns",
                    ],
                )
            )

        self.bottlenecks.extend(bottlenecks)
        return bottlenecks

    def create_audit_event(
        self,
        service: str,
        event_type: str,
        severity: str,
        message: str,
        metadata: Optional[Dict] = None,
    ) -> AuditEvent:
        """Create an audit event for tracking."""
        event = AuditEvent(
            timestamp=datetime.now(),
            service=service,
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
            request_id=f"req_{int(time.time() * 1000)}",
        )
        self.audit_events.append(event)
        return event

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_services": len(self.metrics_history),
                "total_bottlenecks": len(self.bottlenecks),
                "critical_bottlenecks": len(
                    [b for b in self.bottlenecks if b.severity == "critical"]
                ),
                "total_audit_events": len(self.audit_events),
                "error_events": len(
                    [e for e in self.audit_events if e.severity == "error"]
                ),
            },
            "bottlenecks": [
                {
                    "service": b.service_name,
                    "type": b.bottleneck_type,
                    "severity": b.severity,
                    "current_value": b.current_value,
                    "threshold": b.threshold_value,
                    "recommendations": b.recommendations,
                    "timestamp": b.timestamp.isoformat(),
                }
                for b in self.bottlenecks
            ],
            "audit_trail": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "service": e.service,
                    "type": e.event_type,
                    "severity": e.severity,
                    "message": e.message,
                    "metadata": e.metadata,
                    "request_id": e.request_id,
                }
                for e in self.audit_events
            ],
            "metrics_summary": {
                service: {
                    "total_measurements": len(metrics_list),
                    "avg_cpu": sum(
                        m.cpu_usage[0] if m.cpu_usage else 0 for m in metrics_list
                    )
                    / len(metrics_list)
                    if metrics_list
                    else 0,
                    "avg_memory": sum(
                        m.memory_usage[0] if m.memory_usage else 0 for m in metrics_list
                    )
                    / len(metrics_list)
                    if metrics_list
                    else 0,
                    "avg_response_time": sum(m.avg_response_time for m in metrics_list)
                    / len(metrics_list)
                    if metrics_list
                    else 0,
                }
                for service, metrics_list in self.metrics_history.items()
            },
        }


@pytest_asyncio.fixture
async def plugin_manager():
    """Create plugin manager for testing."""
    manager = PluginManager()
    yield manager
    await manager.shutdown()


@pytest_asyncio.fixture
async def performance_analyzer():
    """Create performance analyzer for testing."""
    return PerformanceAnalyzer()


@pytest_asyncio.fixture
async def simulation_plugin(plugin_manager):
    """Create and initialize simulation plugin."""
    plugin = SimulationServicePlugin()
    await plugin_manager.register_plugin(plugin)
    await plugin.initialize()
    yield plugin
    await plugin.shutdown()


@pytest_asyncio.fixture
async def pipeline_plugin(plugin_manager):
    """Create and initialize pipeline plugin."""
    plugin = DataProcessingPipelinePlugin()
    await plugin_manager.register_plugin(plugin)
    await plugin.initialize()
    yield plugin
    await plugin.shutdown()


@pytest_asyncio.fixture
async def monitoring_plugin(plugin_manager):
    """Create and initialize monitoring plugin."""
    plugin = PerformanceMonitorPlugin()
    await plugin_manager.register_plugin(plugin)
    await plugin.initialize()
    yield plugin
    await plugin.shutdown()


@pytest_asyncio.fixture
async def circuit_breaker_plugin(plugin_manager):
    """Create and initialize circuit breaker plugin."""
    plugin = CircuitBreakerPlugin()
    await plugin_manager.register_plugin(plugin)
    await plugin.initialize()
    yield plugin
    await plugin.shutdown()


@pytest.fixture
def test_report_dir():
    """Create directory for test reports."""
    report_dir = Path("test_reports")
    report_dir.mkdir(exist_ok=True)
    return report_dir


class TimeoutMonitor:
    """Monitor for timeout scenarios during testing."""

    def __init__(self, timeout_threshold: float = 5.0):
        self.timeout_threshold = timeout_threshold
        self.timeout_events: List[Dict[str, Any]] = []

    async def monitor_operation(
        self, operation_name: str, operation_func, *args, **kwargs
    ):
        """Monitor an operation for timeouts."""
        start_time = time.time()

        try:
            # Run operation with timeout
            result = await asyncio.wait_for(
                operation_func(*args, **kwargs), timeout=self.timeout_threshold
            )

            duration = time.time() - start_time

            # Log if operation took too long (90% of timeout)
            if duration > self.timeout_threshold * 0.9:
                self.timeout_events.append(
                    {
                        "operation": operation_name,
                        "duration": duration,
                        "threshold": self.timeout_threshold,
                        "status": "slow",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            return result

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self.timeout_events.append(
                {
                    "operation": operation_name,
                    "duration": duration,
                    "threshold": self.timeout_threshold,
                    "status": "timeout",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            raise

    def get_timeout_report(self) -> Dict[str, Any]:
        """Get timeout monitoring report."""
        return {
            "total_operations": len(self.timeout_events),
            "timeouts": len(
                [e for e in self.timeout_events if e["status"] == "timeout"]
            ),
            "slow_operations": len(
                [e for e in self.timeout_events if e["status"] == "slow"]
            ),
            "events": self.timeout_events,
        }


@pytest.fixture
def timeout_monitor():
    """Create timeout monitor for testing."""
    return TimeoutMonitor(timeout_threshold=5.0)
