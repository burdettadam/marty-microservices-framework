"""
Order processing and workflow management service

Production-quality FastAPI service with enterprise infrastructure.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from observability import auto_instrument, init_tracing, instrument_fastapi

from marty_msf.framework.config import BaseServiceConfig
from marty_msf.observability.monitoring import ServiceMonitor

from .routes import router


class OrderServiceConfig(BaseServiceConfig):
    """Configuration for order-service."""

    def __init__(self):
        super().__init__(
            service_name="order-service",
            database_url="sqlite:///orders.db",  # Simple for demo
            secret_key="demo-secret-key"
        )
        self.host = "0.0.0.0"
        self.port = 8001
        self.debug = False
        self.docs_enabled = True


# Global configuration and monitor
config = OrderServiceConfig()
monitor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan with proper startup and shutdown."""
    global monitor

    # Startup
    print(f"Starting {config.service_name} with enterprise infrastructure...")

    # Initialize observability
    init_tracing(service_name=config.service_name)
    auto_instrument()
    instrument_fastapi()

    # Start monitoring
    monitor = ServiceMonitor(config.service_name)
    monitor.start_monitoring()
    app.state.monitor = monitor

    print(f"{config.service_name} started successfully")

    yield

    # Shutdown
    print(f"Shutting down {config.service_name}...")

    if monitor:
        monitor.stop_monitoring()

    print(f"{config.service_name} shutdown complete")


def create_app() -> FastAPI:
    """Create FastAPI application with enterprise infrastructure."""

    # Initialize FastAPI with enterprise configuration
    app = FastAPI(
        title=config.service_name.replace("-", " ").title(),
        description="Order processing and workflow management service",
        version="1.0.0",
        debug=config.debug,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url="/redoc" if config.docs_enabled else None,
        lifespan=lifespan,
    )

    # Add CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router)

    return app


def main():
    """Run the service."""
    app = create_app()

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
