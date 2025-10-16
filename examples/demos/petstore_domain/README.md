# Enhanced Petstore Domain - MMF Capabilities Demo

This enhanced petstore domain service demonstrates the full power of the Marty Microservices Framework (MMF) by implementing enterprise-grade microservice patterns including event-driven workflows, comprehensive observability, resilience patterns, security guardrails, and real data integration.

## 🚀 Key Enhancements

### 1. **Event-Driven Saga Orchestration**
- **Cross-Service Workflows**: Order → Payment → Delivery hand-offs using Kafka event streaming
- **Saga Pattern**: Comprehensive workflow orchestration with compensation actions
- **Correlation Tracking**: End-to-end request tracing across service boundaries
- **Event Sourcing**: Complete audit trail of business events

```python
# Example: Order creation triggers saga workflow
POST /petstore-domain/orders
{
  "customer_id": "customer-001",
  "pet_id": "golden-retriever-001",
  "special_instructions": "Please include vaccination records"
}
```

### 2. **Comprehensive Observability**
- **Structured Logging**: Correlation IDs throughout the request lifecycle
- **Prometheus Metrics**: Counters, histograms, and custom business metrics
- **Distributed Tracing**: Jaeger integration for request flow visualization
- **Grafana Dashboards**: Pre-configured monitoring dashboards

```python
# Observability features automatically included
@trace_operation("create_order")
@track_metrics("order_creation_requests")
@rate_limit(requests_per_minute=30)
async def create_order(request):
    # Your business logic here
```

### 3. **Resilience Patterns**
- **Circuit Breakers**: Automatic failure detection and recovery
- **Retry Logic**: Configurable retry policies with exponential backoff
- **Timeout Handling**: Request-level timeout management
- **Rich Error Metadata**: Detailed error responses with correlation IDs

### 4. **Security Guardrails**
- **JWT/OIDC Authentication**: Token-based security with role validation
- **Rate Limiting**: Configurable limits per endpoint and user
- **Zero-Trust Defaults**: Security-first approach to all endpoints
- **Audit Trails**: Complete security event logging

### 5. **Centralized Configuration & Feature Flags**
- **Live Reload**: Configuration changes without service restart
- **Feature Flags**: Runtime behavior modification
- **Environment-Specific Settings**: Dev, staging, production configs
- **A/B Testing Support**: Feature flag-driven experimentation

### 6. **Real Data Integration**
- **Redis Caching**: High-performance data caching layer
- **PostgreSQL Integration**: Full ACID transaction support
- **Multi-Datasource Support**: Template for various data backends
- **Connection Pooling**: Optimized database connections

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Order Service │───→│ Payment Service │───→│Delivery Service │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Kafka Event Stream                          │
│     OrderCreated → PaymentProcessed → DeliveryScheduled       │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Saga Orchestrator                            │
│  ├─ Step 1: Create Order       (Compensation: Cancel Order)   │
│  ├─ Step 2: Process Payment    (Compensation: Refund)         │
│  └─ Step 3: Schedule Delivery  (Compensation: Cancel)         │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 Setup and Running

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Make (optional, for convenience commands)

### Quick Start

1. **Start the complete infrastructure:**
```bash
docker-compose -f docker-compose.enhanced.yml up -d
```

2. **Verify services are running:**
```bash
# Check service health
curl http://localhost:8080/petstore-domain/health

# Browse pets with enhanced features
curl http://localhost:8080/petstore-domain/pets/browse?category=dog
```

3. **Access monitoring dashboards:**
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686
- **Kafka UI**: http://localhost:8081

### Infrastructure Components

| Service | Port | Purpose |
|---------|------|---------|
| Petstore API | 8080 | Main application |
| Grafana | 3000 | Monitoring dashboards |
| Prometheus | 9090 | Metrics collection |
| Jaeger | 16686 | Distributed tracing |
| Kafka UI | 8081 | Event stream monitoring |
| Redis | 6379 | Caching layer |
| PostgreSQL | 5432 | Primary database |

## 📊 Demo Scenarios

### 1. Cross-Service Workflow Demo

**Create an order and watch the saga unfold:**

```bash
# Start the order saga
curl -X POST http://localhost:8080/petstore-domain/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "customer-001",
    "pet_id": "golden-retriever-001",
    "special_instructions": "Include training guide"
  }'

# Track the saga progress
curl http://localhost:8080/petstore-domain/orders/{order_id}/status
```

**What to observe:**
- Correlation ID propagation across services
- Event publishing to Kafka topics
- Saga step execution and compensation
- Distributed trace in Jaeger

### 2. Observability Deep Dive

**Generate load and observe metrics:**

```bash
# Generate some traffic
for i in {1..50}; do
  curl http://localhost:8080/petstore-domain/pets/browse?category=dog
  sleep 0.1
done
```

**Monitor in real-time:**
- **Grafana**: Custom petstore dashboard
- **Prometheus**: Query `petstore_requests_total`
- **Jaeger**: Search traces by service
- **Logs**: Structured JSON with correlation IDs

### 3. Resilience Testing

**Test circuit breaker behavior:**

```bash
# Trigger circuit breaker (simulated failure)
curl -X POST http://localhost:8080/petstore-domain/orders \
  -H "X-Simulate-Failure: payment-service"

# Observe circuit breaker state
curl http://localhost:8080/petstore-domain/admin/config
```

**What happens:**
- Circuit breaker opens after threshold failures
- Requests fail fast during open state
- Automatic recovery testing in half-open state

### 4. Security Patterns Demo

**Test authentication and rate limiting:**

