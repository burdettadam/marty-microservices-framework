# MMF Framework: Examples vs Generators - Decision Guide

This guide helps you choose the right approach for your MMF (Marty Microservices Framework) development needs.

## 🎯 TL;DR - Quick Decision Tree

```
Are you...
├── Learning MMF concepts? → Use Simple Examples
├── Prototyping quickly? → Use Simple Examples
├── Building production services? → Use Generators
└── Migrating existing services? → Use Generators
```

## 📊 Comparison Matrix

| Aspect | Simple Examples | Service Generators |
|--------|----------------|-------------------|
| **Setup Time** | < 1 minute | 5-10 minutes |
| **Files Generated** | 1 file per concept | 15-20 files per service |
| **Dependencies** | Minimal (FastAPI + Prometheus) | Full MMF Framework |
| **Learning Curve** | Gentle | Steep |
| **Production Ready** | Educational patterns | Enterprise architecture |
| **Customization** | Easy to modify | Template-based |
| **Framework Integration** | Optional | Full integration |
| **Observability** | Basic metrics | Full telemetry |
| **Testing** | Simple | Comprehensive |
| **Documentation** | Inline comments | Generated docs |

## 🚀 Approach 1: Simple Examples

### When to Use
- **Learning MMF patterns** for the first time
- **Quick prototyping** of microservice concepts
- **Understanding core patterns** before production
- **Teaching/training** microservices concepts
- **Proof of concepts** and demos

### What You Get
```
examples/simple-examples/
├── basic_service.py         # Core patterns in 1 file
├── communication_service.py # Service-to-service calls
├── event_service.py        # Event-driven patterns
└── README.md              # Learning guide
```

### Key Features
- ✅ **Self-contained**: Each file demonstrates complete concepts
- ✅ **Zero setup**: Run directly with Python
- ✅ **Educational**: Extensive comments explaining patterns
- ✅ **Minimal deps**: Only FastAPI, Prometheus, standard library
- ✅ **Quick iteration**: Easy to modify and experiment

### Example Usage
```bash
# Start learning immediately
python examples/simple-examples/basic_service.py

# Test the patterns
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

### Migration Path
When ready for production:
1. Understand the patterns from simple examples
2. Use generators to create production services
3. Copy business logic from simple examples
4. Add enterprise features as needed

## 🏭 Approach 2: Service Generators

### When to Use
- **Production microservices** deployment
- **Enterprise architecture** requirements
- **Full MMF framework integration** needed
- **Scalable service development**
- **Team standardization**

### What You Get
```bash
# Generate a production service
python scripts/generate_service.py simple-fastapi user-service --port 8001

# Result: Full service structure
examples/user_service/
├── main.py                 # Service entry point
├── requirements.txt        # Dependencies
├── Dockerfile             # Container config
├── README.md             # Service docs
└── ...                   # Additional files
```

### Generator Types

#### 1. Simple FastAPI (`simple-fastapi`)
**Complexity: ⭐⭐**
- Clean FastAPI service with MMF patterns
- Framework integration with fallbacks
- Suitable for most production use cases
- Easy to understand and modify

```bash
python scripts/generate_service.py simple-fastapi order-service --port 8001
```

#### 2. FastAPI (`fastapi`) - Legacy Complex
**Complexity: ⭐⭐⭐⭐**
- Full enterprise architecture
- Complex directory structure
- Advanced patterns (DDD, CQRS, etc.)
- Use only for complex business domains

#### 3. gRPC (`grpc`)
**Complexity: ⭐⭐⭐**
- High-performance gRPC services
- Protocol buffer integration
- Service mesh ready

#### 4. Hybrid (`hybrid`)
**Complexity: ⭐⭐⭐⭐**
- Both HTTP and gRPC endpoints
- Maximum flexibility
- Complex configuration

### Production Features
- ✅ **Full Framework Integration**: Real MMF imports and patterns
- ✅ **Enterprise Observability**: OpenTelemetry, metrics, tracing
- ✅ **Production Config**: Environment-based configuration
- ✅ **Container Ready**: Dockerfile and health checks
- ✅ **Testing Framework**: Comprehensive test structure
- ✅ **Documentation**: Auto-generated service docs

## 🛣️ Learning Path Recommendations

### Phase 1: Foundation (Simple Examples)
```
Week 1: Run basic_service.py
└── Learn: Health checks, metrics, logging

Week 2: Run communication_service.py
└── Learn: Service calls, circuit breakers, correlation IDs

