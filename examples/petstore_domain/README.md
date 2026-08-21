# Petstore Domain Example

This directory contains a complete example domain implementation using the Marty Microservices Framework (MMF). It demonstrates **Hexagonal Architecture (Ports and Adapters)** with **Bounded Context Isolation** - each service owns its own domain model.

## 🏗️ Architecture

All services follow the same strict Hexagonal Architecture boundaries as the Rust `mmf-services` identity implementation:

```
service/
├── domain/                 # Pure business logic (ZERO external dependencies)
│   ├── entities.py         # Domain entities with identity
│   ├── value_objects.py    # Immutable value types
│   └── exceptions.py       # Domain-specific exceptions
├── application/            # Use cases and port definitions
│   ├── ports/              # Interfaces (ABCs) for infrastructure
│   │   └── *_repository.py # Repository port definitions
│   └── use_cases/          # Application services
├── infrastructure/         # Concrete adapters
│   └── adapters/
│       ├── input/          # Driving adapters (HTTP API, CLI)
│       │   └── api.py      # FastAPI routes
│       └── output/         # Driven adapters (repositories)
│           └── in_memory_*.py
└── di_config.py            # DI container (inherits from mmf.core.di.BaseDIContainer)
```

**Dependency Rule**: `Infrastructure` → `Application` → `Domain`

## 🔒 Bounded Context Isolation

Each service is a **bounded context** with its own domain model:

| Service | Domain Concept | NOT shared with |
|---------|---------------|-----------------|
| `pet_service` | `Pet` entity | Other services don't import `Pet` |
| `store_service` | `CatalogItem`, `Order` | Store's "pet" is a `CatalogItem`, not `Pet` |
| `delivery_board_service` | `Delivery`, `Truck` | Delivery doesn't know about pets or orders |

Services communicate via HTTP APIs, not by sharing domain models.

## 📂 Structure

```
petstore_domain/
├── README.md                    # This file
├── services/                    # Bounded Context Services
│   ├── pet_service/             # Pet management (Hexagonal)
│   ├── store_service/           # Store & orders (Hexagonal)
│   └── delivery_board_service/  # Delivery dispatch (Hexagonal)
├── plugins/                     # Plugin configurations
│   ├── marty.yaml               # Marty Trust PKI plugin
│   └── production_payment_service.yaml
├── config/                      # Domain-specific configuration
├── docs/                        # Domain documentation
└── k8s/                         # Kubernetes manifests
```

## 🚀 Running the Services

### Running Locally

Each service can be run independently using the Hexagonal Architecture version:

```bash
# Pet Service (port 8000)
uvicorn examples.petstore_domain.services.pet_service.main:app --port 8000

# Store Service (port 8001) - Hexagonal version
uvicorn examples.petstore_domain.services.store_service.main_hexagonal:app --port 8001

# Delivery Board Service (port 8002) - Hexagonal version
uvicorn examples.petstore_domain.services.delivery_board_service.main_hexagonal:app --port 8002
```

### Running with Docker Compose

You can also run the entire stack using Docker Compose:

```bash
# Start all services
docker compose up --build

# Stop all services
docker compose down
```

The services will be available at:
- Pet Service: http://localhost:8000
- Store Service: http://localhost:8001
- Delivery Board Service: http://localhost:8002

### Observability & Monitoring

The stack includes a full observability suite:
- **Log Viewer (Dozzle)**: http://localhost:8888
- **Distributed Tracing (Jaeger)**: http://localhost:16686
- **Metrics (Prometheus)**: http://localhost:9090
- **Dashboards (Grafana)**: http://localhost:3000 (User: `admin`, Pass: `admin`)

### Running the Demo Scenario

A demo driver script is included to simulate traffic and interactions:

```bash
# Run the demo scenario
make petstore-demo-run
```

This script will:
1. Create random pets
2. Place orders for those pets
3. Show a summary of actions performed

## 🧪 Architecture Enforcement

The architecture is enforced by automated tests using `pytest-archon`:

```bash
# Run architecture tests
uv run pytest mmf/tests/test_architecture.py -v
```

These tests ensure:
- **Domain isolation**: Domain layers cannot import from Application or Infrastructure
- **Application isolation**: Application layers cannot import from Infrastructure
- **Bounded context isolation**: Services cannot import from other services' internal layers

## 📚 Reference Implementation

For the canonical example of Hexagonal Architecture in MMF, see:
- `crates/mmf-services/src/identity*.rs` - The production Rust reference implementation
- `docs/architecture/STANDARDS.md` - Architectural standards and rules

## Plugin Configuration

The `plugins/` directory contains configurations for plugins used in this domain:

### marty.yaml

Configuration for the Marty Trust PKI plugin, demonstrating:

- Trust anchor and PKD integration
- Document signing services
- Certificate management
- Security configurations
- MMF database integration

### production_payment_service.yaml

Configuration for a production payment service plugin, demonstrating:

- Payment provider integration (Stripe)
- Fraud detection settings
- Audit logging
- Security and rate limiting
- Database requirements

## Plugin Configuration Loading

These plugin configurations demonstrate the MMF plugin configuration loading strategy:

1. **Plugin Discovery**: Plugins are discovered in the `plugins/` directory
2. **Configuration Loading**: Plugin configs are loaded hierarchically with environment overrides
3. **Dependency Resolution**: Plugin dependencies are resolved automatically
4. **Service Integration**: Plugins integrate with MMF's unified configuration system


## Usage

This example demonstrates:

- How to structure a business domain using MMF
- Plugin configuration patterns
- Integration with MMF's unified systems
- Best practices for domain organization

## Microservice Demo: Pet Store + Delivery Board

Three lightweight FastAPI services show the end-to-end shop and delivery flow:

- **pet-service** (`:8000`): Pet records and profiles
- **store-service** (`:8001`): Customer-facing shop and orders
- **delivery-board-service** (`:8002`): Manages trucks, queues deliveries, auto-scales surge trucks

### Run locally

```bash
# Terminal 1: delivery board
uvicorn examples.petstore_domain.services.delivery_board_service.main:app --port 8002 --reload

# Terminal 2: store service (points to delivery board; override via DELIVERY_BOARD_URL)
uvicorn examples.petstore_domain.services.store_service.main:app --port 8001 --reload

# Optional Terminal 3: pet service backing data
uvicorn examples.petstore_domain.services.pet_service.main:app --port 8000 --reload
```

The store service persists orders/catalog via SQLModel in SQLite at `./var/store.db` by default (`STORE_DB_URL` overrides it). Remove the file to reset demo data.

### Try the flow

```bash
# Browse catalog
curl http://localhost:8001/catalog

# Buy a pet with delivery
curl -X POST http://localhost:8001/orders \
  -H "Content-Type: application/json" \
  -d '{"pet_id":"corgi","quantity":1,"customer_name":"Ada","delivery_requested":true,"delivery_address":"123 Microservice Way"}'

# Check delivery board assignment
curl http://localhost:8002/deliveries
```

### Run on kind (Kubernetes)

Prereqs: Docker, kind, kubectl.

```bash
# Build, load images, and apply manifests to a kind cluster named "petstore"
cd examples/petstore_domain
bash k8s/kind-deploy.sh

# Watch pods
kubectl -n petstore get pods

# Port-forward the storefront
kubectl -n petstore port-forward svc/store-service 8001:8001
# then hit the same curl commands as above against localhost:8001
```

## Framework Integration

The plugin configurations use MMF's unified configuration system features:

- Secret references with `${SECRET:key}` syntax
- Environment-specific overrides
- Database integration patterns
- Security configuration inheritance
- Monitoring and observability integration
