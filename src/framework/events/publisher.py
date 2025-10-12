"""
Unified Event Publisher

Provides a unified interface for publishing audit events, notifications,
and domain events using Kafka with support for outbox pattern.
"""

import asyncio
import json
import logging
from typing import Any

from aiokafka import AIOKafkaProducer

from .config import EventConfig, EventPublisherConfig
from .exceptions import EventPublishingError, KafkaConnectionError
from .types import (
    AuditEventData,
    AuditEventType,
    DomainEventData,
    EventMetadata,
    EventPriority,
    NotificationEventData,
    NotificationEventType,
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Unified event publisher for audit events, notifications, and domain events.

    Provides a consistent interface for publishing events across all services
    in the Marty ecosystem, with support for:
    - Audit events for compliance and security
    - Notification events for user and system notifications
    - Domain events for business logic
    - Outbox pattern for transactional consistency
    - Kafka integration with retry and error handling
    """

    def __init__(
        self,
        config: EventConfig | EventPublisherConfig,
        database_session=None
    ):
        """
        Initialize the event publisher.

        Args:
            config: Event publishing configuration
            database_session: Optional database session for outbox pattern
        """
        self.config = config
        self.database_session = database_session
        self._producer: AIOKafkaProducer | None = None
        self._started = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize the Kafka producer."""
        if self._started:
            return

        async with self._lock:
            if self._started:
                return

            try:
                kafka_config = self._get_kafka_config()
                self._producer = AIOKafkaProducer(**kafka_config)
                await self._producer.start()
                self._started = True

                logger.info(
                    f"Event publisher started for service: {self.config.service_name}"
                )

            except Exception as e:
                logger.error(f"Failed to start event publisher: {e}")
                raise KafkaConnectionError(f"Failed to connect to Kafka: {e}")

    async def stop(self) -> None:
        """Stop the Kafka producer."""
        if not self._started:
            return

        async with self._lock:
            if self._producer:
                await self._producer.stop()
                self._producer = None
            self._started = False

            logger.info(
                f"Event publisher stopped for service: {self.config.service_name}"
            )

    async def publish_audit_event(
        self,
        event_type: AuditEventType,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        metadata: EventMetadata | None = None,
        **kwargs
    ) -> str:
        """
        Publish an audit event for compliance and security tracking.

        Args:
            event_type: Type of audit event
            action: Action being audited
            resource_type: Type of resource being acted upon
            resource_id: Optional ID of the resource
            metadata: Optional event metadata
            **kwargs: Additional event data

        Returns:
            Event ID
        """
        audit_data = AuditEventData(
            event_type=event_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            **kwargs
        )

        if metadata is None:
            metadata = self._create_default_metadata()

        topic = self._get_topic_name(self.config.audit_topic)

        return await self._publish_event(
            topic=topic,
            event_type=event_type.value,
            payload=audit_data.dict(),
            metadata=metadata,
            key=resource_id
        )

    async def publish_notification_event(
        self,
        event_type: NotificationEventType,
        recipient_type: str,
        recipient_ids: list[str],
        subject: str,
        message: str,
        metadata: EventMetadata | None = None,
        **kwargs
    ) -> str:
        """
        Publish a notification event for user or system notifications.

        Args:
            event_type: Type of notification event
            recipient_type: Type of recipient (user, admin, system)
            recipient_ids: List of recipient IDs
            subject: Notification subject
            message: Notification message
            metadata: Optional event metadata
            **kwargs: Additional notification data

        Returns:
            Event ID
        """
        notification_data = NotificationEventData(
            event_type=event_type,
            recipient_type=recipient_type,
            recipient_ids=recipient_ids,
            subject=subject,
            message=message,
            **kwargs
        )

        if metadata is None:
            metadata = self._create_default_metadata(priority=EventPriority.HIGH)

        topic = self._get_topic_name(self.config.notification_topic)

        return await self._publish_event(
            topic=topic,
            event_type=event_type.value,
            payload=notification_data.dict(),
            metadata=metadata,
            key=recipient_type
        )

    async def publish_domain_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        event_data: dict[str, Any],
        metadata: EventMetadata | None = None,
        **kwargs
    ) -> str:
        """
        Publish a domain event for business logic.

        Args:
            aggregate_type: Type of domain aggregate
            aggregate_id: ID of the aggregate instance
            event_type: Type of domain event
            event_data: Event payload data
            metadata: Optional event metadata
            **kwargs: Additional domain event data

        Returns:
            Event ID
        """
        domain_data = DomainEventData(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            event_data=event_data,
            **kwargs
        )

        if metadata is None:
            metadata = self._create_default_metadata()

        # Generate topic name based on pattern: {service}.{aggregate}.{event_type}
        topic_name = self.config.domain_topic_pattern.format(
            service=self.config.service_name,
            aggregate=aggregate_type.lower(),
            event_type=event_type.lower()
        )
        topic = self._get_topic_name(topic_name)

        return await self._publish_event(
            topic=topic,
            event_type=event_type,
            payload=domain_data.dict(),
            metadata=metadata,
            key=aggregate_id
        )

    async def publish_custom_event(
        self,
        topic: str,
        event_type: str,
        payload: dict[str, Any],
        metadata: EventMetadata | None = None,
        key: str | None = None
    ) -> str:
        """
        Publish a custom event to a specific topic.

        Args:
            topic: Kafka topic name (without prefix)
            event_type: Type of event
            payload: Event payload data
            metadata: Optional event metadata
            key: Optional partition key

        Returns:
            Event ID
        """
        if metadata is None:
            metadata = self._create_default_metadata()

        full_topic = self._get_topic_name(topic)

        return await self._publish_event(
            topic=full_topic,
            event_type=event_type,
            payload=payload,
            metadata=metadata,
            key=key
        )

    async def _publish_event(
        self,
        topic: str,
        event_type: str,
        payload: dict[str, Any],
        metadata: EventMetadata,
        key: str | None = None
    ) -> str:
        """
        Internal method to publish an event.

        Args:
            topic: Full Kafka topic name
            event_type: Type of event
            payload: Event payload data
            metadata: Event metadata
            key: Optional partition key

        Returns:
            Event ID
        """
        event_envelope = {
            "metadata": metadata.dict(),
            "event_type": event_type,
            "payload": payload
        }

        if self.config.use_outbox_pattern and self.database_session:
            return await self._publish_via_outbox(
                topic, event_envelope, key, metadata.event_id
            )
        else:
            return await self._publish_direct(
                topic, event_envelope, key, metadata.event_id
            )

    async def _publish_direct(
        self,
        topic: str,
        event_envelope: dict[str, Any],
        key: str | None,
        event_id: str
    ) -> str:
        """Publish event directly to Kafka."""
        await self.start()

        try:
            serialized_value = json.dumps(event_envelope, default=str).encode('utf-8')
            serialized_key = key.encode('utf-8') if key else None

            future = await self._producer.send(
                topic=topic,
                value=serialized_value,
                key=serialized_key
            )

            # Wait for the message to be sent
            record_metadata = await future

            logger.debug(
                f"Event {event_id} published to topic {topic} "
                f"(partition: {record_metadata.partition}, "
                f"offset: {record_metadata.offset})"
            )

            return event_id

        except Exception as e:
            logger.error(f"Failed to publish event {event_id}: {e}")
            raise EventPublishingError(f"Failed to publish event: {e}", event_id, e)

    async def _publish_via_outbox(
        self,
        topic: str,
        event_envelope: dict[str, Any],
        key: str | None,
        event_id: str
    ) -> str:
        """Publish event via outbox pattern."""
        try:
            # Import here to avoid circular dependencies
            from ..database.outbox import OutboxRepository

            serialized_payload = json.dumps(event_envelope, default=str).encode('utf-8')
            serialized_key = key.encode('utf-8') if key else None

            outbox = OutboxRepository(self.database_session)
            await outbox.enqueue(
                topic=topic,
                payload=serialized_payload,
                key=serialized_key,
                event_id=event_id
            )

            logger.debug(f"Event {event_id} queued in outbox for topic {topic}")
            return event_id

        except Exception as e:
            logger.error(f"Failed to queue event {event_id} in outbox: {e}")
            raise EventPublishingError(f"Failed to queue event in outbox: {e}", event_id, e)

    def _create_default_metadata(
        self,
        priority: EventPriority = EventPriority.NORMAL
    ) -> EventMetadata:
        """Create default event metadata."""
        return EventMetadata(
            service_name=self.config.service_name,
            service_version=getattr(self.config, 'service_version', '1.0.0'),
            priority=priority
        )

    def _get_topic_name(self, topic: str) -> str:
        """Get full topic name with prefix."""
        if self.config.topic_prefix:
            return f"{self.config.topic_prefix}.{topic}"
        return topic

    def _get_kafka_config(self) -> dict[str, Any]:
        """Get Kafka producer configuration."""
        if hasattr(self.config, 'get_kafka_config'):
            return self.config.get_kafka_config()

        # Fallback for EventConfig
        config = {
            "bootstrap_servers": self.config.kafka_brokers,
            "security_protocol": self.config.kafka_security_protocol,
            "acks": getattr(self.config, 'producer_acks', 'all'),
            "retries": getattr(self.config, 'producer_retries', 3),
            "request_timeout_ms": getattr(self.config, 'producer_timeout_ms', 30000),
            "compression_type": getattr(self.config, 'producer_compression_type', 'snappy'),
            "value_serializer": lambda v: v,  # We handle serialization ourselves
            "key_serializer": lambda k: k,    # We handle serialization ourselves
        }

        if self.config.kafka_sasl_mechanism:
            config.update({
                "sasl_mechanism": self.config.kafka_sasl_mechanism,
                "sasl_plain_username": self.config.kafka_sasl_username,
                "sasl_plain_password": self.config.kafka_sasl_password,
            })

        return config


# Global event publisher instance
_event_publisher: EventPublisher | None = None


def get_event_publisher(
    config: EventConfig | EventPublisherConfig | None = None,
    database_session=None
) -> EventPublisher:
    """
    Get or create the global event publisher instance.

    Args:
        config: Optional configuration (defaults to environment-based config)
        database_session: Optional database session for outbox pattern

    Returns:
        EventPublisher instance
    """
    global _event_publisher

    if _event_publisher is None or config is not None:
        if config is None:
            config = EventConfig.from_env()
        _event_publisher = EventPublisher(config, database_session)

    # Update database session if provided
    if database_session is not None:
        _event_publisher.database_session = database_session

    return _event_publisher
