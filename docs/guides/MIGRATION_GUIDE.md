# Marty Service Migration Guide

This guide helps you migrate existing Marty microservices to use the unified Marty Microservices Framework (MMF) patterns, eliminating custom service runner code.

## Overview

The goal is to:
1. **Eliminate custom main.py startup code** - Replace with framework-managed service launcher
2. **Standardize configuration** - Use framework configuration patterns
3. **Adopt framework patterns** - Use framework templates and chassis components
4. **Remove duplication** - Eliminate internal framework copies

## Migration Steps

### Step 1: Install/Update Framework Dependencies

If not already done, ensure your service has access to the MMF:

```bash
# Option A: Install as package dependency (recommended for production)
pip install marty-microservices-framework

# Option B: Use local development version
cd path/to/marty-microservices-framework
pip install -e .
```

### Step 2: Refactor main.py

**Before (Custom Pattern):**
```python
# Old main.py with custom startup logic
import asyncio
import signal
import uvicorn
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Custom startup logic
    await init_database()
    init_metrics()
    if settings.metrics_enabled:
        start_http_server(settings.metrics_port)
    yield
    # Custom shutdown logic

async def run_servers():
    app = create_app()
    config = uvicorn.Config(app, host=settings.host, port=settings.port)
    server = uvicorn.Server(config)
    await asyncio.gather(server.serve(), serve_grpc())

def main():
    # Custom signal handlers
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        loop.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_servers())
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    finally:
        loop.close()

if __name__ == "__main__":
    main()
```

**After (Framework Pattern):**
```python
# New main.py - simplified, framework-managed
from fastapi import FastAPI
from datetime import datetime
import structlog

logger = structlog.get_logger()

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Your Service",
        description="Service description",
        version="1.0.0"
    )

    # Add your routes and middleware here
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "timestamp": datetime.utcnow()}

    return app

# Create the app instance - framework will manage the lifecycle
app = create_app()

# Optional: Add lifecycle events
@app.on_event("startup")
async def startup_event():
    logger.info("Service starting up")
    # Add your startup logic here

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Service shutting down")
    # Add your cleanup logic here
```

### Step 3: Create Service Configuration

Create a `config.yaml` file in your service root:

```yaml
# config.yaml
service:
  name: "your-service-name"
  version: "1.0.0"
  description: "Your service description"

# Server configuration
host: "0.0.0.0"
port: 8000

# gRPC configuration (if applicable)
grpc_enabled: true
grpc_port: 50051
grpc_module: "grpc_server:serve"

# Application modules
app_module: "main:app"

# Development settings
debug: false
reload: false
log_level: "info"
access_log: true

# Performance
workers: 1

# Monitoring
metrics_enabled: true
metrics_port: 9090

# Add environment-specific configs in:
# config/development.yaml
# config/production.yaml
```

### Step 4: Update gRPC Module (if applicable)

If your service has gRPC, ensure the gRPC module exports a `serve` function:

```python
# grpc_server.py
import asyncio
import grpc
from concurrent import futures

async def serve():
    """Start gRPC server - called by framework."""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add your gRPC services here
    # add_YourServiceServicer_to_server(YourServiceServicer(), server)

    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)

    await server.start()
    await server.wait_for_termination()
```

### Step 5: Update Service Startup

**Before:**
```bash
# Old way - each service has custom startup
cd src/your-service
python main.py

# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**After:**
```bash
# New way - unified framework launcher
cd your-service-directory
marty runservice

# Or with specific configuration
marty runservice --config config/production.yaml --environment production

# Or with overrides
marty runservice your-service --port 8080 --reload --debug
```

### Step 6: Update Docker/Deployment Configuration

Update your Dockerfile and deployment configurations:

**Dockerfile:**
```dockerfile
# Old way
CMD ["python", "main.py"]

# New way
CMD ["marty", "runservice", "--config", "config/production.yaml"]
```

**Docker Compose:**
```yaml
# docker-compose.yml
services:
  your-service:
    build: .
    command: ["marty", "runservice", "--environment", "development", "--reload"]
    ports:
      - "8000:8000"
      - "50051:50051"
    environment:
      - DEBUG=true
```

**Kubernetes:**
```yaml
# k8s deployment
spec:
  containers:
  - name: your-service
    command: ["marty", "runservice", "--config", "/etc/config/service.yaml"]
```

### Step 7: Remove Custom Service Runner Code

After migration, you can remove:
- Custom signal handlers
- Custom uvicorn configuration
- Custom asyncio event loop management
- Custom server startup/shutdown logic
- Custom lifespan management (move to FastAPI events)

## Environment-Specific Configuration

Create environment-specific configs:

```yaml
# config/development.yaml
debug: true
reload: true
log_level: "debug"
database:
  url: "postgresql://dev_user:dev_pass@localhost/dev_db"

# config/production.yaml
debug: false
reload: false
log_level: "info"
workers: 4
database:
  url: "postgresql://prod_user:prod_pass@prod-db/prod_db"
```

## Testing the Migration

1. **Test with framework CLI:**
   ```bash
   marty runservice --dry-run  # Show what would be executed
   marty runservice --debug    # Run with debug output
   ```

2. **Verify endpoints work:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/metrics
   ```

3. **Test gRPC (if applicable):**
   ```bash
   grpcurl -plaintext localhost:50051 list
   ```

## Benefits After Migration

1. **Consistency** - All services use the same startup patterns
2. **Maintainability** - Framework updates apply to all services
3. **Configuration** - Standardized configuration management
4. **Observability** - Built-in metrics, logging, and tracing
5. **Development** - Faster startup and easier debugging
6. **Deployment** - Simplified deployment configurations

## Troubleshooting

**Service won't start:**
- Check configuration file syntax: `marty runservice --dry-run`
- Verify app module path: `app_module: "main:app"`
- Check working directory and imports

**gRPC not working:**
- Verify `grpc_module` points to correct function
- Ensure gRPC function is `async def serve():`
- Check port conflicts

**Configuration not loading:**
- Verify YAML syntax
- Check file paths and permissions
- Use absolute paths if needed

**Import errors:**
- Ensure framework is installed: `pip install marty-microservices-framework`
- Check Python path and working directory
- Verify all dependencies are installed

For more help, see the [Framework Documentation](../README.md) or create an issue.
