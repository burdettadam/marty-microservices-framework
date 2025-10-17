# MMF Unified Observability Implementation Guide

This guide provides comprehensive instructions for implementing and using the Marty Microservices Framework's unified observability system for plugin developers and service implementors.

## 🎯 Overview

The MMF unified observability system provides standardized OpenTelemetry instrumentation, enhanced correlation tracking, and pre-built Grafana dashboards to help plugin developers troubleshoot microservice interactions effectively.

## 🚀 Quick Start

### For New Services

All MMF service templates automatically include unified observability. Simply generate a service and observability is enabled by default:

```bash
# Generate a new FastAPI service with observability
marty generate service --type fastapi --name my-service

# Generate a new gRPC service with observability
marty generate service --type grpc --name my-grpc-service

# Generate a hybrid service with observability
marty generate service --type hybrid --name my-hybrid-service
```

### For Existing Services

Add unified observability to existing services:

```python
from marty_msf.observability.unified import UnifiedObservability
from marty_msf.observability.correlation import CorrelationMiddleware

# Initialize observability
observability = UnifiedObservability(
    service_name="my-service",
    service_version="1.0.0"
)

# In FastAPI applications
app.add_middleware(CorrelationMiddleware)

# Initialize during startup
@app.on_event("startup")
async def startup():
    await observability.initialize()

@app.on_event("shutdown")
async def shutdown():
    await observability.shutdown()
```

## 📊 Core Components

### 1. Unified Observability Orchestrator

The `UnifiedObservability` class provides centralized configuration and management:

```python
from marty_msf.observability.unified import UnifiedObservability, ObservabilityConfig

# Environment-based configuration
config = ObservabilityConfig(
    service_name="payment-service",
    service_version="2.1.0",
    environment="production",

    # OpenTelemetry configuration
    otlp_endpoint="http://jaeger:14268/api/traces",
    enable_tracing=True,

    # Prometheus configuration
    prometheus_port=9090,
    enable_metrics=True,

    # Sampling configuration
    trace_sample_rate=0.1,  # 10% sampling in production
)

observability = UnifiedObservability(config=config)
```

### 2. Enhanced Correlation System

Multi-dimensional correlation tracking for comprehensive request analysis:

```python
from marty_msf.observability.correlation import (
    with_correlation,
    get_correlation_id,
    set_user_id,
    CorrelationContext
)

# Manual correlation context
with with_correlation(
    operation_name="process_payment",
    correlation_id="req_12345",
    user_id="user_67890",
    session_id="sess_abcdef"
):
    # All operations within this context include correlation data
    result = await payment_processor.charge(amount, card_token)

    # Logs automatically include correlation context
    logger.info("Payment processed successfully", extra={
        "amount": amount,
        "result_id": result.id
    })

# Access correlation data anywhere
correlation_id = get_correlation_id()
user_id = get_user_id()
```

### 3. Automatic Instrumentation

Zero-configuration instrumentation for common libraries:

```python
# HTTP client requests automatically traced
import httpx
from marty_msf.observability.correlation import CorrelationHTTPClient

# Enhanced HTTP client with correlation propagation
async with CorrelationHTTPClient() as client:
    response = await client.get("https://api.example.com/data")
    # Correlation headers automatically added

# Database queries automatically traced
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://...")
# All database operations automatically instrumented

# Redis operations automatically traced
import redis.asyncio as redis

client = redis.Redis.from_url("redis://localhost:6379")
# All Redis operations automatically instrumented
```

## 🎛️ Service Template Integration

### FastAPI Services

FastAPI services get comprehensive observability integration:

```python
# main.py (generated from template)
from marty_msf.observability.unified import UnifiedObservability
from marty_msf.observability.correlation import CorrelationMiddleware, with_correlation

app = FastAPI(title="My Service")

# Correlation middleware automatically added
app.add_middleware(CorrelationMiddleware)

# Observability initialized in lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    observability = UnifiedObservability(
        service_name="my-service",
        service_version="1.0.0"
    )
    await observability.initialize()
    yield
    await observability.shutdown()

app = FastAPI(lifespan=lifespan)

# Business logic with correlation
@app.post("/process")
async def process_data(data: ProcessRequest):
    with with_correlation(operation_name="process_data"):
        # Automatic correlation tracking
        result = await business_logic.process(data)
        return result
```

### gRPC Services

gRPC services include correlation interceptors:

