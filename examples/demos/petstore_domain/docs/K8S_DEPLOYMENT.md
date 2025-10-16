# 🐾 Enhanced Petstore Kubernetes Deployment

This guide demonstrates deploying the enhanced petstore with complete MMF capabilities on a local Kubernetes cluster using Kind.

## 🚀 Quick Start

### Prerequisites

- **Docker**: Ensure Docker Desktop is running
- **Kind**: Install from [kind.sigs.k8s.io](https://kind.sigs.k8s.io/docs/user/quick-start/)
- **kubectl**: Install from [kubernetes.io](https://kubernetes.io/docs/tasks/tools/)

### One-Command Deployment

```bash
# Deploy the complete stack
./dev/deploy-kind.sh deploy

# Run the demo
python k8s_demo_runner.py
```

## 📋 What Gets Deployed

### Infrastructure Components
- **Kafka**: Event streaming and saga orchestration
- **Redis**: Caching layer for performance
- **PostgreSQL**: Persistent data storage
- **Prometheus**: Metrics collection
- **Grafana**: Dashboards and visualization
- **Jaeger**: Distributed tracing

### Application Features
- **Enhanced Petstore Service**: Full MMF integration
- **Saga-based Order Processing**: Event-driven workflows
- **Circuit Breakers**: Resilience patterns
- **Rate Limiting**: Security controls
- **Feature Flags**: Dynamic configuration
- **Correlation Tracking**: Request tracing

## 🛠 Manual Deployment Steps

### 1. Create Kind Cluster

```bash
# Create cluster with local registry
./dev/deploy-kind.sh deploy
```

This creates:
- Kind cluster named "petstore-demo"
- Local Docker registry on port 5001
- Port forwarding for all services

### 2. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n petstore
kubectl get pods -n monitoring

# Check services
kubectl get svc -n petstore
kubectl get svc -n monitoring
```

### 3. Access Services

| Service | URL | Description |
|---------|-----|-------------|
| Petstore API | http://localhost:30080/petstore-domain | Main application |
| Grafana | http://localhost:30030 | Dashboards (admin/admin) |
| Prometheus | http://localhost:30090 | Metrics |
| Jaeger | http://localhost:30686 | Distributed tracing |

## 🧪 Running the Demo

### Full Demo Suite

```bash
# Run all scenarios
python k8s_demo_runner.py --scenario all

# Run specific scenario
python k8s_demo_runner.py --scenario order_processing_saga

# Run with custom URL
python k8s_demo_runner.py --url http://localhost:30080 --scenario health_check
```

### Available Scenarios

1. **health_check** - Service health and readiness
2. **feature_flags_demo** - Dynamic feature flags
3. **pet_browsing** - Caching and metrics
4. **order_processing_saga** - Event-driven workflows
5. **resilience_patterns** - Circuit breakers and retries
6. **observability_demo** - Metrics and tracing
7. **security_demo** - Rate limiting
8. **caching_demo** - Redis performance
9. **configuration_demo** - Config management

### Demo Output Example

```
🐾 Enhanced Petstore Kubernetes Demo
🔗 Correlation ID: demo-1703123456
🎯 Target: http://localhost:30080/petstore-domain
⏰ Started: 2023-12-21T10:30:45

================================================================================
🚀 Health Check Demo
   Testing service health and readiness
================================================================================

✅ Health Check (Status: 200)
📄 Response: {
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 125.67,
  "dependencies": {
    "database": "connected",
    "redis": "connected",
    "kafka": "connected"
  }
}
🔗 Correlation ID: demo-1703123456
🆔 Request ID: req-abc123
```

## 📊 Monitoring and Observability

### Grafana Dashboards

Access Grafana at http://localhost:30030 (admin/admin):

1. **Petstore Overview**: Application metrics and health
2. **Saga Workflows**: Event processing and compensation
3. **Infrastructure**: Kafka, Redis, PostgreSQL metrics
4. **Performance**: Response times and throughput

### Prometheus Metrics

Key metrics available at http://localhost:30090:

- `petstore_requests_total`: Request counts by endpoint
- `petstore_request_duration_seconds`: Response times
- `petstore_saga_executions_total`: Saga workflow metrics
- `petstore_cache_hits_total`: Redis cache performance
- `petstore_circuit_breaker_state`: Resilience patterns

### Jaeger Tracing

View distributed traces at http://localhost:30686:

- Full request flow from API to database
- Saga compensation tracking
- Performance bottleneck identification
- Service dependency mapping

## 🔧 Development and Debugging

### View Logs

```bash
# Application logs
kubectl logs -f deployment/petstore-domain -n petstore

# Infrastructure logs
kubectl logs -f deployment/kafka -n petstore
kubectl logs -f deployment/redis -n petstore
kubectl logs -f deployment/postgres -n petstore
```

### Port Forwarding

```bash
# Direct access to petstore
kubectl port-forward svc/petstore-domain 8080:8080 -n petstore

# Access database
kubectl port-forward svc/postgres 5432:5432 -n petstore
```

### Exec into Pods

```bash
# Access petstore container
kubectl exec -it deployment/petstore-domain -n petstore -- /bin/bash

# Access database
kubectl exec -it deployment/postgres -n petstore -- psql -U petstore_user -d petstore
```

## 🧹 Cleanup

### Remove Everything

```bash
# Delete cluster and registry
./dev/deploy-kind.sh cleanup
```

### Selective Cleanup

```bash
# Remove just the application
kubectl delete namespace petstore

# Remove monitoring
kubectl delete namespace monitoring
```

## 🐛 Troubleshooting

### Common Issues

**Service Not Ready**
```bash
# Check pod status
kubectl describe pod <pod-name> -n petstore

# Check events
kubectl get events -n petstore --sort-by='.lastTimestamp'
```

**Image Pull Issues**
```bash
# Rebuild and push images
docker build -t localhost:5001/petstore-domain:latest .
docker push localhost:5001/petstore-domain:latest

# Restart deployment
kubectl rollout restart deployment/petstore-domain -n petstore
```

**Networking Issues**
```bash
# Test service connectivity
kubectl run debug-pod --image=curlimages/curl -i --tty --rm -- sh
# Inside pod: curl http://petstore-domain.petstore:8080/health
```

### Resource Issues

If you encounter resource constraints:

```bash
# Check resource usage
kubectl top nodes
kubectl top pods -n petstore

# Scale down if needed
kubectl scale deployment/petstore-domain --replicas=1 -n petstore
```

## 📚 Next Steps

1. **Explore Saga Workflows**: Check Kafka topics and event flow
2. **Performance Testing**: Use load testing tools against the API
3. **Custom Monitoring**: Add your own Grafana dashboards
4. **Security Enhancement**: Implement authentication workflows
5. **Data Migration**: Test database schema changes

## 🔗 Related Documentation

- [MMF Framework Guide](../../docs/README.md)
- [Saga Pattern Documentation](../../docs/guides/event-publishing-guide.md)
- [Observability Setup](../../docs/guides/observability.md)
- [Plugin Development](../../docs/guides/plugin-system.md)

---

🎉 **Congratulations!** You've successfully deployed a production-ready microservice with complete observability, resilience, and event-driven capabilities!
