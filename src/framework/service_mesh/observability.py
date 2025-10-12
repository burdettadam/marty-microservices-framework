"""
Observability and Monitoring

Comprehensive observability features including metrics collection,
distributed tracing, logging, and telemetry for service mesh monitoring.
"""

import asyncio
import builtins
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class TraceSpanKind(Enum):
    """Trace span kinds."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class LogLevel(Enum):
    """Log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class TelemetryProtocol(Enum):
    """Telemetry protocols."""

    PROMETHEUS = "prometheus"
    JAEGER = "jaeger"
    ZIPKIN = "zipkin"
    OPENTELEMETRY = "opentelemetry"
    DATADOG = "datadog"
    GRAFANA = "grafana"


@dataclass
class MetricData:
    """Metric data point."""

    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: builtins.dict[str, str] = field(default_factory=dict)
    help_text: str | None = None

    # Histogram/Summary specific
    buckets: builtins.list[float] | None = None
    quantiles: builtins.list[float] | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "help_text": self.help_text,
            "buckets": self.buckets,
            "quantiles": self.quantiles,
        }


@dataclass
class TraceSpan:
    """Distributed trace span."""

    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: str | None = None
    operation_name: str = ""
    service_name: str = ""

    # Timing
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    duration_ms: float | None = None

    # Span properties
    span_kind: TraceSpanKind = TraceSpanKind.INTERNAL
    status_code: int = 200
    error: bool = False

    # Context
    tags: builtins.dict[str, str] = field(default_factory=dict)
    logs: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    baggage: builtins.dict[str, str] = field(default_factory=dict)

    def finish(self) -> None:
        """Finish the span."""
        self.end_time = datetime.utcnow()
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def set_tag(self, key: str, value: str) -> None:
        """Set span tag."""
        self.tags[key] = value

    def log(self, message: str, level: str = "info", **kwargs) -> None:
        """Add log entry to span."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            **kwargs,
        }
        self.logs.append(log_entry)

    def set_error(self, error: Exception) -> None:
        """Set span as error."""
        self.error = True
        self.status_code = 500
        self.set_tag("error", "true")
        self.set_tag("error.message", str(error))
        self.set_tag("error.type", type(error).__name__)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "service_name": self.service_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "span_kind": self.span_kind.value,
            "status_code": self.status_code,
            "error": self.error,
            "tags": self.tags,
            "logs": self.logs,
            "baggage": self.baggage,
        }


@dataclass
class LogEntry:
    """Structured log entry."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: LogLevel = LogLevel.INFO
    message: str = ""
    service_name: str = ""

    # Context
    trace_id: str | None = None
    span_id: str | None = None
    user_id: str | None = None
    request_id: str | None = None

    # Metadata
    labels: builtins.dict[str, str] = field(default_factory=dict)
    fields: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "service_name": self.service_name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "labels": self.labels,
            "fields": self.fields,
        }


@dataclass
class Alert:
    """Alert definition."""

    name: str
    condition: str
    threshold: float
    severity: str = "warning"
    description: str = ""

    # Alert settings
    for_duration: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    labels: builtins.dict[str, str] = field(default_factory=dict)
    annotations: builtins.dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "condition": self.condition,
            "threshold": self.threshold,
            "severity": self.severity,
            "description": self.description,
            "for_duration": self.for_duration.total_seconds(),
            "labels": self.labels,
            "annotations": self.annotations,
        }


class MetricsCollector(ABC):
    """Abstract metrics collector interface."""

    @abstractmethod
    async def collect_metric(self, metric: MetricData) -> None:
        """Collect metric data."""
        raise NotImplementedError

    @abstractmethod
    async def get_metrics(
        self, name_pattern: str = None, labels: builtins.dict[str, str] = None
    ) -> builtins.list[MetricData]:
        """Get collected metrics."""
        raise NotImplementedError

    @abstractmethod
    async def export_metrics(self, format: str = "prometheus") -> str:
        """Export metrics in specified format."""
        raise NotImplementedError


