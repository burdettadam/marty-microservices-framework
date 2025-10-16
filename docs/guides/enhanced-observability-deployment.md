# MMF Enhanced Observability Deployment Guide

## Overview

This guide provides complete instructions for deploying and using the enhanced observability features in the Marty Microservices Framework (MMF). The enhanced system provides standardized OpenTelemetry instrumentation, correlation tracking, and debugging tools for plugin developers.

## Architecture

The enhanced observability system consists of:

- **OpenTelemetry Collector**: Central telemetry data collection and processing
- **Jaeger**: Distributed tracing storage and visualization
- **Prometheus**: Metrics collection and storage
- **Grafana**: Unified dashboards and visualization
- **Enhanced Correlation System**: Multi-dimensional request tracking
- **Default Dashboards**: Pre-built monitoring and debugging interfaces

## Quick Start

### 1. Deploy Observability Infrastructure

```bash
# Deploy the observability namespace and components
kubectl apply -f ops/k8s/observability/

# Verify deployments
kubectl get pods -n observability
```

### 2. Generate Service with Enhanced Observability

```bash
# Generate a new FastAPI service
marty generate service --type fastapi --name user-service

# Generate a gRPC service
marty generate service --type grpc --name payment-service

# Generate a hybrid service
marty generate service --type hybrid --name order-service
```

### 3. Deploy Your Services

Services generated with the enhanced templates automatically include:
- Standardized OpenTelemetry configuration
- Correlation ID middleware
- Prometheus metrics endpoints
- Health checks with observability status

```bash
# Deploy your service
kubectl apply -f your-service/k8s/

# Verify observability is working
kubectl logs -f deployment/your-service -n your-namespace
```

## Configuration

### Environment Variables

All MMF services support these standardized environment variables:

```bash
# Service identification
OTEL_SERVICE_NAME=user-service
OTEL_SERVICE_VERSION=1.0.0
DEPLOYMENT_ENVIRONMENT=production

# OpenTelemetry endpoints
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_JAEGER_ENDPOINT=http://jaeger:14268/api/traces

# Sampling configuration (environment-specific)
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1  # 10% sampling for production

# Prometheus configuration
OTEL_EXPORTER_PROMETHEUS_PORT=8000

# Logging configuration
LOG_LEVEL=INFO
```

### Service Annotations

Add these annotations to your Kubernetes deployments for automatic discovery:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
spec:
  template:
    metadata:
      annotations:
        # Enable MMF-specific Prometheus scraping
        mmf.prometheus.scrape: "true"
        mmf.prometheus.port: "8000"
        mmf.prometheus.path: "/metrics"
      labels:
        # MMF service identification
        mmf.service.name: "user-service"
        mmf.service.type: "fastapi"
        mmf.service.version: "1.0.0"
```

## Using the Enhanced Features

### 1. Correlation Tracking

The enhanced correlation system automatically tracks requests across services:

```python
from marty_msf.observability.correlation import (
    with_correlation,
    plugin_operation_context,
    trace_plugin_interaction
)

# Automatic correlation in business logic
@app.post("/process")
async def process_data(data: ProcessRequest):
    with with_correlation(operation_name="process_data"):
        # All operations within this context are automatically correlated
        result = await business_logic.process(data)
        return result

# Plugin operation debugging
def my_plugin_operation():
    with plugin_operation_context(
        plugin_id="data-processor",
        operation_name="transform",
        plugin_version="1.2.0"
    ):
        # Plugin operations are automatically tracked
        return transform_data()

# Inter-plugin interaction tracing
trace_plugin_interaction(
    from_plugin="data-processor",
    to_plugin="validator",
    interaction_type="validation_request"
)
```

### 2. Custom Metrics

Add business-specific metrics using the standardized approach:

```python
from marty_msf.observability.defaults import create_default_observability_config
from marty_msf.observability.unified import UnifiedObservability

# Initialize with defaults
config = create_default_observability_config(
    service_name="user-service",
    service_type="fastapi"
)
observability = UnifiedObservability(config)

# Custom business metrics are automatically namespaced
business_metric = observability.meter.create_counter(
    name="user_registrations_total",
    description="Total user registrations",
    unit="1"
)

business_metric.add(1, {"registration_type": "email"})
```

### 3. Enhanced Logging

Structured logging with automatic correlation injection:

```python
import logging

logger = logging.getLogger(__name__)

# Logs automatically include correlation context
logger.info("Processing user registration", extra={
    "user_id": user.id,
    "registration_type": "email"
})

# Correlation fields are automatically added:
# - correlation_id
# - request_id
# - user_id
# - session_id
# - plugin_id (when applicable)
# - operation_id (when applicable)
```

## Monitoring and Dashboards

### Accessing Dashboards

1. **Grafana UI**: `http://observability.local/grafana`
   - Username: `admin`
   - Password: `admin`

