"""
MMF Demo: Order Service
Demonstrates distributed tracing, audit logging, and performance monitoring
"""
import json
import logging
import sys
import time
import uuid
from datetime import datetime

import aiohttp
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

# Configure structured logging for audit trail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('order_service_audit.log')
    ]
)
logger = logging.getLogger("order-service")

app = FastAPI(
    title="MMF Order Service",
    description="Enterprise order processing with full traceability",
    version="1.0.0"
)

# Prometheus Metrics
ORDER_REQUESTS = Counter('order_service_requests_total', 'Total order requests', ['status', 'operation'])
ORDER_PROCESSING_TIME = Histogram('order_service_processing_seconds', 'Order processing time', ['operation'])
ACTIVE_ORDERS = Gauge('order_service_active_orders', 'Currently processing orders')
PAYMENT_REQUESTS = Counter('order_service_payment_requests_total', 'Payment service calls', ['status'])
INVENTORY_REQUESTS = Counter('order_service_inventory_requests_total', 'Inventory service calls', ['status'])

# Data Models
class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class OrderRequest(BaseModel):
    customer_id: str
    items: list[OrderItem]
    shipping_address: str

class OrderResponse(BaseModel):
    order_id: str
    correlation_id: str
    status: str
    total_amount: float
    processing_time_ms: float
    trace_info: dict