```bash
# Get JWT token (demo mode)
TOKEN=$(curl -X POST http://localhost:8080/auth/login \
  -d '{"username":"demo","password":"demo"}' | jq -r .token)

# Use authenticated endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/petstore-domain/admin/config

# Test rate limiting
for i in {1..150}; do
  curl http://localhost:8080/petstore-domain/pets/browse
done
```

### 5. Feature Flags in Action

**Toggle features at runtime:**

```bash
# Check current feature flags
curl http://localhost:8080/petstore-domain/admin/config

# Toggle personalization feature
curl -X PUT http://localhost:8080/petstore-domain/admin/config \
  -H "Content-Type: application/json" \
  -d '{"feature_flags":{"pet_personalization":true}}'

# See immediate effect
curl http://localhost:8080/petstore-domain/pets/browse
```

## 🔍 Monitoring and Debugging

### Key Metrics to Watch

```prometheus
# Request rate
rate(petstore_requests_total[5m])

# Error rate
rate(petstore_requests_errors_total[5m]) / rate(petstore_requests_total[5m])

# Response time percentiles
histogram_quantile(0.95, petstore_request_duration_seconds_bucket)

# Saga completion rate
rate(petstore_saga_completed_total[5m])

# Circuit breaker state
petstore_circuit_breaker_state
```

### Correlation ID Tracking

Every request gets a correlation ID that flows through:
1. HTTP headers (`X-Correlation-ID`)
2. Log entries (structured JSON)
3. Distributed traces (span tags)
4. Event payloads (metadata)
5. Database records (audit trails)

### Troubleshooting Guide

**Common Issues:**

1. **Services not starting**: Check `docker-compose logs`
2. **Missing traces**: Verify Jaeger configuration
3. **Metrics not appearing**: Check Prometheus targets
4. **Authentication failures**: Verify JWT configuration

## 🧪 Testing

### Unit Tests
```bash
# Run unit tests
python -m pytest tests/unit/

# With coverage
python -m pytest tests/unit/ --cov=app
```

### Integration Tests
```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
python -m pytest tests/integration/
```

### Load Testing
```bash
# Install k6
# Run load test
k6 run tests/load/basic_load_test.js
```

## 📋 API Reference

### Enhanced Endpoints

| Method | Endpoint | Description | Features |
|--------|----------|-------------|----------|
| GET | `/health` | Service health | MMF status, component health |
| GET | `/pets/browse` | Browse pets | Caching, personalization, filters |
| GET | `/pets/{id}` | Pet details | Circuit breaker, retry logic |
| POST | `/orders` | Create order | Saga orchestration, auth required |
| POST | `/payments` | Process payment | Enhanced security, audit trail |
| GET | `/orders/{id}/status` | Order tracking | Workflow status, real-time updates |
| GET | `/admin/config` | Configuration | Feature flags, live reload |

### Legacy Compatibility

All original endpoints remain available:
- `/browse-pets` → Enhanced version at `/pets/browse`
- `/create-order` → Enhanced version at `/orders`
- `/process-payment` → Enhanced version at `/payments`

## 🔧 Configuration

### Feature Flags

```yaml
feature_flags:
  pet_personalization: false      # AI-powered recommendations
  premium_filters: true           # Advanced search filters
  express_order_processing: true  # Saga-based workflows
  payment_processing: true        # Payment service integration
  real_time_order_updates: false  # WebSocket updates
```

### Observability Settings

```yaml
observability:
  tracing_enabled: true
  metrics_enabled: true
  jaeger_endpoint: "http://jaeger:14268/api/traces"
  prometheus_endpoint: "http://prometheus:9090"
  correlation_tracking: true
```

### Security Configuration

```yaml
security:
  jwt_enabled: true
  rate_limiting_enabled: true
  default_rate_limit: 100  # requests per minute
  authentication_required: false  # Demo mode
```

## 🚀 Production Readiness

### Deployment Patterns

1. **Blue-Green Deployment**: Zero-downtime updates
2. **Canary Releases**: Gradual feature rollouts
3. **Circuit Breaker Integration**: Automatic failure handling
4. **Health Check Endpoints**: Kubernetes readiness probes

### Scaling Considerations

- **Horizontal Scaling**: Stateless service design
- **Database Partitioning**: Event sourcing support
- **Cache Warming**: Redis pre-loading strategies
- **Event Streaming**: Kafka partition strategies

### Security Hardening

- **Secret Management**: External secret stores
- **Network Policies**: Zero-trust networking
- **Audit Logging**: Comprehensive security events
- **Compliance**: GDPR, SOC2 ready patterns

## 📚 Learning Resources

### Architecture Patterns Demonstrated

1. **Saga Pattern**: Long-running transaction management
2. **Event Sourcing**: Complete audit trail
3. **CQRS**: Command Query Responsibility Segregation
4. **Circuit Breaker**: Fault tolerance
5. **Bulkhead**: Resource isolation
6. **Retry with Backoff**: Transient failure handling

### MMF Framework Deep Dive

- [Event Streaming Documentation](../../docs/event-streaming.md)
- [Observability Guide](../../docs/observability.md)
- [Security Patterns](../../docs/security.md)
- [Configuration Management](../../docs/configuration.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your enhancement
4. Add tests and documentation
5. Submit a pull request

## 📄 License

This demo is part of the Marty Microservices Framework and is licensed under [LICENSE](../../LICENSE).

---

**🎯 Demo Objectives Achieved:**

✅ **Cross-service workflows** with saga orchestration
✅ **Surface observability** with Prometheus/Jaeger/Grafana
✅ **Demonstrate resiliency** with circuit breakers and retries
✅ **Centralized config** with live feature flags
✅ **Real integrations** with Redis and PostgreSQL
✅ **Security posture** with JWT/OIDC and rate limiting

**Ready for enterprise-grade microservice demonstrations! 🚀**
