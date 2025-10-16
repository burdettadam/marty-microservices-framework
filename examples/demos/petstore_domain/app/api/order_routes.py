"""
Simple order processing routes that demonstrate Kafka event publishing
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.event_service import event_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderRequest(BaseModel):
    pet_id: str
    customer_id: str
    quantity: int = 1
    special_instructions: str = ""


class OrderResponse(BaseModel):
    order_id: str
    status: str
    message: str
    events_published: bool
    timestamp: str


@router.post("/", response_model=OrderResponse)
async def create_order(order_request: OrderRequest):
    """Create a new pet order and publish events to Kafka"""
    order_id = f"ORDER-{uuid.uuid4().hex[:8].upper()}"

    try:
        # Create order (simplified - in real implementation this would save to database)
        order_data = {
            "order_id": order_id,
            "pet_id": order_request.pet_id,
            "customer_id": order_request.customer_id,
            "quantity": order_request.quantity,
            "special_instructions": order_request.special_instructions,
            "status": "created",
            "total_amount": 99.99 * order_request.quantity  # Simplified pricing
        }

        # Publish order created event
        events_published = await event_service.publish_order_event(
            order_id=order_id,
            event_type="created",
            order_data=order_data
        )

        logger.info(f"Order {order_id} created successfully, events published: {events_published}")

        return OrderResponse(
            order_id=order_id,
            status="created",
            message="Order created successfully",
            events_published=events_published,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


@router.post("/{order_id}/payment", response_model=OrderResponse)
async def process_payment(order_id: str, payment_data: Dict[str, Any]):
    """Process payment for an order and publish payment events"""

    try:
        payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"

        # Simulate payment processing
        payment_result = {
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": payment_data.get("amount", 99.99),
            "payment_method": payment_data.get("method", "credit_card"),
            "status": "completed"
        }

        # Publish payment events
        payment_event_published = await event_service.publish_payment_event(
            payment_id=payment_id,
            event_type="processed",
            payment_data=payment_result
        )

        # Publish order updated event
        order_event_published = await event_service.publish_order_event(
            order_id=order_id,
            event_type="payment_completed",
            order_data={"payment_id": payment_id, "status": "paid"}
        )

        events_published = payment_event_published and order_event_published

        logger.info(f"Payment {payment_id} processed for order {order_id}, events published: {events_published}")

        return OrderResponse(
            order_id=order_id,
            status="payment_completed",
            message="Payment processed successfully",
            events_published=events_published,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to process payment for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process payment: {str(e)}")


@router.get("/events/health")
async def get_kafka_health():
    """Check Kafka event service health"""
    return {
        "kafka_connected": event_service.is_healthy(),
        "brokers": event_service.kafka_brokers,
        "topic_prefix": event_service.topic_prefix,
        "timestamp": datetime.utcnow().isoformat()
    }
