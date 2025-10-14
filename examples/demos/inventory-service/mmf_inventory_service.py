"""
MMF Demo: Inventory Service
Demonstrates inventory management with stock levels and reservation tracking
"""
import json
import logging
import random
import sys
import time
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('inventory_service_audit.log')
    ]
)
logger = logging.getLogger("inventory-service")

app = FastAPI(
    title="MMF Inventory Service",
    description="Inventory management with stock tracking and reservations",
    version="1.0.0"
)

# Prometheus Metrics
INVENTORY_REQUESTS = Counter('inventory_service_requests_total', 'Total inventory requests', ['operation', 'status'])
INVENTORY_PROCESSING_TIME = Histogram('inventory_service_processing_seconds', 'Processing time', ['operation'])
STOCK_LEVELS = Gauge('inventory_service_stock_levels', 'Current stock levels', ['product_id'])
ACTIVE_RESERVATIONS = Gauge('inventory_service_active_reservations', 'Active inventory reservations')

# Data Models
class InventoryItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class InventoryCheckRequest(BaseModel):
    items: list[InventoryItem]

class InventoryReserveRequest(BaseModel):
    items: list[InventoryItem]

# Sample inventory data (in production: database)
inventory_stock = {
    "LAPTOP-001": {"stock": 50, "reserved": 0, "price": 999.99},
    "PHONE-002": {"stock": 100, "reserved": 0, "price": 599.99},
    "TABLET-003": {"stock": 75, "reserved": 0, "price": 399.99},
    "HEADPHONES-004": {"stock": 200, "reserved": 0, "price": 199.99},
    "MONITOR-005": {"stock": 30, "reserved": 0, "price": 299.99}
}