```python
# main.py (generated from template)
from marty_msf.observability.unified import UnifiedObservability
from marty_msf.observability.correlation import CorrelationInterceptor

async def create_service_factory():
    # Initialize observability
    observability = UnifiedObservability(
        service_name="my-grpc-service",
        service_version="1.0.0"
    )
    await observability.initialize()

    # Add correlation interceptor
    interceptors = [CorrelationInterceptor()]

    # Create gRPC server with observability
    grpc_server = create_grpc_server(
        port=50051,
        interceptors=interceptors,
        enable_health_service=True
    )

    return grpc_server, {"observability": observability}
```

### Hybrid Services

Hybrid services provide observability for both HTTP and gRPC:

```python
# Both FastAPI middleware and gRPC interceptors configured
app.add_middleware(CorrelationMiddleware)  # For HTTP
interceptors = [CorrelationInterceptor()]  # For gRPC

# Shared observability instance
observability = UnifiedObservability(
    service_name="hybrid-service",
    service_version="1.0.0"
)
```

## 📈 Grafana Dashboard Usage

The MMF provides three pre-built Grafana dashboards optimized for plugin debugging:

### 1. Service Overview Dashboard (`mmf-service-overview.json`)

**Purpose**: High-level service health and performance monitoring

**Key Panels**:
- Service uptime and availability
- Request rate, error rate, and latency percentiles
- Resource utilization (CPU, memory, disk)
- Database connection pool status
- Cache hit/miss ratios

**Use Cases**:
- Monitor overall service health
- Identify performance degradation
- Validate deployment success
- Resource capacity planning

### 2. Tracing Analysis Dashboard (`mmf-tracing-analysis.json`)

**Purpose**: Deep-dive distributed tracing analysis for debugging complex interactions

**Key Panels**:
- Trace duration distribution and percentiles
- Service dependency map with latency
- Error rate by operation and service
- Span count and depth analysis
- Cross-service communication patterns

**Use Cases**:
- Debug slow requests across services
- Identify bottlenecks in service chains
- Analyze plugin interaction patterns
- Optimize distributed transaction performance

### 3. Plugin Troubleshooting Dashboard (`mmf-plugin-troubleshooting.json`)

**Purpose**: Specialized dashboard for plugin developers debugging microservice interactions

**Key Panels**:
- Plugin-specific error rates and patterns
- Cross-plugin communication analysis
- Correlation ID flow visualization
- Plugin lifecycle event tracking
- Resource usage by plugin

**Use Cases**:
- Debug plugin integration issues
- Monitor plugin performance impact
- Trace plugin-to-plugin communication
- Validate plugin deployment and configuration

### Dashboard Import

```bash
# Import dashboards to Grafana
curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @ops/observability/grafana-dashboards/mmf-service-overview.json

curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @ops/observability/grafana-dashboards/mmf-tracing-analysis.json

curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H 'Content-Type: application/json' \
  -d @ops/observability/grafana-dashboards/mmf-plugin-troubleshooting.json
```

## 🔧 Advanced Configuration

### Environment-Specific Configuration

```python
import os
from marty_msf.observability.unified import ObservabilityConfig

# Development configuration
if os.getenv("ENVIRONMENT") == "development":
    config = ObservabilityConfig(
        enable_tracing=True,
        trace_sample_rate=1.0,  # 100% sampling for development
        enable_debug_logging=True,
        otlp_endpoint="http://localhost:14268/api/traces"
    )

# Production configuration
elif os.getenv("ENVIRONMENT") == "production":
    config = ObservabilityConfig(
        enable_tracing=True,
        trace_sample_rate=0.05,  # 5% sampling for production
        enable_debug_logging=False,
        otlp_endpoint="https://jaeger.production.example.com/api/traces"
    )
```

### Custom Metrics

```python
from marty_msf.observability.unified import UnifiedObservability

observability = UnifiedObservability(service_name="my-service")

# Create custom metrics
payment_counter = observability.create_counter(
    name="payments_processed_total",
    description="Total number of payments processed"
)

payment_duration = observability.create_histogram(
    name="payment_processing_duration_seconds",
    description="Payment processing duration"
)

# Use custom metrics
with observability.timer(payment_duration):
    result = await process_payment(payment_data)
    payment_counter.inc(labels={"status": "success", "method": "card"})
```

### Custom Spans

```python
from marty_msf.observability.unified import UnifiedObservability

observability = UnifiedObservability(service_name="my-service")

# Create custom spans for detailed tracing
with observability.start_span("validate_payment_data") as span:
    span.set_attribute("payment.amount", payment.amount)
    span.set_attribute("payment.currency", payment.currency)

    validation_result = await validate_payment(payment)

    span.set_attribute("validation.result", validation_result.is_valid)
    if not validation_result.is_valid:
        span.set_status(Status(StatusCode.ERROR, validation_result.error))
```

