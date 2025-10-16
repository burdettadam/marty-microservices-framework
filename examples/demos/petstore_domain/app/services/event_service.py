"""
Event Service for Petstore Domain
Handles Kafka event streaming with production-like Kafka+Zookeeper setup
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)


class EventService:
    """Service for handling Kafka event streaming"""

    def __init__(self):
        self.kafka_brokers = os.getenv("KAFKA_BROKERS", "kafka.observability.svc.cluster.local:9092")
        self.topic_prefix = os.getenv("KAFKA_TOPIC_PREFIX", "petstore")
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._running = False

    async def start(self) -> None:
        """Initialize Kafka producer and consumer"""
        try:
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_brokers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                retry_backoff_ms=100,
                request_timeout_ms=30000,
                connections_max_idle_ms=540000,
            )
            await self.producer.start()

            logger.info(f"Kafka producer connected to {self.kafka_brokers}")
            self._running = True

        except KafkaError as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise

    async def stop(self) -> None:
        """Stop Kafka connections"""
        self._running = False

        if self.producer:
            await self.producer.stop()

        if self.consumer:
            await self.consumer.stop()

        logger.info("Kafka connections closed")

    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        key: Optional[str] = None
    ) -> bool:
        """Publish an event to Kafka"""
        if not self.producer or not self._running:
            logger.warning("Kafka producer not available")
            return False

        try:
            topic = f"{self.topic_prefix}.{event_type}"

            # Add metadata to event
            event_data = {
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data,
                "service": "petstore-domain"
            }

            # Send event
            await self.producer.send(topic, value=event_data, key=key)
            logger.info(f"Published event {event_type} to topic {topic}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")
            return False

    async def publish_order_event(self, order_id: str, event_type: str, order_data: Dict[str, Any]) -> bool:
        """Publish order-related events"""
        return await self.publish_event(
            event_type=f"order.{event_type}",
            data={
                "order_id": order_id,
                **order_data
            },
            key=order_id
        )

    async def publish_pet_event(self, pet_id: str, event_type: str, pet_data: Dict[str, Any]) -> bool:
        """Publish pet-related events"""
        return await self.publish_event(
            event_type=f"pet.{event_type}",
            data={
                "pet_id": pet_id,
                **pet_data
            },
            key=pet_id
        )

    async def publish_payment_event(self, payment_id: str, event_type: str, payment_data: Dict[str, Any]) -> bool:
        """Publish payment-related events"""
        return await self.publish_event(
            event_type=f"payment.{event_type}",
            data={
                "payment_id": payment_id,
                **payment_data
            },
            key=payment_id
        )

    def is_healthy(self) -> bool:
        """Check if Kafka connection is healthy"""
        return self._running and self.producer is not None


# Global event service instance
event_service = EventService()


async def get_event_service() -> EventService:
    """Get the global event service instance"""
    return event_service
