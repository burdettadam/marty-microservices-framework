"""
Enhanced Petstore Domain Routes with Outbox Pattern

This module demonstrates the integration of the transactional outbox pattern
in the petstore domain API. All business operations that generate events
use the outbox pattern to ensure reliable event publishing.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from ..services.outbox_event_service import outbox_event_service

logger = logging.getLogger(__name__)

# Create router for outbox-enhanced endpoints
router = APIRouter(prefix="/petstore-outbox", tags=["petstore-outbox"])


class CreatePetRequest(BaseModel):
    """Request model for creating a pet"""
    name: str
    species: str
    breed: str | None = None
    age: int | None = None
    price: float
    category: str | None = None
    description: str | None = None
    correlation_id: str | None = None


class UpdatePetRequest(BaseModel):
    """Request model for updating a pet"""
    name: str | None = None
    price: float | None = None
    category: str | None = None
    description: str | None = None
    correlation_id: str | None = None


class CreateOrderRequest(BaseModel):
    """Request model for creating an order"""
    customer_id: str
    pet_id: str
    quantity: int = 1
    special_instructions: str | None = None
    correlation_id: str | None = None


@router.post("/pets")
async def create_pet_with_outbox(request: CreatePetRequest):
    """Create a new pet using transactional outbox pattern"""
    correlation_id = request.correlation_id or str(uuid.uuid4())
    pet_id = str(uuid.uuid4())

    logger.info(f"Creating pet with outbox pattern - pet_id: {pet_id}, correlation_id: {correlation_id}")

    try:
        # Simulate business logic within a transaction
        async with outbox_event_service.get_session() as session:
            # In a real implementation, you would save the pet to the database here
            # For demo purposes, we'll just simulate the save operation

            pet_data = {
                "name": request.name,
                "species": request.species,
                "breed": request.breed,
                "age": request.age,
                "price": request.price,
                "category": request.category,
                "description": request.description,
                "status": "available"
            }

            # Publish event using outbox pattern
            event_id = await outbox_event_service.publish_pet_event(
                session=session,
                pet_id=pet_id,
                event_type="created",
                pet_data=pet_data,
                correlation_id=correlation_id
            )

            # The session.commit() happens automatically in the context manager

        logger.info(f"Pet created successfully - pet_id: {pet_id}, event_id: {event_id}")

        return {
            "pet_id": pet_id,
            "event_id": event_id,
            "status": "created",
            "message": "Pet created successfully with outbox event",
            "correlation_id": correlation_id,
            "created_at": datetime.utcnow().isoformat(),
            "outbox_pattern": "enabled"
        }

    except Exception as e:
        logger.error(f"Failed to create pet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create pet: {str(e)}")


@router.put("/pets/{pet_id}")
async def update_pet_with_outbox(pet_id: str, request: UpdatePetRequest):
    """Update a pet using transactional outbox pattern"""
    correlation_id = request.correlation_id or str(uuid.uuid4())

    logger.info(f"Updating pet with outbox pattern - pet_id: {pet_id}, correlation_id: {correlation_id}")

    try:
        async with outbox_event_service.get_session() as session:
            # Simulate getting existing pet and updating it
            update_data = {}
            if request.name is not None:
                update_data["name"] = request.name
            if request.price is not None:
                update_data["price"] = request.price
            if request.category is not None:
                update_data["category"] = request.category
            if request.description is not None:
                update_data["description"] = request.description

            # Publish event using outbox pattern
            event_id = await outbox_event_service.publish_pet_event(
                session=session,
                pet_id=pet_id,
                event_type="updated",
                pet_data=update_data,
                correlation_id=correlation_id
            )

        logger.info(f"Pet updated successfully - pet_id: {pet_id}, event_id: {event_id}")

        return {
            "pet_id": pet_id,
            "event_id": event_id,
            "status": "updated",
            "message": "Pet updated successfully with outbox event",
            "correlation_id": correlation_id,
            "updated_at": datetime.utcnow().isoformat(),
            "outbox_pattern": "enabled"
        }

    except Exception as e:
        logger.error(f"Failed to update pet: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update pet: {str(e)}")


@router.post("/orders")
async def create_order_with_outbox(request: CreateOrderRequest):
    """Create an order using transactional outbox pattern"""
    correlation_id = request.correlation_id or str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    logger.info(f"Creating order with outbox pattern - order_id: {order_id}, correlation_id: {correlation_id}")

    try:
        async with outbox_event_service.get_session() as session:
            # Simulate order creation business logic
            order_data = {
                "customer_id": request.customer_id,
                "pet_id": request.pet_id,
                "quantity": request.quantity,
                "special_instructions": request.special_instructions,
                "status": "pending",
                "total_amount": 0  # Would be calculated from pet price
            }

            # Publish order created event
            event_id = await outbox_event_service.publish_order_event(
                session=session,
                order_id=order_id,
                event_type="created",
                order_data=order_data,
                correlation_id=correlation_id
            )

        logger.info(f"Order created successfully - order_id: {order_id}, event_id: {event_id}")

        return {
            "order_id": order_id,
            "event_id": event_id,
            "status": "pending",
            "message": "Order created successfully with outbox event",
            "correlation_id": correlation_id,
            "created_at": datetime.utcnow().isoformat(),
            "outbox_pattern": "enabled",
            "next_steps": [
                "Order will be processed asynchronously",
                "Events will be published to Kafka via outbox pattern",
                "Check outbox metrics at /petstore-outbox/metrics"
            ]
        }

    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


@router.post("/users/{user_id}/register")
async def register_user_with_outbox(user_id: str, user_data: dict[str, Any]):
    """Register a user using transactional outbox pattern"""
    correlation_id = user_data.get("correlation_id", str(uuid.uuid4()))

    logger.info(f"Registering user with outbox pattern - user_id: {user_id}, correlation_id: {correlation_id}")

    try:
        async with outbox_event_service.get_session() as session:
            # Simulate user registration business logic
            registration_data = {
                **user_data,
                "status": "registered",
                "registration_date": datetime.utcnow().isoformat()
            }

            # Publish user registered event
            event_id = await outbox_event_service.publish_user_event(
                session=session,
                user_id=user_id,
                event_type="registered",
                user_data=registration_data,
                correlation_id=correlation_id
            )

        logger.info(f"User registered successfully - user_id: {user_id}, event_id: {event_id}")

        return {
            "user_id": user_id,
            "event_id": event_id,
            "status": "registered",
            "message": "User registered successfully with outbox event",
            "correlation_id": correlation_id,
            "registered_at": datetime.utcnow().isoformat(),
            "outbox_pattern": "enabled"
        }

    except Exception as e:
        logger.error(f"Failed to register user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")


@router.get("/metrics")
async def get_outbox_metrics():
    """Get outbox processing metrics"""
    try:
        metrics = await outbox_event_service.get_outbox_metrics()

        return {
            "outbox_metrics": metrics,
            "service_status": "running" if metrics.get("running") else "stopped",
            "kafka_status": "connected" if metrics.get("kafka_connected") else "disconnected",
            "timestamp": datetime.utcnow().isoformat(),
            "description": {
                "pending_events": "Number of events waiting to be processed",
                "failed_events": "Number of events that failed after max retries",
                "processed_today": "Number of events successfully processed today"
            }
        }

    except Exception as e:
        logger.error(f"Failed to get outbox metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/health")
async def outbox_health_check():
    """Health check for outbox pattern implementation"""
    try:
        metrics = await outbox_event_service.get_outbox_metrics()

        is_healthy = (
            metrics.get("running", False) and
            metrics.get("kafka_connected", False) and
            metrics.get("failed_events", 0) < 100  # Less than 100 failed events
        )

        status = "healthy" if is_healthy else "unhealthy"

        return {
            "status": status,
            "outbox_service": "running" if metrics.get("running") else "stopped",
            "kafka_connection": "connected" if metrics.get("kafka_connected") else "disconnected",
            "pending_events": metrics.get("pending_events", 0),
            "failed_events": metrics.get("failed_events", 0),
            "timestamp": datetime.utcnow().isoformat(),
            "pattern": "transactional_outbox",
            "reliability": "ACID_compliant"
        }

    except Exception as e:
        logger.error(f"Outbox health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/demo-info")
async def get_outbox_demo_info():
    """Get information about the outbox pattern demo"""
    return {
        "demo_name": "Transactional Outbox Pattern Demo",
        "description": "Demonstrates reliable event publishing with ACID guarantees",
        "pattern": "transactional_outbox",
        "benefits": [
            "ACID compliance for business data and events",
            "No lost events due to system failures",
            "Exactly-once delivery semantics",
            "Decoupling of business logic from message publishing",
            "Retry and dead letter queue handling"
        ],
        "endpoints": {
            "create_pet": "POST /petstore-outbox/pets",
            "update_pet": "PUT /petstore-outbox/pets/{pet_id}",
            "create_order": "POST /petstore-outbox/orders",
            "register_user": "POST /petstore-outbox/users/{user_id}/register",
            "metrics": "GET /petstore-outbox/metrics",
            "health": "GET /petstore-outbox/health"
        },
        "how_it_works": [
            "1. Business operation starts database transaction",
            "2. Business data is saved to database",
            "3. Event is saved to outbox table in same transaction",
            "4. Transaction commits atomically",
            "5. Background processor reads outbox events",
            "6. Events are published to Kafka",
            "7. Processed events are marked as completed"
        ],
        "database_requirements": {
            "outbox_table": "outbox_events",
            "columns": ["id", "aggregate_id", "event_type", "event_data", "topic", "created_at", "processed_at", "retry_count"],
            "indexes": ["aggregate_id", "created_at", "is_processed"]
        },
        "configuration": {
            "database_url": "Required - PostgreSQL connection string",
            "kafka_brokers": "Required - Kafka broker endpoints",
            "batch_size": "Optional - Events per batch (default: 100)",
            "polling_interval": "Optional - Polling interval in seconds (default: 1.0)",
            "max_retries": "Optional - Max retry attempts (default: 5)"
        }
    }