Week 3: Run event_service.py
└── Learn: Event patterns, retry logic, dead letter queues
```

### Phase 2: Production Preparation (Generators)
```
Week 4: Generate simple-fastapi service
└── Learn: Framework integration, production patterns

Week 5: Deploy generated service
└── Learn: Containerization, monitoring, deployment

Week 6: Add business logic
└── Learn: Migration from examples to production
```

### Phase 3: Advanced Patterns (Complex Generators)
```
Later: Use complex generators for enterprise needs
└── Learn: DDD, CQRS, advanced architecture patterns
```

## 📋 Decision Criteria

### Use Simple Examples If...
- [ ] You're new to MMF or microservices
- [ ] You need to prototype quickly (< 1 hour)
- [ ] You want to understand core patterns first
- [ ] You're teaching or learning
- [ ] You prefer minimal dependencies
- [ ] You want to see everything in one file

### Use Simple FastAPI Generator If...
- [ ] You're building production services
- [ ] You want MMF framework integration
- [ ] You need standardized service structure
- [ ] You want container deployment
- [ ] You need proper testing setup
- [ ] You're comfortable with MMF concepts

### Use Complex Generators If...
- [ ] You have complex business domains
- [ ] You need advanced architectural patterns
- [ ] You're building enterprise-scale systems
- [ ] You have dedicated DevOps support
- [ ] You need full observability stack

## 🔄 Migration Strategies

### From Simple Examples to Production
1. **Copy Business Logic**: Take your working logic from examples
2. **Generate Service**: Use `simple-fastapi` generator
3. **Integrate Logic**: Add business logic to generated structure
4. **Add Dependencies**: Integrate databases, message queues, etc.
5. **Deploy**: Use generated Dockerfile and configs

### From Simple Generator to Complex
1. **Validate Simple Works**: Ensure simple generated service works
2. **Generate Complex**: Create new service with complex generator
3. **Migrate Logic**: Move business logic to new structure
4. **Add Enterprise Features**: Implement DDD, CQRS, etc.
5. **Replace Deployment**: Switch to new service

## 🏗️ Architecture Evolution

```
Simple Examples (Learning)
    ↓ [Understand patterns]
Simple FastAPI Generator (Production)
    ↓ [Need complexity]
Complex Generators (Enterprise)
    ↓ [Scale to many services]
Service Mesh + Advanced Patterns
```

## 📊 Team Adoption Strategy

### For New Teams
1. Start with simple examples for learning
2. Move to simple generators for first production services
3. Gradually adopt complex patterns as needed

### For Experienced Teams
1. Review simple examples to understand MMF patterns
2. Jump to appropriate generator based on requirements
3. Establish team standards and templates

## 🧰 Tool Selection Guide

| Use Case | Tool | Why |
|----------|------|-----|
| Learn MMF | `examples/simple-examples/` | Educational, self-contained |
| Quick Demo | `examples/simple-examples/` | Fast setup, easy to modify |
| Production API | `generate_service.py simple-fastapi` | Production-ready, not complex |
| Enterprise Service | `generate_service.py fastapi` | Full architecture patterns |
| High Performance | `generate_service.py grpc` | gRPC performance |
| Flexibility | `generate_service.py hybrid` | Both HTTP and gRPC |

## 🎓 Training Recommendations

### For Developers New to Microservices
```
Day 1-2: Run and modify simple examples
Day 3-4: Generate simple service, understand structure
Day 5: Deploy simple service, add basic business logic
Week 2: Add more services, practice service communication
Week 3+: Move to complex patterns as needed
```

### For Experienced Developers
```
Day 1: Review simple examples to understand MMF patterns
Day 2: Generate production service, understand framework
Day 3+: Build production services with business logic
```

## 🔍 Quality Gates

### Simple Examples
- [ ] Health endpoint responds
- [ ] Metrics are collected
- [ ] Basic business logic works
- [ ] Logging shows structured output

### Generated Services
- [ ] Service starts without errors
- [ ] Framework integration works
- [ ] Container builds successfully
- [ ] Tests pass
- [ ] Documentation is complete

---

## 📚 Next Steps

1. **Start Learning**: Try `examples/simple-examples/README.md`
2. **Generate First Service**: Use `simple-fastapi` generator
3. **Join Community**: Contribute patterns and improvements
4. **Scale Up**: Move to complex generators when needed

The hybrid approach gives you the best of both worlds: **Learn with examples, build with generators**! 🚀
