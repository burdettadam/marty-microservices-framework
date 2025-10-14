# MMF Framework Examples

This directory contains comprehensive examples demonstrating all capabilities of the Marty Microservices Framework (MMF). We provide a **hybrid approach** with examples at different levels of complexity to match your needs.

## � Three-Tier Learning Path

### 1. 🚀 Simple Examples - Learn Core Patterns
**Path:** `simple-examples/`
**Time:** 5-10 minutes to understand
**Complexity:** ⭐

Self-contained services demonstrating core MMF patterns:
- ✅ **Minimal Dependencies**: FastAPI + Prometheus only
- ✅ **Single Files**: Easy to understand and modify
- ✅ **Core Patterns**: Health, metrics, logging, communication
- ✅ **Instant Setup**: Run with `python3 filename.py`

### 2. 🏪 Store Demo - Integrated Example
**Path:** `store-demo/`
**Time:** 30-45 minutes to explore
**Complexity:** ⭐⭐

Complete e-commerce example with multiple services:
- ✅ **Business Context**: Real-world store operations
- ✅ **Service Communication**: Order → Payment → Inventory flow
- ✅ **Observability**: Metrics, tracing, health checks
- ✅ **Docker Orchestration**: Complete docker-compose setup

### 3. 🏭 Generated Services - Production Ready
**Path:** `generated-demo/` (create with generator)
**Time:** 1-2 hours to customize
**Complexity:** ⭐⭐⭐

Production-quality services from official templates:
- ✅ **Enterprise Patterns**: Repository, DDD, event sourcing
- ✅ **Framework Integration**: Real MMF components
- ✅ **Kubernetes Ready**: Complete K8s manifests
- ✅ **Service Mesh**: Istio/Linkerd configuration

## 📊 Demo Comparison

| Aspect | store-demo | production-demo |
|--------|------------|-----------------|
| **Purpose** | Learning/Education | Production Template |
| **Complexity** | Simplified | Enterprise-grade |
| **Services** | Single-file mocks | Generated scaffolds |
| **Dependencies** | Mock implementations | Real framework components |
| **Infrastructure** | Docker Compose only | Full K8s + Service Mesh |
| **Business Logic** | Inline examples | Proper service layers |

### **Core Architecture**
- **Microservices Pattern**: Order, Payment, and Inventory services
- **Service Communication**: HTTP APIs with proper error handling
- **Load Testing**: Comprehensive performance analysis and bottleneck detection
- **Observability**: Prometheus metrics, Grafana dashboards, distributed tracing

### **Enterprise Features**
- **Configuration Management**: Environment-based config with validation
- **Security Framework**: JWT auth, RBAC, rate limiting, API keys
- **Event Publishing**: Audit, notification, and business events
- **Database Patterns**: Repository pattern, transactions, audit capabilities
- **Plugin System**: Extensible architecture with analytics plugins

### **Advanced Capabilities**
- **Resilience Patterns**: Circuit breakers, retries, graceful degradation
- **Performance Monitoring**: Real-time metrics and alerting
- **Service Migration**: Patterns for monolith decomposition
- **Testing Framework**: Load testing, contract testing, chaos engineering

## 🚀 Quick Start

### **1. Run the Complete Demo**
```bash
# Navigate to the store demo
cd examples/store-demo

# Start all services with Docker Compose
docker-compose up -d

# Run the comprehensive demo runner
python mmf_demo_runner.py

# Check generated reports
ls -la reports/
```

### **2. Individual Demo Components**
```bash
# Configuration Management Demo
python enhanced_config_demo.py

# Security Framework Demo
python enhanced_security_demo.py

# Event Publishing Demo
python enhanced_events_demo.py

# Complete Integration Demo
python comprehensive_demo.py
```

## 📁 Store Demo Structure

```
store-demo/
├── services/                    # Microservices implementations
│   ├── mmf_order_service.py    # Order management service
│   ├── mmf_payment_service.py  # Payment processing service
│   └── mmf_inventory_service.py # Inventory management service
├── docker/                      # Docker configurations
│   ├── Dockerfile.order        # Order service container
│   ├── Dockerfile.payment      # Payment service container
│   └── Dockerfile.inventory    # Inventory service container
├── monitoring/                  # Observability configuration
│   └── prometheus.yml          # Metrics collection setup
├── reports/                     # Demo output and analysis
│   ├── README.md               # Reports documentation
│   ├── demo_output_*.txt       # Complete console output
│   └── demo_results_*.json     # Structured analysis data
├── docker-compose.yml          # Multi-service orchestration
├── mmf_demo_runner.py         # Main demo orchestrator
├── enhanced_config_demo.py    # Configuration patterns
├── enhanced_security_demo.py  # Security implementations
├── enhanced_events_demo.py    # Event publishing patterns
└── comprehensive_demo.py      # Integration showcase
```