# In-memory order storage (in production: database)
orders_db = {}

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID for distributed tracing"""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id

    # Add to logs
    logger.info(f"Request received - Correlation ID: {correlation_id}, Path: {request.url.path}")

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

@app.post("/orders", response_model=OrderResponse)
async def create_order(order: OrderRequest, request: Request):
    """Create a new order with full transaction tracing"""
    start_time = time.time()
    correlation_id = request.state.correlation_id
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    ACTIVE_ORDERS.inc()

    try:
        # Audit log: Order creation started
        audit_data = {
            "event": "order_creation_started",
            "order_id": order_id,
            "correlation_id": correlation_id,
            "customer_id": order.customer_id,
            "item_count": len(order.items),
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"AUDIT: {json.dumps(audit_data)}")

        # Calculate total amount
        total_amount = sum(item.quantity * item.price for item in order.items)

        # Step 1: Check inventory availability
        inventory_result = await check_inventory(order.items, correlation_id)
        if not inventory_result["available"]:
            ORDER_REQUESTS.labels(status="failed", operation="inventory_check").inc()
            raise HTTPException(status_code=400, detail="Insufficient inventory")

        # Step 2: Process payment
        payment_result = await process_payment(order.customer_id, total_amount, correlation_id)
        if not payment_result["success"]:
            ORDER_REQUESTS.labels(status="failed", operation="payment").inc()
            raise HTTPException(status_code=400, detail="Payment failed")

        # Step 3: Reserve inventory
        reservation_result = await reserve_inventory(order.items, correlation_id)
        if not reservation_result["success"]:
            ORDER_REQUESTS.labels(status="failed", operation="inventory_reserve").inc()
            # Rollback payment
            await rollback_payment(payment_result["transaction_id"], correlation_id)
            raise HTTPException(status_code=400, detail="Inventory reservation failed")

        # Store order
        order_data = {
            "order_id": order_id,
            "correlation_id": correlation_id,
            "customer_id": order.customer_id,
            "items": [item.dict() for item in order.items],
            "total_amount": total_amount,
            "status": "confirmed",
            "created_at": datetime.utcnow().isoformat(),
            "payment_id": payment_result["transaction_id"],
            "reservation_id": reservation_result["reservation_id"]
        }
        orders_db[order_id] = order_data

        processing_time = time.time() - start_time
        ORDER_PROCESSING_TIME.labels(operation="create_order").observe(processing_time)
        ORDER_REQUESTS.labels(status="success", operation="create_order").inc()

        # Final audit log
        audit_data.update({
            "event": "order_creation_completed",
            "status": "success",
            "total_amount": total_amount,
            "processing_time_ms": processing_time * 1000,
            "payment_id": payment_result["transaction_id"],
            "reservation_id": reservation_result["reservation_id"]
        })
        logger.info(f"AUDIT: {json.dumps(audit_data)}")

        return OrderResponse(
            order_id=order_id,
            correlation_id=correlation_id,
            status="confirmed",
            total_amount=total_amount,
            processing_time_ms=round(processing_time * 1000, 2),
            trace_info={
                "payment_id": payment_result["transaction_id"],
                "reservation_id": reservation_result["reservation_id"],
                "steps_completed": ["inventory_check", "payment", "inventory_reserve"]
            }
        )

    except Exception as e:
        processing_time = time.time() - start_time
        ORDER_REQUESTS.labels(status="error", operation="create_order").inc()

        # Error audit log
        error_audit = {
            "event": "order_creation_failed",
            "order_id": order_id,
            "correlation_id": correlation_id,
            "error": str(e),
            "processing_time_ms": processing_time * 1000,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.error(f"AUDIT: {json.dumps(error_audit)}")
        raise
    finally:
        ACTIVE_ORDERS.dec()

async def check_inventory(items: list[OrderItem], correlation_id: str):
    """Call inventory service to check availability"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"items": [item.dict() for item in items]}
            headers = {"X-Correlation-ID": correlation_id}

            async with session.post(
                "http://localhost:8003/inventory/check",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                result = await response.json()
                INVENTORY_REQUESTS.labels(status="success").inc()
                return result
    except Exception as e:
        INVENTORY_REQUESTS.labels(status="error").inc()
        logger.error(f"Inventory check failed - Correlation ID: {correlation_id}, Error: {str(e)}")
        raise HTTPException(status_code=503, detail="Inventory service unavailable")

async def process_payment(customer_id: str, amount: float, correlation_id: str):
    """Call payment service to process payment"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"customer_id": customer_id, "amount": amount}
            headers = {"X-Correlation-ID": correlation_id}

            async with session.post(
                "http://localhost:8002/payments/process",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    PAYMENT_REQUESTS.labels(status="success").inc()
                    return result
                else:
                    # Payment failed (fraud check, bank decline, etc.)
                    error_text = await response.text()
                    PAYMENT_REQUESTS.labels(status="business_error").inc()
                    return {"success": False, "error": f"{response.status}: {error_text}"}
    except Exception as e:
        PAYMENT_REQUESTS.labels(status="error").inc()
        logger.error(f"Payment processing failed - Correlation ID: {correlation_id}, Error: {str(e)}")
        raise HTTPException(status_code=503, detail="Payment service unavailable")

async def reserve_inventory(items: list[OrderItem], correlation_id: str):
    """Reserve inventory items"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"items": [item.dict() for item in items]}
            headers = {"X-Correlation-ID": correlation_id}

            async with session.post(
                "http://localhost:8003/inventory/reserve",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                result = await response.json()
                return result
    except Exception as e:
        logger.error(f"Inventory reservation failed - Correlation ID: {correlation_id}, Error: {str(e)}")
        raise HTTPException(status_code=503, detail="Inventory reservation failed")

async def rollback_payment(transaction_id: str, correlation_id: str):
    """Rollback payment in case of failure"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"X-Correlation-ID": correlation_id}
            async with session.post(
                f"http://localhost:8002/payments/{transaction_id}/rollback",
                headers=headers
            ):
                logger.info(f"Payment rollback completed - Transaction: {transaction_id}, Correlation: {correlation_id}")
    except Exception as e:
        logger.error(f"Payment rollback failed - Transaction: {transaction_id}, Error: {str(e)}")

@app.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    """Get order details with trace information"""
    correlation_id = request.state.correlation_id

    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")

    order = orders_db[order_id]
    logger.info(f"Order retrieved - Order ID: {order_id}, Correlation ID: {correlation_id}")

    return order

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "order-service"}

if __name__ == "__main__":
    import uvicorn
    print("🛒 Starting MMF Order Service...")
    print("📊 Metrics: http://localhost:8001/metrics")
    print("📋 API Docs: http://localhost:8001/docs")
    uvicorn.run(app, host="0.0.0.0", port=8001)
