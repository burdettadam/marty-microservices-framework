"""
MMF Demo: Payment Service
Demonstrates payment processing with deliberate bottlenecks for performance analysis
"""
import asyncio
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
        logging.FileHandler('payment_service_audit.log')
    ]
)
logger = logging.getLogger("payment-service")

app = FastAPI(
    title="MMF Payment Service",
    description="Payment processing with performance bottlenecks for analysis",
    version="1.0.0"
)

# Prometheus Metrics
PAYMENT_REQUESTS = Counter('payment_service_requests_total', 'Total payment requests', ['status', 'operation'])
PAYMENT_PROCESSING_TIME = Histogram('payment_service_processing_seconds', 'Payment processing time', ['operation'])
ACTIVE_PAYMENTS = Gauge('payment_service_active_payments', 'Currently processing payments')
FRAUD_CHECKS = Counter('payment_service_fraud_checks_total', 'Fraud check attempts', ['result'])
BANK_API_CALLS = Counter('payment_service_bank_api_calls_total', 'Bank API calls', ['status'])

# Data Models
class PaymentRequest(BaseModel):
    customer_id: str
    amount: float

class PaymentResponse(BaseModel):
    transaction_id: str
    success: bool
    correlation_id: str
    processing_time_ms: float
    details: dict

# In-memory payment storage
payments_db = {}

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID for distributed tracing"""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id

    logger.info(f"Payment request received - Correlation ID: {correlation_id}, Path: {request.url.path}")

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

@app.post("/payments/process", response_model=PaymentResponse)
async def process_payment(payment: PaymentRequest, request: Request):
    """Process payment with deliberate performance bottlenecks"""
    start_time = time.time()
    correlation_id = request.state.correlation_id
    transaction_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"

    ACTIVE_PAYMENTS.inc()

    try:
        # Audit log: Payment processing started
        audit_data = {
            "event": "payment_processing_started",
            "transaction_id": transaction_id,
            "correlation_id": correlation_id,
            "customer_id": payment.customer_id,
            "amount": payment.amount,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"AUDIT: {json.dumps(audit_data)}")

        # Step 1: Fraud check (performance bottleneck)
        fraud_result = await perform_fraud_check(payment.customer_id, payment.amount, correlation_id)
        if not fraud_result["passed"]:
            PAYMENT_REQUESTS.labels(status="failed", operation="fraud_check").inc()
            raise HTTPException(status_code=400, detail="Payment failed fraud check")

        # Step 2: Bank API call (another bottleneck with random delays)
        bank_result = await call_bank_api(payment.amount, correlation_id)
        if not bank_result["success"]:
            PAYMENT_REQUESTS.labels(status="failed", operation="bank_api").inc()
            raise HTTPException(status_code=400, detail="Bank API declined payment")

        # Step 3: Store payment record
        payment_data = {
            "transaction_id": transaction_id,
            "correlation_id": correlation_id,
            "customer_id": payment.customer_id,
            "amount": payment.amount,
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
            "bank_reference": bank_result["reference"],
            "fraud_score": fraud_result["score"]
        }
        payments_db[transaction_id] = payment_data

        processing_time = time.time() - start_time
        PAYMENT_PROCESSING_TIME.labels(operation="process_payment").observe(processing_time)
        PAYMENT_REQUESTS.labels(status="success", operation="process_payment").inc()

        # Final audit log
        audit_data.update({
            "event": "payment_processing_completed",
            "status": "success",
            "processing_time_ms": processing_time * 1000,
            "bank_reference": bank_result["reference"],
            "fraud_score": fraud_result["score"]
        })
        logger.info(f"AUDIT: {json.dumps(audit_data)}")

        return PaymentResponse(
            transaction_id=transaction_id,
            success=True,
            correlation_id=correlation_id,
            processing_time_ms=round(processing_time * 1000, 2),
            details={
                "bank_reference": bank_result["reference"],
                "fraud_score": fraud_result["score"],
                "steps_completed": ["fraud_check", "bank_api", "record_storage"]
            }
        )

    except Exception as e:
        processing_time = time.time() - start_time
        PAYMENT_REQUESTS.labels(status="error", operation="process_payment").inc()

        # Error audit log
        error_audit = {
            "event": "payment_processing_failed",
            "transaction_id": transaction_id,
            "correlation_id": correlation_id,
            "error": str(e),
            "processing_time_ms": processing_time * 1000,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.error(f"AUDIT: {json.dumps(error_audit)}")
        raise
    finally:
        ACTIVE_PAYMENTS.dec()

async def perform_fraud_check(customer_id: str, amount: float, correlation_id: str):
    """Perform fraud check with deliberate performance bottleneck"""
    start_time = time.time()

    # Simulate complex fraud analysis (deliberate slowdown)
    # Higher amounts = longer processing time (bottleneck simulation)
    base_delay = 0.5  # Base 500ms delay
    amount_factor = min(amount / 1000.0, 5.0)  # Up to 5x multiplier for large amounts
    delay_time = base_delay + (amount_factor * 0.3)  # Additional delay based on amount

    await asyncio.sleep(delay_time)

    # Simulate fraud score calculation
    fraud_score = random.uniform(0.1, 0.9)
    passed = fraud_score < 0.8  # 80% pass rate

    processing_time = time.time() - start_time

    FRAUD_CHECKS.labels(result="passed" if passed else "failed").inc()

    audit_data = {
        "event": "fraud_check_completed",
        "correlation_id": correlation_id,
        "customer_id": customer_id,
        "amount": amount,
        "fraud_score": fraud_score,
        "passed": passed,
        "processing_time_ms": processing_time * 1000,
        "timestamp": datetime.utcnow().isoformat()
    }
    logger.info(f"AUDIT: {json.dumps(audit_data)}")

    return {
        "passed": passed,
        "score": fraud_score,
        "processing_time_ms": processing_time * 1000
    }

async def call_bank_api(amount: float, correlation_id: str):
    """Call external bank API with random delays (bottleneck simulation)"""
    start_time = time.time()

    # Simulate variable bank API response times
    # Random delays to simulate network latency and bank processing
    delay_time = random.uniform(0.2, 1.5)  # 200ms to 1.5s random delay
    await asyncio.sleep(delay_time)

    # Simulate occasional bank API failures (5% failure rate)
    success = random.random() > 0.05

    processing_time = time.time() - start_time

    BANK_API_CALLS.labels(status="success" if success else "error").inc()

    bank_reference = f"BANK-{uuid.uuid4().hex[:12].upper()}" if success else None

    audit_data = {
        "event": "bank_api_call_completed",
        "correlation_id": correlation_id,
        "amount": amount,
        "success": success,
        "bank_reference": bank_reference,
        "processing_time_ms": processing_time * 1000,
        "timestamp": datetime.utcnow().isoformat()
    }
    logger.info(f"AUDIT: {json.dumps(audit_data)}")

    return {
        "success": success,
        "reference": bank_reference,
        "processing_time_ms": processing_time * 1000
    }

@app.post("/payments/{transaction_id}/rollback")
async def rollback_payment(transaction_id: str, request: Request):
    """Rollback a payment transaction"""
    correlation_id = request.state.correlation_id

    if transaction_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment transaction not found")

    payment = payments_db[transaction_id]
    payment["status"] = "rolled_back"
    payment["rollback_time"] = datetime.utcnow().isoformat()

    audit_data = {
        "event": "payment_rollback_completed",
        "transaction_id": transaction_id,
        "correlation_id": correlation_id,
        "original_amount": payment["amount"],
        "timestamp": datetime.utcnow().isoformat()
    }
    logger.info(f"AUDIT: {json.dumps(audit_data)}")

    return {"status": "rolled_back", "transaction_id": transaction_id}

@app.get("/payments/{transaction_id}")
async def get_payment(transaction_id: str, request: Request):
    """Get payment details"""
    correlation_id = request.state.correlation_id

    if transaction_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment = payments_db[transaction_id]
    logger.info(f"Payment retrieved - Transaction ID: {transaction_id}, Correlation ID: {correlation_id}")

    return payment

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "payment-service"}

if __name__ == "__main__":
    import uvicorn
    print("💳 Starting MMF Payment Service...")
    print("📊 Metrics: http://localhost:8002/metrics")
    print("📋 API Docs: http://localhost:8002/docs")
    uvicorn.run(app, host="0.0.0.0", port=8002)
