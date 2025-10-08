"""
Core Message Queue Abstractions

Provides fundamental message and queue abstractions that form the foundation
of the messaging framework.
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


class MessageStatus(Enum):
    """Message processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    RETRYING = "retrying"


class ExchangeType(Enum):
    """Exchange types for message routing."""

    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    HEADERS = "headers"


@dataclass
class MessageHeaders:
    """Message headers container."""

    # Standard headers
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    content_type: str = "application/json"
    content_encoding: str = "utf-8"
    priority: MessagePriority = MessagePriority.NORMAL
    expiration: Optional[float] = None
    reply_to: Optional[str] = None

    # Routing headers
    routing_key: Optional[str] = None
    exchange: Optional[str] = None

    # Processing headers
    retry_count: int = 0
    max_retries: int = 3
    delay_seconds: float = 0.0

    # Custom headers
    custom: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.expiration is None:
            return False
        return time.time() > (self.timestamp + self.expiration)

    def should_retry(self) -> bool:
        """Check if message should be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self):
        """Increment retry counter."""
        self.retry_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert headers to dictionary."""
        return {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "content_type": self.content_type,
            "content_encoding": self.content_encoding,
            "priority": self.priority.value,
            "expiration": self.expiration,
            "reply_to": self.reply_to,
            "routing_key": self.routing_key,
            "exchange": self.exchange,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "delay_seconds": self.delay_seconds,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageHeaders":
        """Create headers from dictionary."""
        headers = cls()
        headers.message_id = data.get("message_id", headers.message_id)
        headers.correlation_id = data.get("correlation_id")
        headers.timestamp = data.get("timestamp", headers.timestamp)
        headers.content_type = data.get("content_type", headers.content_type)
        headers.content_encoding = data.get(
            "content_encoding", headers.content_encoding
        )
        headers.priority = MessagePriority(data.get("priority", headers.priority.value))
        headers.expiration = data.get("expiration")
        headers.reply_to = data.get("reply_to")
        headers.routing_key = data.get("routing_key")
        headers.exchange = data.get("exchange")
        headers.retry_count = data.get("retry_count", headers.retry_count)
        headers.max_retries = data.get("max_retries", headers.max_retries)
        headers.delay_seconds = data.get("delay_seconds", headers.delay_seconds)
        headers.custom = data.get("custom", {})
        return headers


@dataclass
class Message:
    """Core message abstraction."""

    body: Any
    headers: MessageHeaders = field(default_factory=MessageHeaders)
    status: MessageStatus = MessageStatus.PENDING

    def __post_init__(self):
        """Initialize message after creation."""
        if not self.headers.message_id:
            self.headers.message_id = str(uuid.uuid4())

    @property
    def id(self) -> str:
        """Get message ID."""
        return self.headers.message_id

    @property
    def correlation_id(self) -> Optional[str]:
        """Get correlation ID."""
        return self.headers.correlation_id

    @property
    def routing_key(self) -> Optional[str]:
        """Get routing key."""
        return self.headers.routing_key

    @property
    def priority(self) -> MessagePriority:
        """Get message priority."""
        return self.headers.priority

    def is_expired(self) -> bool:
        """Check if message has expired."""
        return self.headers.is_expired()

    def should_retry(self) -> bool:
        """Check if message should be retried."""
        return self.headers.should_retry()

    def mark_processing(self):
        """Mark message as being processed."""
        self.status = MessageStatus.PROCESSING

    def mark_completed(self):
        """Mark message as completed."""
        self.status = MessageStatus.COMPLETED

    def mark_failed(self):
        """Mark message as failed."""
        self.status = MessageStatus.FAILED
        self.headers.increment_retry()

    def mark_dead_letter(self):
        """Mark message as dead letter."""
        self.status = MessageStatus.DEAD_LETTER

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "body": self.body,
            "headers": self.headers.to_dict(),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            body=data["body"],
            headers=MessageHeaders.from_dict(data["headers"]),
            status=MessageStatus(data["status"]),
        )


@dataclass
class QueueConfig:
    """Configuration for message queues."""

    name: str
    durable: bool = True
    auto_delete: bool = False
    exclusive: bool = False
    max_length: Optional[int] = None
    max_priority: int = 15
    message_ttl: Optional[int] = None
    dead_letter_exchange: Optional[str] = None
    dead_letter_routing_key: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExchangeConfig:
    """Configuration for message exchanges."""

    name: str
    exchange_type: ExchangeType = ExchangeType.DIRECT
    durable: bool = True
    auto_delete: bool = False
    internal: bool = False
    arguments: Dict[str, Any] = field(default_factory=dict)


