# Store Demo - Comprehensive Microservices Example

This directory contains a complete e-commerce microservices demonstration showcasing the Marty Microservices Framework (MMF) capabilities.

## Directory Structure

```
store-demo/
├── README.md                    # This file
├── docker-compose.yml           # Complete orchestration setup
├── mmf_demo_runner.py          # Demo orchestration and testing
├── mmf_analytics_plugin.py     # Analytics and reporting plugin
├── services/                   # Microservices
│   ├── mmf_order_service.py    # Order processing service
│   ├── mmf_payment_service.py  # Payment processing service
│   └── mmf_inventory_service.py # Inventory management service
├── docker/                     # Docker configuration
│   ├── Dockerfile.order        # Order service container
│   ├── Dockerfile.payment      # Payment service container
│   ├── Dockerfile.inventory    # Inventory service container
│   └── Dockerfile.demo         # Demo runner container
└── monitoring/                 # Observability configuration
    └── prometheus.yml          # Prometheus metrics config
```

## Quick Start

### Docker Compose (Recommended)

1. **Start the complete stack:**
   ```bash
   cd examples/store-demo
   docker compose up -d
   ```

2. **Run the demo:**
   ```bash
   docker compose exec demo-runner python /app/mmf_demo_runner.py
   ```

3. **View results:**
   - Reports: `./reports/` (JSON and text files)
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000

### Local Development

From the repository root:

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Start services (separate terminals):**
   ```bash
   # Terminal 1 - Order Service
   python examples/store-demo/services/mmf_order_service.py

   # Terminal 2 - Payment Service
   python examples/store-demo/services/mmf_payment_service.py

   # Terminal 3 - Inventory Service
   python examples/store-demo/services/mmf_inventory_service.py
   ```

3. **Run demo:**
   ```bash
   python examples/store-demo/mmf_demo_runner.py
   ```

## Services Overview

- **Order Service** (Port 8001): Handles order creation and processing with audit logging
- **Payment Service** (Port 8002): Processes payments with fraud detection simulation
- **Inventory Service** (Port 8003): Manages product inventory and reservations
- **Demo Runner**: Orchestrates load testing and provides analytics

## Performance Characteristics

- **Success Rate**: 63-70% (intentionally includes realistic failures)
- **Response Time**: ~1.8 seconds average
- **Bottleneck**: Payment service (as designed for testing)
- **Concurrent Processing**: Fully async with proper error handling

## Related Documentation

- **[Complete Store Demo Guide](../../docs/STORE_DEMO.md)** - Comprehensive documentation
- **[Framework Architecture](../../docs/architecture.md)** - Framework overview
- **[Development Guide](../../docs/development/README.md)** - Development practices
