# Development Guide for petstore-domain

This directory contains development scripts and configuration for the petstore-domain service.

## Quick Start

1. **Deploy to kind cluster:**
   ```bash
   ./dev/deploy.sh
   ```

2. **Start port forwarding:**
   ```bash
   ./dev/port-forward.sh
   ```

3. **Test the service:**
   ```bash
   curl http://localhost:8080/health
   ```

## Scripts

### Infrastructure Scripts
- `port-forward.sh` - Port forwarding helper for accessing the service locally
- `deploy.sh` - Quick deployment script for kind cluster
- `dev-config.yaml` - Development configuration

### Demo and Test Runners
- `experience_polish_demo.py` - Comprehensive demo showcasing all MMF features
- `petstore_demo_runner.py` - Core petstore functionality demo
- `enhanced_petstore_demo_runner.py` - Enhanced demo with event streaming
- `k8s_demo_runner.py` - Kubernetes-focused demo runner
- `kafka_demo.py` - Kafka integration test with production Kafka+Zookeeper

### Kafka Integration Testing
Test the production-like Kafka setup:
```bash
# Test Kafka connectivity and event publishing
python3 dev/kafka_demo.py

# Check Kafka health via API
curl http://localhost:8080/api/orders/events/health
```

Use these demo runners to test various scenarios:
```bash
# Quick experience polish demo
python3 dev/experience_polish_demo.py --scenario quick

# Full customer journey with ML
python3 dev/experience_polish_demo.py --scenario full --customers 3 --export-data

# Error resilience testing
python3 dev/experience_polish_demo.py --scenario error-demo --errors

# Kubernetes-specific demo
python3 dev/k8s_demo_runner.py
```

## Development Endpoints

- Health Check: http://localhost:8080/health
- API Documentation: http://localhost:8080/docs
- Metrics: http://localhost:8080/metrics
- Service Status: http://localhost:8080/api/v1/status

## Port Forwarding

The port forwarding script supports various options:

```bash
# Use default port (8080)
./dev/port-forward.sh

# Use custom local port
./dev/port-forward.sh 8081

# Use custom local and service ports
./dev/port-forward.sh 8081 8080

# Use custom namespace
./dev/port-forward.sh 8081 80 production
```

## Deployment

The deployment script:
1. Builds the Docker image from the framework root
2. Loads the image into the kind cluster
3. Applies Kubernetes manifests
4. Waits for the deployment to be ready

Make sure you have:
- Docker running
- kind cluster running (`kind get clusters`)
- kubectl configured for the cluster

## Configuration

The `dev-config.yaml` file contains service-specific configuration for development:
- Service name and package information
- Kubernetes resource names
- Port configurations
- Endpoint URLs