2. **Jaeger UI**: `http://observability.local/jaeger`

3. **Prometheus UI**: `http://observability.local/prometheus`

### Default Dashboards

#### MMF Service Overview
- Service health status
- Request rates and error rates
- Response time percentiles
- Active connections
- Database and cache operations

#### MMF Plugin Debugging
- Plugin operation rates
- Plugin error rates
- Inter-plugin interaction mapping
- Correlation ID flow tracking
- Plugin performance distribution

#### MMF Distributed Tracing
- Service dependency mapping
- Trace duration analysis
- Error trace identification
- Correlation success rates

### Key Metrics to Monitor

```promql
# Service health
up{job="mmf-services"}

# Request rate
rate(mmf_requests_total[5m])

# Error rate
rate(mmf_requests_total{status_code=~"5.."}[5m]) / rate(mmf_requests_total[5m])

# Response time
histogram_quantile(0.95, rate(mmf_request_duration_seconds_bucket[5m]))

# Plugin operations
rate(mmf_plugin_operations_total[5m])

# Plugin errors
rate(mmf_plugin_operations_total{status="error"}[5m])

# Database operations
rate(mmf_database_operations_total[5m])

# Cache hit rate
rate(mmf_cache_operations_total{operation="hit"}[5m]) /
rate(mmf_cache_operations_total{operation=~"hit|miss"}[5m])
```

## Alerting

### Default Alert Rules

The system includes pre-configured alerts for:

**Service Health:**
- Service down alerts
- High error rate warnings
- High latency warnings
- Resource usage alerts

**Plugin Operations:**
- Plugin error rate warnings
- Plugin performance degradation
- Plugin failure spikes

**Infrastructure:**
- Database connection failures
- Cache performance degradation
- Correlation tracking failures

### Custom Alerts

Add custom alerts by creating additional PrometheusRule resources:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: my-service-alerts
  namespace: observability
spec:
  groups:
  - name: my-service
    rules:
    - alert: MyServiceCustomAlert
      expr: my_custom_metric > threshold
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Custom alert for my service"
```

## Troubleshooting

### Common Issues

1. **Missing Correlation IDs**
   - Check that CorrelationMiddleware is added to FastAPI apps
   - Verify CorrelationInterceptor is configured for gRPC services
   - Ensure HTTP clients use CorrelationHTTPClient for propagation

2. **Metrics Not Appearing**
   - Verify Prometheus annotations are correct
   - Check service is exposing metrics on configured port
   - Confirm namespace has proper labels

3. **Traces Not Visible**
   - Verify OTLP endpoint configuration
   - Check sampling rates aren't too low
   - Confirm Jaeger is receiving traces

### Debug Commands

```bash
# Check observability component status
kubectl get pods -n observability

# View service logs
kubectl logs -f deployment/your-service -n your-namespace

# Check Prometheus targets
kubectl port-forward svc/prometheus 9090:9090 -n observability
# Visit http://localhost:9090/targets

# Check OpenTelemetry Collector status
kubectl logs -f deployment/otel-collector -n observability

# View correlation flow
kubectl logs -f deployment/your-service -n your-namespace | grep correlation_id
```

## Performance Considerations

### Sampling Strategies

Environment-specific sampling rates are automatically configured:

- **Development**: 100% sampling
- **Testing**: 100% sampling
- **Staging**: 50% sampling
- **Production**: 10% sampling

### Resource Requirements

Recommended resource allocation:

```yaml
# OpenTelemetry Collector
resources:
  requests:
    cpu: 200m
    memory: 400Mi
  limits:
    cpu: 1000m
    memory: 2Gi

# Jaeger
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 1000m
    memory: 2Gi

# Prometheus
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi
```

## Migration Guide

### From Legacy Observability

If you have existing services with legacy observability:

1. **Update Service Templates**: Regenerate services using new templates
2. **Update Dependencies**: Ensure latest MMF observability modules
3. **Environment Variables**: Update to use new standardized variable names
4. **Middleware**: Replace custom correlation middleware with MMF defaults
5. **Dashboards**: Import new MMF dashboards to Grafana

### Gradual Migration

1. Deploy enhanced observability infrastructure alongside existing
2. Update services one by one to use new templates
3. Verify metrics and traces appear in new dashboards
4. Remove legacy observability components once migration complete

## Best Practices

1. **Use Correlation Contexts**: Always use `with_correlation()` for business operations
2. **Plugin Debugging**: Use `plugin_operation_context()` for all plugin operations
3. **Structured Logging**: Include relevant business context in log extras
4. **Custom Metrics**: Follow MMF naming conventions for metrics
5. **Alert Fatigue**: Tune alert thresholds based on your service characteristics
6. **Dashboard Customization**: Create service-specific dashboards using MMF templates as base

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review logs from observability components
3. Consult the MMF documentation
4. Open an issue in the MMF repository
