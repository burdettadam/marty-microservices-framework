# MMF Framework Demos

This directory contains comprehensive demonstrations of all capabilities of the Marty Microservices Framework (MMF). We provide multiple demo options to match your learning style and available time.

## 🚀 Quick Setup

### Prerequisites
1. **Python Environment**: Python 3.8+ with virtual environment
2. **Dependencies**: PostgreSQL, Redis (for full demos)
3. **Optional**: Docker, Kubernetes + Istio (for advanced demos)

### **One-Command Setup**
```bash
# Clone and navigate to the repository
git clone https://github.com/burdettadam/marty-microservices-framework.git
cd marty-microservices-framework

# Activate the virtual environment
source .venv/bin/activate

# Navigate to demos
cd examples/demos

# Start with the interactive launcher
./demo_launcher.sh
```

## 🎯 Demo Options

### 1. 🚀 **Quick Start Demo** (5 minutes)
**Perfect for first-time users**
```bash
python quick_start_demo.py
```
- ✅ **No External Dependencies**: Simulated operations
- ✅ **Core Concepts**: Database, caching, messaging, health checks
- ✅ **Interactive**: Watch MMF in action with live progress
- ✅ **Fast Setup**: Ready to run immediately

### 2. � **Feature Demos** (15-45 minutes)
**Deep dive into specific MMF capabilities**
```bash
# List all available feature demos
python runner/petstore_demo_runner.py --list

# Run specific demos
python runner/petstore_demo_runner.py --demo core         # Core framework
python runner/petstore_demo_runner.py --demo resilience   # Error handling
python runner/petstore_demo_runner.py --demo api-docs     # API documentation
python runner/petstore_demo_runner.py --demo service-mesh # Kubernetes + Istio
```
- ✅ **Real Services**: Connects to actual PostgreSQL, Redis, APIs
- ✅ **Production Patterns**: Circuit breakers, timeouts, retries
- ✅ **Comprehensive Testing**: Real-world scenarios and operations

### 3. 🏪 **Petstore Domain** (2-3 hours)
**Complete production-ready example**
```bash
cd petstore_domain/
python main.py
```
- ✅ **Full Microservices**: Order, Payment, Inventory services
- ✅ **Enterprise Features**: Security, observability, resilience
- ✅ **Service Mesh Ready**: Istio configuration included
- ✅ **Production Patterns**: Event-driven architecture, SAGA workflows

## � What to Expect

### **Quick Start Demo Output**
```
🚀 Welcome to the Marty Microservices Framework!
✅ Database operations completed successfully
✅ Cache operations completed - 95% hit rate!
✅ Message processing completed
✅ Health monitoring active
📊 Performance: 1000 req/sec, 50ms avg response
```

### **Feature Demo Output**
```
🔍 Checking production prerequisites...
✅ PostgreSQL (K8s): Connected to cluster database
✅ Redis (K8s): Cache cluster accessible
✅ API Service (K8s): Health endpoint responding
🎉 All prerequisites satisfied!

[Detailed test results with real metrics]
```

### **Petstore Domain Output**
```
🚀 Starting MMF Petstore Domain Service
📊 Observability: Prometheus metrics at :9090
🔍 API Documentation: Swagger UI at :8080/docs
✅ Order Service: Ready for requests
✅ Payment Service: Payment processing active
✅ Inventory Service: Stock management online
```

## �📋 Interactive Demo Launcher

The easiest way to explore all demos:
```bash
./demo_launcher.sh
```

This interactive script provides:
- 🎯 **Guided Selection**: Choose demos based on your needs
- 📊 **Prerequisites Check**: Verifies requirements before running
- 🚀 **One-Click Launch**: Automated demo execution
- 📚 **Documentation Links**: Direct access to relevant guides

## 🔧 Detailed Setup Instructions

### **Prerequisites Setup**

#### **1. Basic Setup (Required for all demos)**
```bash
# Ensure Python 3.8+ is installed
python3 --version

# Clone the repository
git clone https://github.com/burdettadam/marty-microservices-framework.git
cd marty-microservices-framework

# Activate virtual environment (created during development)
source .venv/bin/activate

# Verify setup
cd examples/demos
python quick_start_demo.py --help
```

#### **2. Database Setup (For feature demos)**
```bash
# Option A: Using Docker (Recommended)
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=mmf_demo \
  -p 5432:5432 postgres:13

docker run -d --name redis \
  -p 6379:6379 redis:alpine

# Option B: Local Installation
# Install PostgreSQL and Redis locally
# Configure with default settings: user=postgres, password=postgres, db=mmf_demo
```

