"""
Outbox Pattern Implementation

Provides transactional outbox pattern for reliable event publishing.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

Base = declarative_base()


class OutboxEvent(Base):
    """Outbox event model for transactional event publishing."""

    __tablename__ = "event_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(255), nullable=False, unique=True)
    topic = Column(String(255), nullable=False)
    payload = Column(LargeBinary, nullable=False)
    key = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)


class OutboxRepository:
    """Repository for managing outbox events."""

    def __init__(self, session: Session):
        """
        Initialize the outbox repository.

        Args:
            session: Database session
        """
        self.session = session

    async def enqueue(
        self,
        topic: str,
        payload: bytes,
        key: bytes | None = None,
        event_id: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """
        Enqueue an event in the outbox.

        Args:
            topic: Kafka topic name
            payload: Serialized event payload
            key: Optional partition key
            event_id: Optional event ID (auto-generated if not provided)
            max_retries: Maximum number of retry attempts

        Returns:
            Event ID
        """
        if event_id is None:
            import uuid

            event_id = str(uuid.uuid4())

        outbox_event = OutboxEvent(
            event_id=event_id, topic=topic, payload=payload, key=key, max_retries=max_retries
        )

        self.session.add(outbox_event)
        # Note: Session commit should be handled by the calling transaction

        logger.debug(f"Enqueued event {event_id} in outbox for topic {topic}")
        return event_id

    def get_pending_events(self, limit: int = 100) -> list[OutboxEvent]:
        """
        Get pending events that haven't been processed.

        Args:
            limit: Maximum number of events to retrieve

        Returns:
            List of pending outbox events
        """
        return (
            self.session.query(OutboxEvent)
            .filter(OutboxEvent.processed_at.is_(None))
            .filter(OutboxEvent.retry_count < OutboxEvent.max_retries)
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .all()
        )

    def mark_processed(self, event_id: str) -> None:
        """
        Mark an event as successfully processed.

        Args:
            event_id: Event ID to mark as processed
        """
        event = self.session.query(OutboxEvent).filter_by(event_id=event_id).first()
        if event:
            event.processed_at = datetime.now(timezone.utc)
            self.session.commit()
            logger.debug(f"Marked event {event_id} as processed")
        else:
            logger.warning(f"Event {event_id} not found in outbox")

    def mark_failed(self, event_id: str, error_message: str) -> None:
        """
        Mark an event as failed and increment retry count.

        Args:
            event_id: Event ID to mark as failed
            error_message: Error message describing the failure
        """
        event = self.session.query(OutboxEvent).filter_by(event_id=event_id).first()
        if event:
            event.retry_count += 1
            event.error_message = error_message

            if event.retry_count >= event.max_retries:
                logger.error(
                    f"Event {event_id} exceeded max retries ({event.max_retries}), "
                    f"error: {error_message}"
                )
            else:
                logger.warning(
                    f"Event {event_id} failed (retry {event.retry_count}/{event.max_retries}), "
                    f"error: {error_message}"
                )

            self.session.commit()
        else:
            logger.warning(f"Event {event_id} not found in outbox")

    def get_failed_events(self, limit: int = 100) -> list[OutboxEvent]:
        """
        Get events that have exceeded max retries.

        Args:
            limit: Maximum number of events to retrieve

        Returns:
            List of failed outbox events
        """
        return (
            self.session.query(OutboxEvent)
            .filter(OutboxEvent.processed_at.is_(None))
            .filter(OutboxEvent.retry_count >= OutboxEvent.max_retries)
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .all()
        )

    def cleanup_processed_events(self, older_than_days: int = 7) -> int:
        """
        Clean up processed events older than specified days.

        Args:
            older_than_days: Delete processed events older than this many days

        Returns:
            Number of events deleted
        """
        cutoff_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=older_than_days)

        deleted_count = (
            self.session.query(OutboxEvent)
            .filter(OutboxEvent.processed_at.is_not(None))
            .filter(OutboxEvent.processed_at < cutoff_date)
            .delete()
        )

        self.session.commit()

        logger.info(f"Cleaned up {deleted_count} processed outbox events")
        return deleted_count