reservations_db = {}

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID for distributed tracing"""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id

    logger.info(f"Inventory request received - Correlation ID: {correlation_id}, Path: {request.url.path}")

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

@app.on_event("startup")
async def startup_event():
    """Initialize stock level metrics on startup"""
    for product_id, data in inventory_stock.items():
        STOCK_LEVELS.labels(product_id=product_id).set(data["stock"])

@app.post("/inventory/check")
async def check_inventory(request_data: InventoryCheckRequest, request: Request):
    """Check inventory availability"""
    start_time = time.time()
    correlation_id = request.state.correlation_id

    try:
        # Audit log: Inventory check started
        audit_data = {
            "event": "inventory_check_started",
            "correlation_id": correlation_id,
            "items_requested": len(request_data.items),
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"AUDIT: {json.dumps(audit_data)}")

        availability_results = []
        all_available = True

        for item in request_data.items:
            # Simulate database lookup delay
            time.sleep(random.uniform(0.01, 0.05))  # 10-50ms delay per item

            if item.product_id not in inventory_stock:
                availability_results.append({
                    "product_id": item.product_id,
                    "requested": item.quantity,
                    "available": 0,
                    "sufficient": False
                })
                all_available = False
                continue

            stock_data = inventory_stock[item.product_id]
            available_stock = stock_data["stock"] - stock_data["reserved"]
            sufficient = available_stock >= item.quantity

            if not sufficient:
                all_available = False

            availability_results.append({
                "product_id": item.product_id,
                "requested": item.quantity,
                "available": available_stock,
                "sufficient": sufficient
            })

        processing_time = time.time() - start_time
        INVENTORY_PROCESSING_TIME.labels(operation="check").observe(processing_time)
        INVENTORY_REQUESTS.labels(operation="check", status="success").inc()

        # Final audit log
        audit_data.update({
            "event": "inventory_check_completed",
            "available": all_available,
            "processing_time_ms": processing_time * 1000,
            "results": availability_results
        })
        logger.info(f"AUDIT: {json.dumps(audit_data)}")

        return {
            "available": all_available,
            "correlation_id": correlation_id,
            "processing_time_ms": round(processing_time * 1000, 2),
            "items": availability_results
        }

    except Exception as e:
        processing_time = time.time() - start_time
        INVENTORY_REQUESTS.labels(operation="check", status="error").inc()

        error_audit = {
            "event": "inventory_check_failed",
            "correlation_id": correlation_id,
            "error": str(e),
            "processing_time_ms": processing_time * 1000,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.error(f"AUDIT: {json.dumps(error_audit)}")
        raise

@app.post("/inventory/reserve")
async def reserve_inventory(request_data: InventoryReserveRequest, request: Request):
    """Reserve inventory items"""
    start_time = time.time()
    correlation_id = request.state.correlation_id
    reservation_id = f"RES-{uuid.uuid4().hex[:8].upper()}"

    ACTIVE_RESERVATIONS.inc()

    try:
        # Audit log: Reservation started
        audit_data = {
            "event": "inventory_reservation_started",
            "reservation_id": reservation_id,
            "correlation_id": correlation_id,
            "items_to_reserve": len(request_data.items),
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"AUDIT: {json.dumps(audit_data)}")

        reservation_results = []
        all_reserved = True

        # First pass: Check if all items can be reserved
        for item in request_data.items:
            if item.product_id not in inventory_stock:
                all_reserved = False
                break

            stock_data = inventory_stock[item.product_id]
            available_stock = stock_data["stock"] - stock_data["reserved"]

            if available_stock < item.quantity:
                all_reserved = False
                break

        if not all_reserved:
            INVENTORY_REQUESTS.labels(operation="reserve", status="failed").inc()
            raise HTTPException(status_code=400, detail="Insufficient inventory for reservation")

        # Second pass: Actually reserve the items
        for item in request_data.items:
            # Simulate database update delay
            time.sleep(random.uniform(0.02, 0.08))  # 20-80ms delay per item

            stock_data = inventory_stock[item.product_id]
            stock_data["reserved"] += item.quantity

            # Update metrics
            STOCK_LEVELS.labels(product_id=item.product_id).set(
                stock_data["stock"] - stock_data["reserved"]
            )

            reservation_results.append({
                "product_id": item.product_id,
                "quantity_reserved": item.quantity,
                "remaining_stock": stock_data["stock"] - stock_data["reserved"]
            })

        # Store reservation record
        reservation_record = {
            "reservation_id": reservation_id,
            "correlation_id": correlation_id,
            "items": [item.dict() for item in request_data.items],
            "status": "active",
            "created_at": datetime.utcnow().isoformat()
        }
        reservations_db[reservation_id] = reservation_record

        processing_time = time.time() - start_time
        INVENTORY_PROCESSING_TIME.labels(operation="reserve").observe(processing_time)
        INVENTORY_REQUESTS.labels(operation="reserve", status="success").inc()

        # Final audit log
        audit_data.update({
            "event": "inventory_reservation_completed",
            "status": "success",
            "processing_time_ms": processing_time * 1000,
            "results": reservation_results
        })
        logger.info(f"AUDIT: {json.dumps(audit_data)}")

        return {
            "success": True,
            "reservation_id": reservation_id,
            "correlation_id": correlation_id,
            "processing_time_ms": round(processing_time * 1000, 2),
            "items": reservation_results
        }

    except Exception as e:
        processing_time = time.time() - start_time
        INVENTORY_REQUESTS.labels(operation="reserve", status="error").inc()
        ACTIVE_RESERVATIONS.dec()

        error_audit = {
            "event": "inventory_reservation_failed",
            "reservation_id": reservation_id,
            "correlation_id": correlation_id,
            "error": str(e),
            "processing_time_ms": processing_time * 1000,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.error(f"AUDIT: {json.dumps(error_audit)}")
        raise

@app.get("/inventory/stock")
async def get_stock_levels(request: Request):
    """Get current stock levels for all products"""
    correlation_id = request.state.correlation_id

    stock_info = {}
    for product_id, data in inventory_stock.items():
        stock_info[product_id] = {
            "total_stock": data["stock"],
            "reserved": data["reserved"],
            "available": data["stock"] - data["reserved"],
            "price": data["price"]
        }

    logger.info(f"Stock levels retrieved - Correlation ID: {correlation_id}")

    return {
        "correlation_id": correlation_id,
        "timestamp": datetime.utcnow().isoformat(),
        "stock_levels": stock_info
    }

@app.get("/inventory/reservations/{reservation_id}")
async def get_reservation(reservation_id: str, request: Request):
    """Get reservation details"""
    correlation_id = request.state.correlation_id

    if reservation_id not in reservations_db:
        raise HTTPException(status_code=404, detail="Reservation not found")

    reservation = reservations_db[reservation_id]
    logger.info(f"Reservation retrieved - ID: {reservation_id}, Correlation: {correlation_id}")

    return reservation

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "inventory-service"}

if __name__ == "__main__":
    import uvicorn
    print("📦 Starting MMF Inventory Service...")
    print("📊 Metrics: http://localhost:8003/metrics")
    print("📋 API Docs: http://localhost:8003/docs")
    uvicorn.run(app, host="0.0.0.0", port=8003)