class MessageQueue(ABC):
    """Abstract base class for message queues."""

    def __init__(self, config: QueueConfig):
        self.config = config
        self.name = config.name

        # Metrics
        self._message_count = 0
        self._consumer_count = 0
        self._published_count = 0
        self._consumed_count = 0
        self._failed_count = 0

    @abstractmethod
    async def publish(self, message: Message) -> bool:
        """Publish a message to the queue."""
        pass

    @abstractmethod
    async def consume(self, timeout: Optional[float] = None) -> Optional[Message]:
        """Consume a message from the queue."""
        pass

    @abstractmethod
    async def ack(self, message: Message) -> bool:
        """Acknowledge message processing."""
        pass

    @abstractmethod
    async def nack(self, message: Message, requeue: bool = True) -> bool:
        """Negative acknowledge message."""
        pass

    @abstractmethod
    async def purge(self) -> int:
        """Purge all messages from queue."""
        pass

    @abstractmethod
    async def delete(self) -> bool:
        """Delete the queue."""
        pass

    @abstractmethod
    async def get_message_count(self) -> int:
        """Get number of messages in queue."""
        pass

    @abstractmethod
    async def get_consumer_count(self) -> int:
        """Get number of active consumers."""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "name": self.name,
            "config": {
                "durable": self.config.durable,
                "auto_delete": self.config.auto_delete,
                "max_length": self.config.max_length,
                "max_priority": self.config.max_priority,
            },
            "metrics": {
                "message_count": self._message_count,
                "consumer_count": self._consumer_count,
                "published_count": self._published_count,
                "consumed_count": self._consumed_count,
                "failed_count": self._failed_count,
            },
        }


class MessageExchange(ABC):
    """Abstract base class for message exchanges."""

    def __init__(self, config: ExchangeConfig):
        self.config = config
        self.name = config.name
        self.exchange_type = config.exchange_type

        # Bound queues
        self._bindings: Dict[str, List[str]] = {}  # routing_key -> queue_names

        # Metrics
        self._published_count = 0
        self._routed_count = 0
        self._unrouted_count = 0

    @abstractmethod
    async def publish(self, message: Message, routing_key: str = "") -> bool:
        """Publish message to exchange."""
        pass

    @abstractmethod
    async def bind_queue(self, queue_name: str, routing_key: str = "") -> bool:
        """Bind queue to exchange."""
        pass

    @abstractmethod
    async def unbind_queue(self, queue_name: str, routing_key: str = "") -> bool:
        """Unbind queue from exchange."""
        pass

    @abstractmethod
    async def delete(self) -> bool:
        """Delete the exchange."""
        pass

    def get_bindings(self) -> Dict[str, List[str]]:
        """Get exchange bindings."""
        return self._bindings.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get exchange statistics."""
        return {
            "name": self.name,
            "type": self.exchange_type.value,
            "config": {
                "durable": self.config.durable,
                "auto_delete": self.config.auto_delete,
                "internal": self.config.internal,
            },
            "bindings": self._bindings,
            "metrics": {
                "published_count": self._published_count,
                "routed_count": self._routed_count,
                "unrouted_count": self._unrouted_count,
            },
        }


class QueueManager(ABC):
    """Abstract base class for queue managers."""

    def __init__(self):
        self._queues: Dict[str, MessageQueue] = {}
        self._exchanges: Dict[str, MessageExchange] = {}

    @abstractmethod
    async def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create a new queue."""
        pass

    @abstractmethod
    async def create_exchange(self, config: ExchangeConfig) -> MessageExchange:
        """Create a new exchange."""
        pass

    @abstractmethod
    async def delete_queue(self, name: str) -> bool:
        """Delete a queue."""
        pass

    @abstractmethod
    async def delete_exchange(self, name: str) -> bool:
        """Delete an exchange."""
        pass

    async def get_queue(self, name: str) -> Optional[MessageQueue]:
        """Get queue by name."""
        return self._queues.get(name)

    async def get_exchange(self, name: str) -> Optional[MessageExchange]:
        """Get exchange by name."""
        return self._exchanges.get(name)

    async def list_queues(self) -> List[str]:
        """List all queue names."""
        return list(self._queues.keys())

    async def list_exchanges(self) -> List[str]:
        """List all exchange names."""
        return list(self._exchanges.keys())

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to message broker."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from message broker."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to message broker."""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        queue_stats = {}
        exchange_stats = {}

        for name, queue in self._queues.items():
            queue_stats[name] = queue.get_stats()

        for name, exchange in self._exchanges.items():
            exchange_stats[name] = exchange.get_stats()

        return {
            "queues": queue_stats,
            "exchanges": exchange_stats,
            "total_queues": len(self._queues),
            "total_exchanges": len(self._exchanges),
        }
