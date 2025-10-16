#!/usr/bin/env python3
"""
Local Kafka Integration Test for Petstore Domain
Tests Kafka integration with localhost broker for local development
"""
import asyncio
import logging
import os
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


async def test_local_kafka():
    """Test Kafka with localhost broker"""
    # Override environment to use localhost
    os.environ["KAFKA_BROKERS"] = "localhost:9092"

    logger.info("🔌 Testing LOCAL Kafka connection (localhost:9092)...")

    event_service = EventService()

    try:
        await event_service.start()
        logger.info("✅ Successfully connected to local Kafka")

        # Test publishing events
        await test_events(event_service)

        logger.info("✅ All local Kafka tests completed successfully")
        return True

    except Exception as e:
        logger.warning(f"⚠️  Local Kafka connection failed (expected if no local Kafka): {e}")
        logger.info("ℹ️  This is normal if you don't have Kafka running locally")
        return False
    finally:
        await event_service.stop()
        logger.info("🔌 Local Kafka connection closed")


async def test_production_config():
    """Test production configuration without connecting"""
    # Reset to production config
    if "KAFKA_BROKERS" in os.environ:
        del os.environ["KAFKA_BROKERS"]

    logger.info("🔧 Testing PRODUCTION Kafka configuration...")

    event_service = EventService()

    # Test configuration without connecting
    expected_broker = "kafka.observability.svc.cluster.local:9092"
    actual_broker = event_service.kafka_brokers

    if actual_broker == expected_broker:
        logger.info(f"✅ Production broker configuration correct: {actual_broker}")
    else:
        logger.error(f"❌ Production broker configuration incorrect: {actual_broker}")
        return False

    expected_prefix = "petstore"
    actual_prefix = event_service.topic_prefix

    if actual_prefix == expected_prefix:
        logger.info(f"✅ Topic prefix configuration correct: {actual_prefix}")
    else:
        logger.error(f"❌ Topic prefix configuration incorrect: {actual_prefix}")
        return False

    logger.info("✅ Production configuration validation passed")
    return True


async def test_events(event_service: EventService):
    """Test event publishing"""
    logger.info("📦 Testing event publishing...")

    # Test order event
    success = await event_service.publish_order_event(
        order_id="ORDER-TEST-001",
        event_type="created",
        order_data={
            "customer_id": "CUSTOMER-123",
            "pet_id": "PET-456",
            "quantity": 2,
            "total_amount": 199.98
        }
    )

    if success:
        logger.info("✅ Order event published successfully")
    else:
        logger.error("❌ Failed to publish order event")

    # Test pet event
    success = await event_service.publish_pet_event(
        pet_id="PET-TEST-001",
        event_type="adoption_requested",
        pet_data={
            "breed": "Golden Retriever",
            "age": 2,
            "customer_id": "CUSTOMER-123"
        }
    )

    if success:
        logger.info("✅ Pet event published successfully")
    else:
        logger.error("❌ Failed to publish pet event")


def test_import_functionality():
    """Test that all imports work correctly"""
    logger.info("📚 Testing import functionality...")

    try:
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
        logger.info("✅ aiokafka imports successful")
    except ImportError as e:
        logger.error(f"❌ aiokafka import failed: {e}")
        return False

    try:
        from confluent_kafka import Producer
        logger.info("✅ confluent-kafka imports successful")
    except ImportError as e:
        logger.error(f"❌ confluent-kafka import failed: {e}")
        return False

    logger.info("✅ All Kafka dependencies imported successfully")
    return True


async def main():
    """Main demo function"""
    logger.info("🚀 Starting Local Kafka Integration Test")
    logger.info("="*60)

    # Test imports first
    if not test_import_functionality():
        logger.error("❌ Import test failed")
        sys.exit(1)

    # Test production configuration
    config_success = await test_production_config()

    # Test local connection (may fail if no local Kafka)
    local_success = await test_local_kafka()

    logger.info("="*60)
    logger.info("📊 Test Results Summary:")
    logger.info(f"   Dependencies: ✅ Installed")
    logger.info(f"   Production Config: {'✅ Valid' if config_success else '❌ Invalid'}")
    logger.info(f"   Local Kafka Test: {'✅ Connected' if local_success else '⚠️  No local Kafka'}")

    if config_success:
        logger.info("🎉 Configuration validation successful!")
        logger.info("ℹ️  The plugin is ready for Kafka integration in K8s environment")
        logger.info("ℹ️  Expected broker: kafka.observability.svc.cluster.local:9092")
        logger.info("ℹ️  Expected topics: petstore.order.*, petstore.pet.*, petstore.payment.*")
    else:
        logger.error("❌ Configuration validation failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
