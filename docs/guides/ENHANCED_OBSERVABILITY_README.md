# MMF Enhanced Observability Implementation

This implementation provides improved observability defaults for the Marty Microservices Framework, standardizing OpenTelemetry instrumentation across all service templates with enhanced correlation ID tracking and default Grafana dashboards for plugin developer troubleshooting.

## 🚀 Key Improvements

### 1. Standardized Configuration
- **Environment-aware defaults**: Automatic sampling rate adjustment (dev: 100%, staging: 50%, prod: 10%)
- **Unified configuration interface**: Single configuration class for all observability features
- **Graceful fallbacks**: System works even when observability components are unavailable
- **Zero-config instrumentation**: Automatic setup for FastAPI, gRPC, databases, HTTP clients, and more

### 2. Enhanced Correlation ID System
- **Multi-dimensional tracking**: Correlation, request, user, session, plugin, and operation IDs
- **Automatic propagation**: Seamless correlation across HTTP and gRPC service boundaries
- **Plugin debugging**: Specialized correlation context for plugin interaction troubleshooting
- **Log injection**: Automatic correlation context inclusion in all structured logs
- **MMF-namespaced headers**: `X-MMF-*` headers for better identification

### 3. Default Grafana Dashboards
- **MMF Service Overview**: High-level service health, request rates, error rates, and performance metrics
- **MMF Plugin Debugging**: Plugin operation analysis, error tracking, and interaction mapping
- **MMF Distributed Tracing**: Service dependency visualization and trace analysis
- **Pre-configured**: Ready-to-use dashboards with proper templating and filtering

### 4. Complete Infrastructure Stack
- **OpenTelemetry Collector**: Enhanced configuration with MMF-specific processing
- **Jaeger**: Complete distributed tracing setup with OTLP support
- **Prometheus**: Updated scraping configuration for MMF services
- **Alert Rules**: Production-ready alerts for service health, plugin operations, and infrastructure

### 5. Service Template Updates
- **FastAPI Template**: Enhanced with standardized observability, correlation middleware, and automatic instrumentation
- **gRPC Template**: Integrated correlation interceptors and unified observability configuration
- **Hybrid Template**: Combined FastAPI and gRPC observability features

## 📁 Files Added/Modified

### Core Observability Framework
- `src/marty_msf/observability/defaults.py` - Standardized configuration and defaults
- `src/marty_msf/observability/correlation.py` - Enhanced with plugin debugging utilities
- `src/marty_msf/observability/unified.py` - Updated to support new configuration options

### Service Templates
- `services/fastapi/simple-fastapi-service/main.py.j2` - Enhanced with standardized observability
- `services/grpc/grpc_service/main.py.j2` - Updated with unified configuration
- `services/hybrid/hybrid_service/main.py.j2` - Integrated enhanced observability

### Kubernetes Infrastructure
- `ops/k8s/observability/jaeger.yaml` - Complete Jaeger deployment with OTLP support
- `ops/k8s/observability/otel-collector.yaml` - Enhanced OpenTelemetry Collector configuration
- `ops/k8s/observability/grafana.yaml` - Updated with MMF dashboard integration
- `ops/k8s/observability/prometheus.yaml` - Enhanced with MMF service discovery
- `ops/k8s/observability/mmf-alerts.yaml` - Production-ready alert rules

### Default Dashboards
- `ops/observability/grafana/dashboards/mmf-service-overview.json` - Service monitoring dashboard
- `ops/observability/grafana/dashboards/mmf-plugin-debugging.json` - Plugin troubleshooting dashboard
- `ops/observability/grafana/dashboards/mmf-distributed-tracing.json` - Tracing analysis dashboard

### Documentation
- `docs/architecture/observability-strategy.md` - Implementation strategy and decisions
- `docs/guides/enhanced-observability-deployment.md` - Complete deployment and usage guide
- `docs/architecture/architecture.md` - Updated with enhanced observability architecture

## 🎯 Plugin Developer Benefits

### Simplified Debugging
```python
# Automatic plugin operation tracking
with plugin_operation_context(
    plugin_id="data-processor",
    operation_name="transform",
    plugin_version="1.2.0"
):
    return process_data()

# Inter-plugin interaction tracing
trace_plugin_interaction(
    from_plugin="validator",
    to_plugin="transformer",
    interaction_type="data_validation"
)
```

### Zero-Config Observability
- Services generated with enhanced templates automatically include full observability
- No manual instrumentation required
- Correlation IDs automatically propagated across service calls
- Structured logging with correlation context injection

### Production-Ready Monitoring
- Pre-built dashboards specifically designed for plugin debugging
- Real-time plugin performance and error tracking
- Service dependency mapping with plugin interaction visibility
- Intelligent alerting for plugin failures and performance issues

## 🚀 Quick Start

### 1. Deploy Infrastructure
```bash
kubectl apply -f ops/k8s/observability/
```

### 2. Generate Service
```bash
marty generate service --type fastapi --name my-service
```

### 3. Access Dashboards
- Grafana: `http://observability.local/grafana`
- Jaeger: `http://observability.local/jaeger`
- Prometheus: `http://observability.local/prometheus`

## 🔧 Configuration

### Environment Variables
```bash
OTEL_SERVICE_NAME=my-service
OTEL_SERVICE_VERSION=1.0.0
DEPLOYMENT_ENVIRONMENT=production
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_TRACES_SAMPLER_ARG=0.1  # 10% sampling
```

### Service Annotations
```yaml
annotations:
  mmf.prometheus.scrape: "true"
  mmf.prometheus.port: "8000"
  mmf.prometheus.path: "/metrics"
labels:
  mmf.service.name: "my-service"
  mmf.service.type: "fastapi"
```

## 📊 Key Metrics

### Service Metrics
- `mmf_requests_total` - Total requests with method, endpoint, status labels
- `mmf_request_duration_seconds` - Request duration histogram
- `mmf_active_connections` - Active connection gauge

### Plugin Metrics
- `mmf_plugin_operations_total` - Plugin operations with plugin_id, operation, status labels
- `mmf_plugin_operation_duration_seconds` - Plugin operation duration histogram

### Infrastructure Metrics
- `mmf_database_operations_total` - Database operations
- `mmf_cache_operations_total` - Cache operations with hit/miss tracking

## 🚨 Default Alerts

- **Service Down**: Critical alert when services are unavailable
- **High Error Rate**: Warning when error rate exceeds 10%
- **High Latency**: Warning when 95th percentile exceeds 1 second
- **Plugin Errors**: Warning when plugin error rate exceeds 5%
- **Resource Usage**: Warnings for high CPU/memory usage
- **Infrastructure Health**: Alerts for database and cache issues

## 🎯 Next Steps

1. **Validate Setup**: Deploy infrastructure and verify all components are healthy
2. **Generate Test Service**: Create a service using enhanced templates
3. **Explore Dashboards**: Familiarize yourself with the default dashboards
4. **Customize Alerts**: Adjust alert thresholds based on your service characteristics
5. **Add Custom Metrics**: Implement business-specific metrics using the standardized approach

This enhanced observability system provides a solid foundation for monitoring, debugging, and optimizing microservices in the MMF ecosystem, with specialized support for plugin developers to troubleshoot complex service interactions.
