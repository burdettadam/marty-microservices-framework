"""
Kafka Event Bus Infrastructure for Marty Microservices Framework

Provides enterprise-grade event streaming capabilities with Kafka integration,
based on patterns from the main Marty project.
"""

import asyncio
import builtins
import json
import logging
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EventMessage(BaseModel):
    """Standard event message format for Kafka events"""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    service_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: builtins.dict[str, Any]
    correlation_id: str | None = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class KafkaConfig(BaseModel):
    """Kafka configuration settings"""

    bootstrap_servers: builtins.list[str] = ["localhost:9092"]
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str | None = None
    sasl_plain_username: str | None = None
    sasl_plain_password: str | None = None
    consumer_group_id: str = "marty-microservice"
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True
    max_poll_records: int = 500
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 3000


class EventBus:
    """
    Kafka-based event bus for microservice communication

    Provides reliable event streaming with support for:
    - Async event publishing
    - Event consumption with handlers
    - Dead letter queue handling
    - Automatic retries and error handling
    """

    def __init__(self, config: KafkaConfig, service_name: str):
        self.config = config
        self.service_name = service_name
        self.producer: AIOKafkaProducer | None = None
        self.consumers: builtins.dict[str, AIOKafkaConsumer] = {}
        self.event_handlers: builtins.dict[str, builtins.list[Callable]] = {}
        self._running = False

    async def start(self) -> None:
        """Initialize Kafka producer and consumers"""
        try:
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                security_protocol=self.config.security_protocol,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: str(k).encode("utf-8") if k else None,
                retry_backoff_ms=100,
                request_timeout_ms=30000,
                max_request_size=1048576,  # 1MB
                compression_type="snappy",
            )
            await self.producer.start()

            self._running = True
            logger.info(f"Event bus started for service: {self.service_name}")

        except Exception as e:
            logger.error(f"Failed to start event bus: {e}")
            raise

    async def stop(self) -> None:
        """Cleanup Kafka connections"""
        self._running = False

        if self.producer:
            await self.producer.stop()

        for consumer in self.consumers.values():
            await consumer.stop()

        logger.info(f"Event bus stopped for service: {self.service_name}")

    async def publish_event(
        self,
        topic: str,
        event_type: str,
        payload: builtins.dict[str, Any],
        key: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """
        Publish an event to a Kafka topic

        Args:
            topic: Kafka topic name
            event_type: Type of event being published
            payload: Event data
            key: Optional partition key
            correlation_id: Optional correlation ID for request tracing
        """
        if not self.producer or not self._running:
            raise RuntimeError("Event bus not started")

        event = EventMessage(
            event_type=event_type,
            service_name=self.service_name,
            payload=payload,
            correlation_id=correlation_id,
        )

        try:
            await self.producer.send_and_wait(topic, value=event.dict(), key=key)

            logger.debug(
                f"Published event {event.event_id} to topic {topic}",
                extra={
                    "event_id": event.event_id,
                    "event_type": event_type,
                    "topic": topic,
                    "service_name": self.service_name,
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to publish event to topic {topic}: {e}",
                extra={"event_type": event_type, "topic": topic, "error": str(e)},
            )
            raise

    def register_handler(
        self, topic: str, handler: Callable[[EventMessage], None]
    ) -> None:
        """
        Register an event handler for a specific topic

        Args:
            topic: Kafka topic to listen to
            handler: Async function to handle events
        """
        if topic not in self.event_handlers:
            self.event_handlers[topic] = []

        self.event_handlers[topic].append(handler)
        logger.info(f"Registered handler for topic: {topic}")

    async def start_consumer(self, topics: builtins.list[str]) -> None:
        """
        Start consuming events from specified topics

        Args:
            topics: List of topics to consume from
        """
        if not self._running:
            raise RuntimeError("Event bus not started")

        for topic in topics:
            if topic in self.consumers:
                logger.warning(f"Consumer for topic {topic} already exists")
                continue

            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=f"{self.config.consumer_group_id}-{self.service_name}",
                auto_offset_reset=self.config.auto_offset_reset,
                enable_auto_commit=self.config.enable_auto_commit,
                max_poll_records=self.config.max_poll_records,
                session_timeout_ms=self.config.session_timeout_ms,
                heartbeat_interval_ms=self.config.heartbeat_interval_ms,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )

            await consumer.start()
            self.consumers[topic] = consumer

            # Start consuming in background task
            asyncio.create_task(self._consume_messages(topic, consumer))

            logger.info(f"Started consumer for topic: {topic}")

    async def _consume_messages(self, topic: str, consumer: AIOKafkaConsumer) -> None:
        """Background task to consume messages from a topic"""
        try:
            async for message in consumer:
                await self._handle_message(topic, message)
        except asyncio.CancelledError:
            logger.info(f"Consumer for topic {topic} cancelled")
        except Exception as e:
            logger.error(f"Error consuming from topic {topic}: {e}")

    async def _handle_message(self, topic: str, message) -> None:
        """Process a received message"""
        try:
            event_data = message.value
            event = EventMessage(**event_data)

            logger.debug(
                f"Received event {event.event_id} from topic {topic}",
                extra={
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "topic": topic,
                    "source_service": event.service_name,
                },
            )

            # Call registered handlers
            handlers = self.event_handlers.get(topic, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(
                        f"Handler error for event {event.event_id}: {e}",
                        extra={
                            "event_id": event.event_id,
                            "handler": handler.__name__,
                            "error": str(e),
                        },
                    )

        except Exception as e:
            logger.error(f"Failed to process message from topic {topic}: {e}")


@asynccontextmanager
async def event_bus_context(config: KafkaConfig, service_name: str):
    """Context manager for event bus lifecycle"""
    bus = EventBus(config, service_name)
    try:
        await bus.start()
        yield bus
    finally:
        await bus.stop()


# Convenience functions for common event patterns
async def publish_service_event(
    event_bus: EventBus,
    event_type: str,
    data: builtins.dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Publish a service-level event"""
    topic = f"service.{event_bus.service_name}.events"
    await event_bus.publish_event(
        topic=topic, event_type=event_type, payload=data, correlation_id=correlation_id
    )


async def publish_domain_event(
    event_bus: EventBus,
    domain: str,
    event_type: str,
    data: builtins.dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Publish a domain-specific event"""
    topic = f"domain.{domain}.events"
    await event_bus.publish_event(
        topic=topic, event_type=event_type, payload=data, correlation_id=correlation_id
    )
