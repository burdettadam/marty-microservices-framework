"""
Production-ready payment processing service with fraud detection and audit logging

This service follows enterprise patterns and the MMF adoption flow:
clone → generate → add business logic

Features:
- Comprehensive logging with correlation IDs
- Prometheus metrics integration
- Health checks and readiness probes
- Structured configuration management
- Error handling and audit logging
- Service mesh ready

Service: production-payment-service
Generated with MMF Service Generator
"""
import asyncio
import json
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
from app.services.production_payment_service_service import (
    ProductionPaymentServiceService,
)
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('production_payment_service_service.log'),
        logging.FileHandler('production_payment_service_service_audit.log')
    ]
)
logger = logging.getLogger("production-payment-service")

# Clear Prometheus registry to avoid duplicates
REGISTRY._collector_to_names.clear()
REGISTRY._names_to_collectors.clear()

# Prometheus Metrics
REQUEST_COUNTER = Counter('production_payment_service_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('production_payment_service_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
ACTIVE_REQUESTS = Gauge('production_payment_service_active_requests', 'Active requests')
BUSINESS_OPERATIONS = Counter('production_payment_service_business_operations_total', 'Business operations', ['operation', 'status'])

# Global service instance
service_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global service_instance

    # Startup
    logger.info("Starting ProductionPaymentService Service...")
    try:
        service_instance = ProductionPaymentServiceService()
        await service_instance.initialize()
        logger.info("Service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down ProductionPaymentService Service...")
    if service_instance:
        await service_instance.cleanup()
    logger.info("Service shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="ProductionPaymentService Service",
    description="Production-ready payment processing service with fraud detection and audit logging",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add correlation ID middleware
add_correlation_id_middleware(app)

# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to collect metrics for all requests"""
    start_time = time.time()
    ACTIVE_REQUESTS.inc()

    try:
        response = await call_next(request)

        # Record metrics
        duration = time.time() - start_time
        REQUEST_DURATION.labels(method=request.method, endpoint=request.url.path).observe(duration)
        REQUEST_COUNTER.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        return response
    finally:
        ACTIVE_REQUESTS.dec()

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging"""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    error_data = {
        "event": "http_exception",
        "correlation_id": correlation_id,
        "status_code": exc.status_code,
        "detail": exc.detail,
        "path": request.url.path,
        "method": request.method,
        "timestamp": datetime.utcnow().isoformat()
    }

    logger.warning(f"HTTP Exception: {json.dumps(error_data)}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    error_data = {
        "event": "unexpected_exception",
        "correlation_id": correlation_id,
        "error": str(exc),
        "error_type": type(exc).__name__,
        "path": request.url.path,
        "method": request.method,
        "timestamp": datetime.utcnow().isoformat()
    }

    logger.error(f"Unexpected Exception: {json.dumps(error_data)}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Health and monitoring endpoints
@app.get("/health", tags=["monitoring"])
async def health_check():
    """Health check endpoint for load balancers and orchestrators"""
    return {
        "status": "healthy",
        "service": "production-payment-service",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/ready", tags=["monitoring"])
async def readiness_check():
    """Readiness check endpoint"""
    try:
        # Add your readiness checks here (database connections, external services, etc.)
        if service_instance:
            is_ready = await service_instance.health_check()
            if is_ready:
                return {
                    "status": "ready",
                    "service": "production-payment-service",
                    "timestamp": datetime.utcnow().isoformat()
                }

        raise HTTPException(status_code=503, detail="Service not ready")
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/info", tags=["monitoring"])
async def service_info():
    """Service information endpoint"""
    settings = get_settings()
    return {
        "service": "production-payment-service",
        "version": "1.0.0",
        "description": "Production-ready payment processing service with fraud detection and audit logging",
        "environment": getattr(settings, 'environment', 'unknown'),
        "framework": "Marty Microservices Framework",
        "generated_at": "2025-10-13 12:00:00",
        "timestamp": datetime.utcnow().isoformat()
    }

# Include API routes
app.include_router(router, prefix="/api/v1")

def get_service() -> ProductionPaymentServiceService:
    """Get the service instance"""
    if service_instance is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return service_instance

if __name__ == "__main__":
    settings = get_settings()

    print(f"🚀 Starting ProductionPaymentService Service...")
    print(f"📊 Metrics: http://localhost:8002/metrics")
    print(f"📋 API Docs: http://localhost:8002/docs")
    print(f"❤️  Health: http://localhost:8002/health")
    print(f"🔄 Ready: http://localhost:8002/ready")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=getattr(settings, 'debug', False),
        log_level="info"
    )
