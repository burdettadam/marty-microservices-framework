# ProductionPaymentService Service

A production-ready microservice built with the Marty Microservices Framework.

## Quick Start

This service follows the Marty framework adoption flow: **clone → generate → add business logic**.

### 1. Development Setup

```bash
# Install dependencies
uv sync

# Run the service locally
python main.py
```

### 2. Add Your Business Logic

The service structure is designed for easy business logic integration:

- **`app/services/production_payment_service_service.py`** - Main business logic
- **`app/api/routes.py`** - API endpoint definitions
- **`app/models/`** - Data models and schemas
- **`app/core/config.py`** - Configuration management

### 3. API Endpoints

- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics` (Prometheus format)
- **API Documentation**: `GET /docs` (Swagger/OpenAPI)

### 4. Testing

```bash
# Run unit tests
uv run pytest tests/unit/

# Run integration tests
uv run pytest tests/integration/

# Run all tests with coverage
uv run pytest --cov=app tests/
```

### 5. Docker Deployment

```bash
# Build Docker image
docker build -t production-payment-service:latest .

# Run containerized service
docker run -p 8002:8002 production-payment-service:latest
```

### 6. Kubernetes Deployment

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/base/

# Deploy with service mesh (if enabled)
kubectl apply -k k8s/overlays/service-mesh/
```

## Architecture

This service follows the Marty Microservices Framework patterns:

- **Structured Logging** with correlation IDs
- **Prometheus Metrics** for observability
- **Health Checks** for orchestration
- **Configuration Management** with environment-specific configs
- **Audit Logging** for compliance and debugging
- **Error Handling** with proper HTTP status codes

## Framework Features Used

- ✅ FastAPI for high-performance async API
- ✅ Prometheus metrics integration
- ✅ Structured logging with correlation tracking
- ✅ Health check endpoints
- ✅ Configuration management
- ✅ Docker containerization
- ✅ Kubernetes deployment manifests
- ✅ Service mesh ready (Istio/Linkerd)

## Business Logic Integration

To add your specific business logic:

1. **Define your data models** in `app/models/`
2. **Implement your service logic** in `app/services/production_payment_service_service.py`
3. **Add API endpoints** in `app/api/routes.py`
4. **Configure environment variables** in `app/core/config.py`
5. **Add tests** in `tests/unit/` and `tests/integration/`

## Monitoring and Observability

The service includes comprehensive observability:

- **Metrics**: Prometheus metrics available at `/metrics`
- **Logging**: Structured JSON logging with correlation IDs
- **Health**: Health check at `/health`
- **Tracing**: Ready for distributed tracing integration

## Configuration

Environment-specific configuration is managed through:

- `config/base.yaml` - Base configuration
- `config/development.yaml` - Development overrides
- `config/production.yaml` - Production overrides
- Environment variables for sensitive data

## Contributing

1. Follow the established patterns in the generated code
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all metrics and logging are properly implemented

## Support

For framework documentation and support, see:
- `docs/` directory in the framework root
- Framework README and guides
- Example services in `examples/`