#### **3. Kubernetes Setup (For service mesh demos)**
```bash
# Install kubectl and kind/minikube
# For Kind cluster:
kind create cluster --name mmf-demo

# Install Istio
curl -L https://istio.io/downloadIstio | sh -
istioctl install --set values.defaultRevision=default
```

### **Running Specific Demos**

#### **Quick Start Demo (No prerequisites)**
```bash
cd examples/demos
python quick_start_demo.py          # Standard run
python quick_start_demo.py --verbose # Detailed output
```

#### **Feature Demos (Requires databases)**
```bash
# Check prerequisites first
python runner/petstore_demo_runner.py --check

# List available demos
python runner/petstore_demo_runner.py --list

# Run specific feature demos
python runner/petstore_demo_runner.py --demo core         # 3-5 min
python runner/petstore_demo_runner.py --demo resilience   # 5-8 min
python runner/petstore_demo_runner.py --demo api-docs     # 2-4 min
python runner/petstore_demo_runner.py --demo service-mesh # 8-12 min

# Run all demos
python runner/petstore_demo_runner.py --demo all          # 30-45 min
```

#### **Petstore Domain Demo (Full experience)**
```bash
cd petstore_domain/

# Quick start
python main.py

# Or use the comprehensive demos
./dev/demo.sh                    # Interactive demo
./dev/run_resilience_demo.sh     # Resilience patterns
./dev/demo_api_features.sh       # API documentation
./dev/deploy-kind.sh deploy      # Kubernetes deployment
```

## 📁 Project Structure

```
examples/demos/
├── quick_start_demo.py              # 🚀 5-minute intro demo
├── runner/                          # 🎯 Feature demo runners
│   ├── petstore_demo_runner.py     #    Main feature demo script
│   └── mmf_demo_runner.py          #    Alternative runner
├── petstore_domain/                 # 🏪 Complete example application
│   ├── docs/                       #    📚 Comprehensive documentation
│   ├── dev/                        #    🔧 Demo scripts and tools
│   ├── main.py                     #    🚀 Application entry point
│   ├── app/                        #    💼 Application services
│   ├── k8s/                        #    ☸️  Kubernetes manifests
│   └── docker-compose.enhanced.yml #    🐳 Docker orchestration
├── demo_launcher.sh                # 🎯 Interactive demo selector
├── DEMO_GUIDE.md                   # 📖 Detailed demo guide
└── README.md                       # 📋 This file
```

## 🎓 Learning Paths

### **New to MMF (Start here!)**
1. **Quick Introduction**: `python quick_start_demo.py`
2. **Interactive Guide**: `./demo_launcher.sh`
3. **Feature Exploration**: `python runner/petstore_demo_runner.py --list`
4. **Deep Dive**: `cd petstore_domain/` and explore documentation

### **Evaluating MMF for Production**
1. **Prerequisites Check**: `python runner/petstore_demo_runner.py --check`
2. **Core Features**: `python runner/petstore_demo_runner.py --demo core`
3. **Resilience Testing**: `python runner/petstore_demo_runner.py --demo resilience`
4. **Complete Example**: `cd petstore_domain/ && python main.py`

### **Ready to Build**
1. **Study Patterns**: Explore `petstore_domain/app/` directory structure
2. **Review Documentation**: Check `petstore_domain/docs/` guides
3. **Kubernetes Deployment**: Try `petstore_domain/dev/deploy-kind.sh deploy`
4. **Service Mesh**: Explore `petstore_domain/k8s/service-mesh/`

## 🔍 Troubleshooting

### **Common Issues**

#### **"Module not found" errors**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Check if in correct directory
pwd  # Should end with /examples/demos
```

#### **Database connection failures**
```bash
# Check if services are running
docker ps  # Should show postgres and redis containers

# Test connections
docker exec postgres pg_isready
docker exec redis redis-cli ping
```

#### **Permission denied on scripts**
```bash
# Make scripts executable
chmod +x demo_launcher.sh
chmod +x petstore_domain/dev/*.sh
```

### **Getting Help**
- 📖 **Detailed Guides**: See `DEMO_GUIDE.md` for comprehensive instructions
- 🏪 **Petstore Documentation**: Check `petstore_domain/docs/` directory
- 🛠️  **Framework Docs**: Visit the main `docs/` directory
- 🎯 **Interactive Help**: Run `./demo_launcher.sh` for guided assistance

## 🚀 Next Steps

After running the demos:

1. **📚 Study the Code**: Examine `petstore_domain/app/` for implementation patterns
2. **🔧 Customize**: Modify the petstore example for your domain
3. **🚀 Deploy**: Use the Kubernetes manifests for production deployment
4. **📊 Monitor**: Set up observability with the included monitoring stack
5. **🏗️  Build**: Create your own services using MMF patterns

Ready to build enterprise-grade microservices with MMF! 🎯