class InMemoryMetricsCollector(MetricsCollector):
    """In-memory metrics collector implementation."""

    def __init__(self, max_metrics: int = 10000):
        self.max_metrics = max_metrics
        self._metrics: deque = deque(maxlen=max_metrics)
        self._counters: builtins.dict[str, float] = defaultdict(float)
        self._gauges: builtins.dict[str, float] = {}
        self._histograms: builtins.dict[str, builtins.list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def collect_metric(self, metric: MetricData) -> None:
        """Collect metric."""
        async with self._lock:
            self._metrics.append(metric)

            # Update metric stores
            metric_key = f"{metric.name}:{json.dumps(metric.labels, sort_keys=True)}"

            if metric.metric_type == MetricType.COUNTER:
                self._counters[metric_key] += metric.value
            elif metric.metric_type == MetricType.GAUGE:
                self._gauges[metric_key] = metric.value
            elif metric.metric_type == MetricType.HISTOGRAM:
                self._histograms[metric_key].append(metric.value)

    async def get_metrics(
        self, name_pattern: str = None, labels: builtins.dict[str, str] = None
    ) -> builtins.list[MetricData]:
        """Get metrics."""
        async with self._lock:
            filtered_metrics = []

            for metric in self._metrics:
                if name_pattern and name_pattern not in metric.name:
                    continue

                if labels:
                    if not all(metric.labels.get(k) == v for k, v in labels.items()):
                        continue

                filtered_metrics.append(metric)

            return filtered_metrics

    async def export_metrics(self, format: str = "prometheus") -> str:
        """Export metrics in Prometheus format."""
        if format != "prometheus":
            raise ValueError(f"Unsupported format: {format}")

        async with self._lock:
            lines = []

            # Export counters
            for metric_key, value in self._counters.items():
                name, labels_json = metric_key.split(":", 1)
                labels_dict = json.loads(labels_json)
                labels_str = ",".join(f'{k}="{v}"' for k, v in labels_dict.items())
                if labels_str:
                    lines.append(f"{name}{{{labels_str}}} {value}")
                else:
                    lines.append(f"{name} {value}")

            # Export gauges
            for metric_key, value in self._gauges.items():
                name, labels_json = metric_key.split(":", 1)
                labels_dict = json.loads(labels_json)
                labels_str = ",".join(f'{k}="{v}"' for k, v in labels_dict.items())
                if labels_str:
                    lines.append(f"{name}{{{labels_str}}} {value}")
                else:
                    lines.append(f"{name} {value}")

            return "\n".join(lines)


class TracingManager:
    """Distributed tracing management."""

    def __init__(self):
        self._traces: builtins.dict[str, builtins.list[TraceSpan]] = defaultdict(list)
        self._active_spans: builtins.dict[str, TraceSpan] = {}
        self._lock = asyncio.Lock()

    async def start_span(
        self,
        operation_name: str,
        service_name: str,
        parent_span: TraceSpan = None,
        trace_id: str = None,
    ) -> TraceSpan:
        """Start new trace span."""
        span = TraceSpan(operation_name=operation_name, service_name=service_name)

        if parent_span:
            span.trace_id = parent_span.trace_id
            span.parent_span_id = parent_span.span_id
        elif trace_id:
            span.trace_id = trace_id

        async with self._lock:
            self._active_spans[span.span_id] = span
            self._traces[span.trace_id].append(span)

        return span

    async def finish_span(self, span: TraceSpan) -> None:
        """Finish trace span."""
        span.finish()

        async with self._lock:
            if span.span_id in self._active_spans:
                del self._active_spans[span.span_id]

    async def get_trace(self, trace_id: str) -> builtins.list[TraceSpan]:
        """Get trace by ID."""
        async with self._lock:
            return self._traces.get(trace_id, [])

    async def get_active_spans(self) -> builtins.list[TraceSpan]:
        """Get active spans."""
        async with self._lock:
            return list(self._active_spans.values())

    async def export_traces(
        self, format: str = "jaeger"
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Export traces."""
        async with self._lock:
            if format == "jaeger":
                return [
                    span.to_dict() for spans in self._traces.values() for span in spans
                ]
            raise ValueError(f"Unsupported format: {format}")


class LoggingManager:
    """Centralized logging management."""

    def __init__(self, max_logs: int = 50000):
        self.max_logs = max_logs
        self._logs: deque = deque(maxlen=max_logs)
        self._lock = asyncio.Lock()

    async def log(
        self,
        level: LogLevel,
        message: str,
        service_name: str,
        trace_id: str = None,
        span_id: str = None,
        **kwargs,
    ) -> None:
        """Add log entry."""
        log_entry = LogEntry(
            level=level,
            message=message,
            service_name=service_name,
            trace_id=trace_id,
            span_id=span_id,
            fields=kwargs,
        )

        async with self._lock:
            self._logs.append(log_entry)

    async def get_logs(
        self,
        service_name: str = None,
        level: LogLevel = None,
        trace_id: str = None,
        limit: int = 1000,
    ) -> builtins.list[LogEntry]:
        """Get log entries."""
        async with self._lock:
            filtered_logs = []
            count = 0

            for log_entry in reversed(self._logs):
                if count >= limit:
                    break

                if service_name and log_entry.service_name != service_name:
                    continue

                if level and log_entry.level != level:
                    continue

                if trace_id and log_entry.trace_id != trace_id:
                    continue

                filtered_logs.append(log_entry)
                count += 1

            return filtered_logs

    async def export_logs(self, format: str = "json") -> str:
        """Export logs."""
        async with self._lock:
            if format == "json":
                return "\n".join(json.dumps(log.to_dict()) for log in self._logs)
            raise ValueError(f"Unsupported format: {format}")


class ServiceMonitor:
    """Service monitoring and health checking."""

    def __init__(self):
        self._service_health: builtins.dict[str, builtins.dict[str, Any]] = {}
        self._health_checks: builtins.dict[str, Callable] = {}
        self._lock = asyncio.Lock()

    def register_health_check(
        self, service_name: str, health_check: Callable[[], bool]
    ) -> None:
        """Register health check for service."""
        self._health_checks[service_name] = health_check

    async def check_service_health(self, service_name: str) -> builtins.dict[str, Any]:
        """Check service health."""
        health_check = self._health_checks.get(service_name)

        if not health_check:
            return {
                "service": service_name,
                "status": "unknown",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "No health check registered",
            }

        try:
            is_healthy = (
                await health_check()
                if asyncio.iscoroutinefunction(health_check)
                else health_check()
            )
            status = "healthy" if is_healthy else "unhealthy"
        except Exception:
            status = "error"
            is_healthy = False

        health_info = {
            "service": service_name,
            "status": status,
            "healthy": is_healthy,
            "timestamp": datetime.utcnow().isoformat(),
            "last_check": datetime.utcnow().isoformat(),
        }

        async with self._lock:
            self._service_health[service_name] = health_info

        return health_info

    async def get_all_service_health(
        self,
    ) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get health status for all services."""
        health_results = {}

        for service_name in self._health_checks.keys():
            health_results[service_name] = await self.check_service_health(service_name)

        return health_results


class DistributedTracing:
    """Distributed tracing context manager."""

    def __init__(self, tracing_manager: TracingManager):
        self.tracing_manager = tracing_manager
        self._current_span: TraceSpan | None = None

    async def __aenter__(self) -> TraceSpan:
        """Enter tracing context."""
        return self._current_span

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit tracing context."""
        if self._current_span:
            if exc_type:
                self._current_span.set_error(exc_val)
            await self.tracing_manager.finish_span(self._current_span)

    def start_span(
        self, operation_name: str, service_name: str
    ) -> "DistributedTracing":
        """Start new span context."""
        new_context = DistributedTracing(self.tracing_manager)

        async def _create_span():
            new_context._current_span = await self.tracing_manager.start_span(
                operation_name, service_name, self._current_span
            )

        asyncio.create_task(_create_span())
        return new_context


class Telemetry:
    """Comprehensive telemetry data management."""

    def __init__(self):
        self.metrics_collector = InMemoryMetricsCollector()
        self.tracing_manager = TracingManager()
        self.logging_manager = LoggingManager()
        self.service_monitor = ServiceMonitor()
        self._exporters: builtins.dict[TelemetryProtocol, Callable] = {}

    def add_exporter(self, protocol: TelemetryProtocol, exporter: Callable) -> None:
        """Add telemetry exporter."""
        self._exporters[protocol] = exporter

    async def export_telemetry(self, protocol: TelemetryProtocol) -> Any:
        """Export telemetry data."""
        exporter = self._exporters.get(protocol)
        if not exporter:
            raise ValueError(f"No exporter registered for {protocol.value}")

        return await exporter()

    async def get_telemetry_summary(self) -> builtins.dict[str, Any]:
        """Get telemetry summary."""
        metrics = await self.metrics_collector.get_metrics()
        traces = await self.tracing_manager.export_traces()
        logs = await self.logging_manager.get_logs(limit=100)
        health = await self.service_monitor.get_all_service_health()

        return {
            "metrics_count": len(metrics),
            "traces_count": len(traces),
            "logs_count": len(logs),
            "services_monitored": len(health),
            "healthy_services": sum(
                1 for h in health.values() if h.get("healthy", False)
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }


class MetricsExporter:
    """Metrics exporter for various backends."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    async def export_to_prometheus(self) -> str:
        """Export metrics to Prometheus format."""
        return await self.collector.export_metrics("prometheus")

    async def export_to_json(self) -> str:
        """Export metrics to JSON format."""
        metrics = await self.collector.get_metrics()
        return json.dumps([metric.to_dict() for metric in metrics], indent=2)


class TraceExporter:
    """Trace exporter for various backends."""

    def __init__(self, tracing_manager: TracingManager):
        self.tracing_manager = tracing_manager

    async def export_to_jaeger(self) -> builtins.list[builtins.dict[str, Any]]:
        """Export traces to Jaeger format."""
        return await self.tracing_manager.export_traces("jaeger")

    async def export_to_zipkin(self) -> builtins.list[builtins.dict[str, Any]]:
        """Export traces to Zipkin format."""
        traces = await self.tracing_manager.export_traces("jaeger")
        # Convert to Zipkin format (simplified)
        zipkin_traces = []
        for trace in traces:
            zipkin_trace = {
                "id": trace["span_id"],
                "traceId": trace["trace_id"],
                "name": trace["operation_name"],
                "timestamp": int(
                    datetime.fromisoformat(trace["start_time"]).timestamp() * 1000000
                ),
                "duration": int(trace["duration_ms"] * 1000)
                if trace["duration_ms"]
                else None,
                "localEndpoint": {"serviceName": trace["service_name"]},
                "tags": trace["tags"],
            }
            if trace["parent_span_id"]:
                zipkin_trace["parentId"] = trace["parent_span_id"]
            zipkin_traces.append(zipkin_trace)

        return zipkin_traces


class AlertManager:
    """Alert management and notification."""

    def __init__(self):
        self._alerts: builtins.dict[str, Alert] = {}
        self._alert_handlers: builtins.list[Callable] = []
        self._active_alerts: builtins.dict[str, datetime] = {}

    def register_alert(self, alert: Alert) -> None:
        """Register alert rule."""
        self._alerts[alert.name] = alert

    def add_alert_handler(
        self, handler: Callable[[Alert, builtins.dict[str, Any]], None]
    ) -> None:
        """Add alert handler."""
        self._alert_handlers.append(handler)

    async def check_alerts(
        self, metrics: builtins.list[MetricData]
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Check alert conditions."""
        triggered_alerts = []

        for _alert_name, alert in self._alerts.items():
            # Simplified alert evaluation - in production, use proper expression evaluation
            for metric in metrics:
                if alert.condition in metric.name and metric.value > alert.threshold:
                    alert_data = {
                        "alert": alert.to_dict(),
                        "metric": metric.to_dict(),
                        "triggered_at": datetime.utcnow().isoformat(),
                    }

                    triggered_alerts.append(alert_data)

                    # Notify handlers
                    for handler in self._alert_handlers:
                        try:
                            await handler(
                                alert, alert_data
                            ) if asyncio.iscoroutinefunction(handler) else handler(
                                alert, alert_data
                            )
                        except Exception as e:
                            logger.error(f"Alert handler error: {e}")

        return triggered_alerts


class ObservabilityManager:
    """Comprehensive observability management."""

    def __init__(self):
        self.telemetry = Telemetry()
        self.metrics_exporter = MetricsExporter(self.telemetry.metrics_collector)
        self.trace_exporter = TraceExporter(self.telemetry.tracing_manager)
        self.alert_manager = AlertManager()

    async def initialize(self) -> None:
        """Initialize observability components."""
        logger.info("Observability manager initialized")

    async def collect_service_metrics(
        self, service_name: str, metrics: builtins.dict[str, float]
    ) -> None:
        """Collect metrics for a service."""
        for metric_name, value in metrics.items():
            metric = MetricData(
                name=metric_name,
                value=value,
                metric_type=MetricType.GAUGE,
                labels={"service": service_name},
            )
            await self.telemetry.metrics_collector.collect_metric(metric)

    async def trace_request(
        self,
        service_name: str,
        operation: str,
        request_data: builtins.dict[str, Any] = None,
    ) -> DistributedTracing:
        """Start request tracing."""
        context = DistributedTracing(self.telemetry.tracing_manager)
        context._current_span = await self.telemetry.tracing_manager.start_span(
            operation, service_name
        )

        if request_data:
            for key, value in request_data.items():
                context._current_span.set_tag(key, str(value))

        return context

    async def log_event(
        self, service_name: str, level: LogLevel, message: str, **kwargs
    ) -> None:
        """Log service event."""
        await self.telemetry.logging_manager.log(level, message, service_name, **kwargs)

    async def get_observability_dashboard(self) -> builtins.dict[str, Any]:
        """Get observability dashboard data."""
        summary = await self.telemetry.get_telemetry_summary()
        metrics = await self.telemetry.metrics_collector.get_metrics()
        health = await self.telemetry.service_monitor.get_all_service_health()

        return {
            "summary": summary,
            "recent_metrics": [m.to_dict() for m in metrics[-10:]],
            "service_health": health,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Utility functions


def create_metric(
    name: str,
    value: float,
    metric_type: MetricType,
    labels: builtins.dict[str, str] = None,
) -> MetricData:
    """Create metric data."""
    return MetricData(
        name=name, value=value, metric_type=metric_type, labels=labels or {}
    )


def create_alert(
    name: str, condition: str, threshold: float, severity: str = "warning"
) -> Alert:
    """Create alert rule."""
    return Alert(name=name, condition=condition, threshold=threshold, severity=severity)


async def time_operation(
    operation: Callable,
    metrics_collector: MetricsCollector,
    operation_name: str,
    service_name: str,
) -> Any:
    """Time operation and collect metrics."""
    start_time = time.time()

    try:
        result = (
            await operation() if asyncio.iscoroutinefunction(operation) else operation()
        )

        duration = time.time() - start_time

        # Collect timing metric
        timing_metric = MetricData(
            name=f"{operation_name}_duration_seconds",
            value=duration,
            metric_type=MetricType.HISTOGRAM,
            labels={"service": service_name, "operation": operation_name},
        )
        await metrics_collector.collect_metric(timing_metric)

        # Collect success metric
        success_metric = MetricData(
            name=f"{operation_name}_total",
            value=1,
            metric_type=MetricType.COUNTER,
            labels={
                "service": service_name,
                "operation": operation_name,
                "status": "success",
            },
        )
        await metrics_collector.collect_metric(success_metric)

        return result

    except Exception as e:
        duration = time.time() - start_time

        # Collect error metric
        error_metric = MetricData(
            name=f"{operation_name}_total",
            value=1,
            metric_type=MetricType.COUNTER,
            labels={
                "service": service_name,
                "operation": operation_name,
                "status": "error",
            },
        )
        await metrics_collector.collect_metric(error_metric)

        raise e
