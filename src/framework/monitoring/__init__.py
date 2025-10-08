"""
Enhanced Monitoring and Observability Framework

This module provides comprehensive monitoring capabilities including:
- Custom metrics collection with Prometheus integration
- Distributed tracing with OpenTelemetry
- Advanced health checks
- Business metrics and SLA monitoring
- Alert management and notifications
- Automatic middleware integration

Key Features:
- Prometheus metrics collection
- Distributed tracing (Jaeger)
- Health check framework
- Custom business metrics
- SLA monitoring and alerting
- FastAPI/gRPC middleware integration

Usage:
    from framework.monitoring import (
        initialize_monitoring,
        setup_fastapi_monitoring,
        MonitoringManager,
        BusinessMetric,
        AlertRule
    )

    # Initialize monitoring
    manager = initialize_monitoring("my-service", use_prometheus=True)

    # Add health checks
    manager.add_health_check(DatabaseHealthCheck("database", db_session))

    # Setup middleware
    setup_fastapi_monitoring(app)
"""

from .core import (
    DatabaseHealthCheck,
    DistributedTracer,
    ExternalServiceHealthCheck,
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    InMemoryCollector,
    MetricDefinition,
    MetricsCollector,
    MetricType,
    MonitoringManager,
    PrometheusCollector,
    RedisHealthCheck,
    ServiceMetrics,
    SimpleHealthCheck,
    get_monitoring_manager,
    initialize_monitoring,
    set_monitoring_manager,
)
from .custom_metrics import (
    Alert,
    AlertLevel,
    AlertManager,
    AlertRule,
    BusinessMetric,
    BusinessMetricsCollector,
    CustomMetricsManager,
    MetricAggregation,
    MetricBuffer,
    get_custom_metrics_manager,
    initialize_custom_metrics,
    record_error_rate,
    record_response_time_sla,
    record_revenue,
    record_transaction_result,
    record_user_registration,
)
from .middleware import (
    MonitoringMiddlewareConfig,
    monitor_async_function,
    monitor_function,
    setup_fastapi_monitoring,
    setup_grpc_monitoring,
)

__all__ = [
    # Core monitoring
    "MonitoringManager",
    "MetricsCollector",
    "PrometheusCollector",
    "InMemoryCollector",
    "MetricDefinition",
    "MetricType",
    "ServiceMetrics",
    "initialize_monitoring",
    "get_monitoring_manager",
    "set_monitoring_manager",
    # Health checks
    "HealthCheck",
    "HealthCheckResult",
    "HealthStatus",
    "SimpleHealthCheck",
    "DatabaseHealthCheck",
    "RedisHealthCheck",
    "ExternalServiceHealthCheck",
    # Distributed tracing
    "DistributedTracer",
    # Middleware
    "MonitoringMiddlewareConfig",
    "setup_fastapi_monitoring",
    "setup_grpc_monitoring",
    "monitor_function",
    "monitor_async_function",
    # Custom metrics and alerting
    "CustomMetricsManager",
    "BusinessMetricsCollector",
    "BusinessMetric",
    "AlertManager",
    "AlertRule",
    "Alert",
    "AlertLevel",
    "MetricAggregation",
    "MetricBuffer",
    "initialize_custom_metrics",
    "get_custom_metrics_manager",
    # Business metric helpers
    "record_user_registration",
    "record_transaction_result",
    "record_response_time_sla",
    "record_error_rate",
    "record_revenue",
]

__version__ = "1.0.0"
