# Production Demo - Marty Microservices Framework

This directory contains a **production-quality** demonstration of the Marty Microservices Framework, generated using the official service templates and scaffolding tools.

## 🏗️ Architecture Overview

Unlike the `store-demo/` (which uses simplified mock services for learning), this demo uses **fully-generated production services** with:

- **Enterprise-grade FastAPI/gRPC services** generated from official templates
- **Full framework integration** using real MMF components
- **Production patterns** including repositories, event sourcing, observability
- **Comprehensive infrastructure** including service mesh, monitoring, security

## 🔧 Generated Services

The services in this demo are generated using:
```bash
python scripts/generate_service.py --type fastapi --name order-service --output examples/production-demo/services/
python scripts/generate_service.py --type fastapi --name payment-service --output examples/production-demo/services/
python scripts/generate_service.py --type fastapi --name inventory-service --output examples/production-demo/services/
```

## 📁 Structure

```
production-demo/
├── services/               # Generated production services
│   ├── order_service/     # Full FastAPI service with MMF integration
│   ├── payment_service/   # Full FastAPI service with MMF integration
│   └── inventory_service/ # Full FastAPI service with MMF integration
├── docker/                # Production Docker configurations
├── monitoring/            # Full observability stack
├── reports/               # Demo analysis and metrics
├── k8s/                   # Kubernetes manifests (if generated)
└── docker-compose.yml     # Multi-service orchestration
```

## 🚀 Key Differences from store-demo

| Aspect | store-demo | production-demo |
|--------|------------|-----------------|
| **Purpose** | Learning/Tutorial | Production Template |
| **Services** | Single-file mocks | Full generated scaffolds |
| **Dependencies** | Mock implementations | Real framework imports |
| **Structure** | Simplified | Enterprise-grade |
| **Patterns** | Basic examples | Repository, DDD, CQRS |
| **Infrastructure** | Minimal | Full stack |

## 🎯 Business Logic

This demo implements the same e-commerce workflow as store-demo:
- **Order Processing**: Customer orders with validation
- **Payment Processing**: Payment validation and processing
- **Inventory Management**: Stock checking and reservation
- **Event-Driven Architecture**: Cross-service communication
- **Observability**: Comprehensive monitoring and tracing

## 🔍 Comparison with store-demo

The `store-demo/` directory is preserved as a backup and learning resource. It contains:
- Simplified service implementations for educational purposes
- Mock framework components for easy understanding
- Single-file services for quick comprehension

This `production-demo/` showcases:
- What services look like when properly generated
- How the framework integrates in production scenarios
- Full enterprise patterns and infrastructure

## 🚀 Getting Started

```bash
# Navigate to production demo
cd examples/production-demo

# Start all services
docker-compose up -d

# Run the demo
python production_demo_runner.py
```

See individual service README files for detailed documentation.
