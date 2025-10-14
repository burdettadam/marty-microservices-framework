"""
Example Service Service

This service is ready for business logic implementation.
Generated with MMF Plugin Service Generator.
"""
import asyncio
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

import uvicorn
from app.api.routes import router

# Import service components
from app.core.config import get_settings
from app.core.middleware import add_correlation_id_middleware
from app.services.example_service_service import ExampleServiceService
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('example_service_service.log'),
        logging.FileHandler('example_service_service_audit.log')
    ]
)
logger = logging.getLogger("example-service")

# Global service instance
service_instance: Optional[ExampleServiceService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global service_instance

    # Startup
    logger.info("Starting example-service service...")

    try:
        # Initialize settings
        settings = get_settings()
        logger.info(f"Loaded settings: {settings.dict()}")

        # Initialize service
        service_instance = ExampleServiceService()
        await service_instance.initialize()

        # TODO: Initialize plugin integration
        # Example:
        # plugin_manager = PluginManager()
        # await plugin_manager.load_plugin("example_business")

        logger.info("Service started successfully")

    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down example-service service...")

    try:
        if service_instance:
            await service_instance.shutdown()

        logger.info("Service shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="Example Service Service",
    description="Generated service ready for business logic",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add correlation ID middleware
add_correlation_id_middleware(app)

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    global service_instance

    if not service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")

    health_status = await service_instance.health_check()

    if health_status["status"] != "healthy":
        raise HTTPException(status_code=503, detail=health_status)

    return health_status


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "example-service",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "message": "Service is ready for business logic"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