## 🔧 Demo Components Explained

### **mmf_demo_runner.py** - Main Orchestrator
- **Purpose**: Coordinates all demo components and generates reports
- **Features**: Load testing, performance analysis, service orchestration
- **Outputs**: Both JSON structured data and complete text logs
- **Key Capabilities**: Bottleneck detection, performance metrics, service health monitoring

### **enhanced_config_demo.py** - Configuration Management
- **Purpose**: Demonstrates environment-based configuration patterns
- **Features**: Service-specific configs, validation, environment detection
- **Integration**: Shows config management across all microservices
- **Patterns**: Development, testing, production environment handling

### **enhanced_security_demo.py** - Security Framework
- **Purpose**: Complete security implementation showcase
- **Features**: JWT authentication, RBAC, rate limiting, API keys
- **Integration**: Security middleware across all services
- **Patterns**: Token management, role/permission validation, request throttling

### **enhanced_events_demo.py** - Event Publishing
- **Purpose**: Unified event system demonstration
- **Features**: Audit events, notifications, business events, event correlation
- **Integration**: Event-driven architecture across services
- **Patterns**: Async event handling, event sourcing, cross-service communication

### **comprehensive_demo.py** - Integration Showcase
- **Purpose**: Demonstrates all framework capabilities working together
- **Features**: End-to-end workflows, service interactions, complete feature integration
- **Integration**: Shows how all components work as a cohesive system
- **Patterns**: Real-world scenarios, business process automation

## 🎯 Learning Paths

### **For New Developers**
1. Start with `enhanced_config_demo.py` to understand configuration patterns
2. Explore `enhanced_security_demo.py` for authentication/authorization
3. Run `enhanced_events_demo.py` to see event-driven architecture
4. Execute `comprehensive_demo.py` for complete integration
5. Finally, run `mmf_demo_runner.py` for full system demonstration

### **For Migration Projects**
1. Review `comprehensive_demo.py` for migration patterns
2. Study service structures in `services/` directory
3. Examine Docker configurations for containerization
4. Use monitoring setup as observability template
5. Adapt patterns from enhanced demos to your services

### **For Performance Analysis**
1. Run `mmf_demo_runner.py` with different load patterns
2. Examine generated reports in `reports/` directory
3. Study bottleneck analysis and recommendations
4. Use monitoring configuration for production observability
5. Apply performance optimization suggestions

## 📊 Report Analysis

The demo generates comprehensive reports in the `reports/` directory:

### **Structured Data (JSON)**
- Service performance metrics
- Load testing results
- Bottleneck analysis
- Resource utilization
- Error rates and patterns

### **Complete Logs (Text)**
- Full console output capture
- Detailed execution traces
- Debug information
- Service interaction logs
- Framework behavior analysis

## 🔍 Framework Capabilities Demonstrated

| Component | Enhanced Demo | Store Services | Integration |
|-----------|---------------|----------------|-------------|
| **Configuration** | ✅ Environment detection | ✅ Service-specific configs | ✅ Cross-service consistency |
| **Security** | ✅ JWT/RBAC/Rate limiting | ✅ API protection | ✅ Service-to-service auth |
| **Events** | ✅ All event types | ✅ Business workflows | ✅ Event correlation |
| **Database** | ✅ Repository patterns | ✅ Transaction handling | ✅ Data consistency |
| **Observability** | ✅ Metrics/Tracing | ✅ Service monitoring | ✅ Performance analysis |
| **Load Testing** | ✅ Performance analysis | ✅ Bottleneck detection | ✅ Scaling recommendations |

## 🚀 Next Steps

1. **Explore the Code**: Examine each enhanced demo to understand patterns
2. **Run Load Tests**: Use `mmf_demo_runner.py` to analyze performance
3. **Study Reports**: Review generated analysis for optimization insights
4. **Adapt Patterns**: Apply demonstrated patterns to your microservices
5. **Scale Up**: Use Docker configurations for production deployment

For detailed framework documentation, see [docs/README.md](../docs/README.md).
