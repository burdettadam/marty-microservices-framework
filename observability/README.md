# Observability Infrastructure

This directory contains comprehensive observability infrastructure for the Marty Microservices Framework, providing enterprise-grade monitoring, event streaming, and performance analysis capabilities.

## Overview

The observability stack includes:

- **Kafka Event Streaming**: Enterprise event bus for microservice communication
- **Prometheus Monitoring**: Metrics collection and alerting
- **Grafana Dashboards**: Visualization and business intelligence
- **Load Testing**: Performance analysis and capacity planning
- **Distributed Tracing**: Request flow visibility
- **Log Aggregation**: Centralized logging with Loki

## Quick Start

### 1. Start the Observability Stack

```bash
# Start Kafka infrastructure
docker-compose -f observability/kafka/docker-compose.kafka.yml up -d

# Start monitoring stack
docker-compose -f observability/monitoring/docker-compose.monitoring.yml up -d
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **Kafka UI**: http://localhost:8080
- **Jaeger**: http://localhost:16686

### 3. Integrate with Your Service

```python
from observability.kafka import EventBus, KafkaConfig
from observability.metrics import MetricsCollector, MetricsConfig

# Setup metrics
metrics_config = MetricsConfig(
    service_name="my-service",
    service_version="1.0.0"
)
metrics = MetricsCollector(metrics_config)

# Setup event bus
kafka_config = KafkaConfig(
    bootstrap_servers=["localhost:9092"],
    consumer_group_id="my-service"
)
event_bus = EventBus(kafka_config, "my-service")
```

## Components

### 📊 Kafka Event Streaming (`kafka/`)

Enterprise-grade event streaming infrastructure with:

- **Event Bus**: Async publishing and consumption with aiokafka
- **Standard Event Format**: Correlation IDs and structured messages
- **Topic Patterns**: Service and domain event organization
- **Monitoring**: Kafka metrics and consumer lag tracking

**Key Features:**
- Automatic retries and error handling
- Dead letter queue support
- Distributed tracing integration
- Performance monitoring

[📖 Kafka Documentation](kafka/README.md)

### 📈 Monitoring Stack (`monitoring/`)

Comprehensive monitoring with Prometheus, Grafana, and Alertmanager:

- **Prometheus**: Metrics collection from all services
- **Grafana**: Rich dashboards for service and business metrics
- **Alertmanager**: Smart alerting with team routing
- **Alert Rules**: Pre-configured alerts for common issues

**Included Dashboards:**
- Microservice Detail (gRPC metrics, latency, errors)
- Platform Overview (system health, resource usage)
- Business Metrics (transaction volume, success rates)
- Kafka Monitoring (throughput, consumer lag)

[📖 Monitoring Documentation](monitoring/README.md)

### 🎯 Metrics Collection (`metrics/`)

Standardized metrics collection for microservices:

- **gRPC Metrics**: Request rates, latency percentiles, error rates
- **Business Metrics**: Transaction tracking, success rates
- **System Metrics**: Database connections, cache hit rates
- **Custom Metrics**: Easy creation of service-specific metrics

**Example Usage:**
```python
# Automatic gRPC metrics
@grpc_metrics_decorator(metrics_collector)
async def get_user(request):
    return user_service.get_user(request.user_id)

# Business transaction tracking
@business_metrics_decorator(metrics_collector, "user_creation")
async def create_user(user_data):
    return await user_repository.create(user_data)
```

### ⚡ Load Testing (`load_testing/`)

Performance testing and capacity planning:

- **gRPC Load Testing**: Service-specific performance testing
- **HTTP Load Testing**: REST API performance validation
- **Real-time Monitoring**: Live performance metrics during tests
- **Comprehensive Reporting**: Detailed performance analysis

**Example Load Test:**
```python
config = LoadTestConfig(
    target_host="localhost",
    target_port=50051,
    concurrent_users=50,
    test_duration_seconds=300,
    protocol="grpc"
)

runner = LoadTestRunner()
report = await runner.run_load_test(config)
```

## Integration Patterns

### Service Template Integration

Each microservice template includes observability by default:

```python
# In your service initialization
from observability import setup_observability

async def main():
    # Setup observability stack
    metrics, event_bus, tracer = await setup_observability(
        service_name="user-service",
        service_version="1.2.0"
    )

    # Start your service with observability
    server = create_grpc_server(metrics, event_bus)
    await server.start()
```

### Event-Driven Architecture

```python
# Publishing domain events
await publish_domain_event(
    event_bus,
    domain="user",
    event_type="user.created",
    data={"user_id": user.id, "email": user.email},
    correlation_id=context.correlation_id
)

# Consuming events with metrics
@event_handler("user.events")
async def handle_user_event(event: EventMessage):
    metrics.record_business_transaction(
        transaction_type="user_notification",
        duration=0.1,
        status="success"
    )
```

### Performance Monitoring

```python
# Custom business metrics
revenue_counter = metrics.create_custom_counter(
    name="revenue_total",
    description="Total revenue processed",
    labels=["currency", "region"]
)

# Track critical operations
with metrics.time_operation("database_query"):
    results = await database.execute_query(sql)
```

## Alerting Strategy

### Alert Severities

- **Critical**: Service down, very high error rates (>20%), critical latency (>3s)
- **Warning**: High error rates (>5%), high latency (>1s), resource exhaustion
- **Info**: Unusual patterns, capacity planning alerts

### Team Routing

- **Platform Team**: Infrastructure and service health alerts
- **Business Team**: Transaction volume and success rate alerts
- **On-Call**: Critical alerts requiring immediate response

### Runbooks

Each alert includes runbook links for resolution guidance:
- Service down: Restart procedures, health checks
- High error rates: Log analysis, recent deployment checks
- High latency: Performance profiling, resource scaling

## Performance Benchmarks

### Target SLOs

- **Availability**: 99.9% uptime
- **Latency**: P95 < 500ms, P99 < 1000ms
- **Error Rate**: < 1% for business operations
- **Throughput**: 1000+ RPS per service instance

### Load Testing Scenarios

- **Normal Load**: 10 concurrent users, 100 RPS
- **Peak Load**: 50 concurrent users, 500 RPS
- **Stress Test**: 100+ concurrent users, 1000+ RPS
- **Endurance**: Extended duration tests (1+ hours)

## Troubleshooting

### Common Issues

1. **High Memory Usage**: Check for memory leaks, adjust container limits
2. **Database Connection Exhaustion**: Review connection pooling configuration
3. **Kafka Consumer Lag**: Scale consumer instances, optimize processing
4. **Alert Fatigue**: Review alert thresholds, implement alert correlation

### Debug Workflows

1. **Performance Issues**:
   - Check Grafana dashboards for anomalies
   - Run targeted load tests
   - Review trace data in Jaeger

2. **Integration Issues**:
   - Verify Kafka connectivity
   - Check service discovery and registration
   - Review correlation IDs in logs

3. **Capacity Planning**:
   - Analyze historical trends
   - Run load tests with projected traffic
   - Review resource utilization patterns

## Security Considerations

- **Metrics**: No sensitive data in metric labels
- **Events**: PII tokenization in event payloads
- **Monitoring**: Access controls for dashboards and metrics
- **Alerting**: Secure webhook endpoints and notification channels

## Contributing

When adding new observability features:

1. Follow the established patterns for metrics and events
2. Add appropriate dashboards and alerts
3. Include load testing scenarios
4. Update documentation with examples
5. Add integration tests for observability components

For detailed implementation guides, see the component-specific documentation in each subdirectory.
