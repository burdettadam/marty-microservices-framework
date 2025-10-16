#!/usr/bin/env python3
"""
Kafka Integration Demo for Petstore Domain
Tests the production-like Kafka+Zookeeper setup
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add the app directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.event_service import EventService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_kafka_connection():
    """Test basic Kafka connectivity"""
    logger.info("🔌 Testing Kafka connection...")

    event_service = EventService()

    try:
        await event_service.start()
        logger.info("✅ Successfully connected to Kafka")

        # Test publishing various event types
        await test_order_events(event_service)
        await test_pet_events(event_service)
        await test_payment_events(event_service)

        logger.info("✅ All event tests completed successfully")

    except Exception as e:
        logger.error(f"❌ Kafka connection failed: {e}")
        return False
    finally:
        await event_service.stop()
        logger.info("🔌 Kafka connection closed")

    return True


async def test_order_events(event_service: EventService):
    """Test order-related events"""
    logger.info("📦 Testing order events...")

    order_id = "ORDER-TEST-001"

    # Test order created event
    success = await event_service.publish_order_event(
        order_id=order_id,
        event_type="created",
        order_data={
            "customer_id": "CUSTOMER-123",
            "pet_id": "PET-456",
            "quantity": 2,
            "total_amount": 199.98
        }
    )

    if success:
        logger.info("✅ Order created event published")
    else:
        logger.error("❌ Failed to publish order created event")

    # Test order payment event
    success = await event_service.publish_order_event(
        order_id=order_id,
        event_type="payment_completed",
        order_data={
            "payment_id": "PAY-789",
            "status": "paid"
        }
    )

    if success:
        logger.info("✅ Order payment event published")
    else:
        logger.error("❌ Failed to publish order payment event")


async def test_pet_events(event_service: EventService):
    """Test pet-related events"""
    logger.info("🐕 Testing pet events...")

    pet_id = "PET-TEST-001"

    success = await event_service.publish_pet_event(
        pet_id=pet_id,
        event_type="adoption_requested",
        pet_data={
            "breed": "Golden Retriever",
            "age": 2,
            "customer_id": "CUSTOMER-123",
            "requested_at": "2024-10-15T10:30:00Z"
        }
    )

    if success:
        logger.info("✅ Pet adoption event published")
    else:
        logger.error("❌ Failed to publish pet adoption event")


async def test_payment_events(event_service: EventService):
    """Test payment-related events"""
    logger.info("💳 Testing payment events...")

    payment_id = "PAY-TEST-001"

    success = await event_service.publish_payment_event(
        payment_id=payment_id,
        event_type="processed",
        payment_data={
            "order_id": "ORDER-TEST-001",
            "amount": 199.98,
            "payment_method": "credit_card",
            "status": "completed",
            "processed_at": "2024-10-15T10:35:00Z"
        }
    )

    if success:
        logger.info("✅ Payment processed event published")
    else:
        logger.error("❌ Failed to publish payment processed event")


async def main():
    """Main demo function"""
    logger.info("🚀 Starting Kafka Integration Demo")
    logger.info("="*50)

    # Test Kafka connection and events
    success = await test_kafka_connection()

    logger.info("="*50)
    if success:
        logger.info("🎉 Demo completed successfully!")
        logger.info("📊 Check your Kafka topics for the published events:")
        logger.info("   - petstore.order.created")
        logger.info("   - petstore.order.payment_completed")
        logger.info("   - petstore.pet.adoption_requested")
        logger.info("   - petstore.payment.processed")
    else:
        logger.error("❌ Demo failed - check Kafka connectivity")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