## 🐛 Debugging Workflows

### 1. Cross-Service Request Tracing

When debugging issues that span multiple services:

1. **Find the correlation ID** from logs or error messages
2. **Search in Grafana** using the Tracing Analysis dashboard
3. **Filter by correlation ID** to see the complete request flow
4. **Analyze span timings** to identify bottlenecks
5. **Check error spans** for failure points

```bash
# Search logs by correlation ID
kubectl logs -l app=my-service | grep "correlation_id:req_12345"

# Query Jaeger directly
curl "http://jaeger:16686/api/traces?service=my-service&tag=correlation_id:req_12345"
```

### 2. Plugin Performance Analysis

For plugin-specific performance issues:

1. **Use Plugin Troubleshooting Dashboard** in Grafana
2. **Filter by plugin name** or operation
3. **Compare before/after deployment** metrics
4. **Analyze resource usage** patterns
5. **Check plugin-to-plugin** communication latency

### 3. Error Root Cause Analysis

For error investigation:

1. **Identify error patterns** in Service Overview dashboard
2. **Drill down** to specific traces in Tracing Analysis dashboard
3. **Examine error spans** for stack traces and context
4. **Follow correlation flow** to identify error propagation
5. **Check correlation context** for user/session patterns

## 🔍 Best Practices

### 1. Correlation Context Usage

```python
# ✅ Good: Use correlation context for business operations
with with_correlation(
    operation_name="user_checkout",
    user_id=user.id,
    session_id=session.id,
    business_context={"cart_id": cart.id, "total": cart.total}
):
    result = await checkout_service.process(cart)

# ❌ Avoid: Don't create correlation contexts for every function call
def helper_function():
    with with_correlation(operation_name="helper"):  # Unnecessary
        return some_calculation()
```

### 2. Custom Metrics Naming

```python
# ✅ Good: Descriptive, consistent naming
user_login_attempts = observability.create_counter(
    name="user_login_attempts_total",
    description="Total user login attempts",
    labels=["status", "method", "source"]
)

# ❌ Avoid: Vague or inconsistent naming
counter = observability.create_counter(name="logins")  # Too vague
```

### 3. Error Handling

```python
# ✅ Good: Preserve correlation context in error handling
try:
    with with_correlation(operation_name="payment_processing"):
        result = await process_payment(payment_data)
except PaymentError as e:
    # Correlation context preserved in error logs
    logger.error(f"Payment processing failed: {e}")
    raise

# ✅ Good: Add correlation context to exceptions
except Exception as e:
    correlation_id = get_correlation_id()
    raise ProcessingError(f"Failed processing {correlation_id}") from e
```

### 4. Sampling Strategy

```python
# ✅ Good: Environment-appropriate sampling
sampling_rates = {
    "development": 1.0,    # 100% for development
    "staging": 0.3,        # 30% for staging
    "production": 0.05,    # 5% for production
}

config = ObservabilityConfig(
    trace_sample_rate=sampling_rates.get(environment, 0.1)
)
```

## 🛠️ Infrastructure Setup

### Local Development

```yaml
# docker-compose.yml
version: '3.8'
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
      - "14268:14268"
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - ./grafana/dashboards:/var/lib/grafana/dashboards
```

### Kubernetes Deployment

```yaml
# ops/observability/jaeger.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jaeger
  template:
    metadata:
      labels:
        app: jaeger
    spec:
      containers:
      - name: jaeger
        image: jaegertracing/all-in-one:latest
        ports:
        - containerPort: 16686
        - containerPort: 14268
        env:
        - name: COLLECTOR_OTLP_ENABLED
          value: "true"
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger
spec:
  selector:
    app: jaeger
  ports:
  - name: ui
    port: 16686
    targetPort: 16686
  - name: collector
    port: 14268
    targetPort: 14268
```

## 🤝 Contributing

To contribute to the observability system:

1. **Add new instrumentation** for additional libraries
2. **Enhance correlation tracking** with new context dimensions
3. **Create specialized dashboards** for specific use cases
4. **Improve documentation** with real-world examples
5. **Submit performance optimizations** for high-throughput scenarios

## 📚 Additional Resources

- [OpenTelemetry Python Documentation](https://opentelemetry-python.readthedocs.io/)
- [Prometheus Python Client](https://prometheus.github.io/client_python/)
- [Grafana Dashboard Documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [Jaeger Deployment Guide](https://www.jaegertracing.io/docs/deployment/)
- [MMF Architecture Documentation](../architecture/architecture.md)

For questions or support, please refer to the MMF documentation or open an issue in the repository.
