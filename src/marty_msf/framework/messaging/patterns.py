"""
Message Patterns and Producer/Consumer Abstractions

Provides high-level messaging patterns including request-reply, publish-subscribe,
work queues, and routing patterns with producer/consumer abstractions.
"""

import asyncio
import builtins
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .core import Message, MessageHeaders, MessagePriority
from .serialization import JSONSerializer, MessageSerializer

logger = logging.getLogger(__name__)


class MessagePattern(Enum):
    """Message pattern types."""

    REQUEST_REPLY = "request_reply"
    PUBLISH_SUBSCRIBE = "publish_subscribe"
    WORK_QUEUE = "work_queue"
    ROUTING = "routing"
    RPC = "rpc"


class ConsumerMode(Enum):
    """Consumer processing modes."""

    PULL = "pull"  # Consumer pulls messages
    PUSH = "push"  # Messages pushed to consumer
    STREAMING = "streaming"  # Continuous streaming


@dataclass
class ProducerConfig:
    """Configuration for message producers."""

    # Basic config
    name: str
    exchange: str | None = None
    routing_key: str = ""

    # Message settings
    default_priority: MessagePriority = MessagePriority.NORMAL
    default_ttl: float | None = None
    persistent: bool = True

    # Serialization
    serializer: MessageSerializer | None = None

    # Reliability
    confirm_delivery: bool = True
    retry_attempts: int = 3
    retry_delay: float = 1.0

    # Performance
    batch_size: int = 1
    batch_timeout: float = 1.0
    connection_pool_size: int = 5

    # Monitoring
    enable_metrics: bool = True


@dataclass
class ConsumerConfig:
    """Configuration for message consumers."""

    # Basic config
    name: str
    queue: str
    consumer_tag: str | None = None

    # Processing settings
    mode: ConsumerMode = ConsumerMode.PULL
    prefetch_count: int = 10
    prefetch_size: int = 0
    auto_ack: bool = False

    # Concurrency
    max_workers: int = 1
    worker_timeout: float = 30.0

    # Retry and error handling
    retry_attempts: int = 3
    retry_delay: float = 1.0
    dead_letter_enabled: bool = True

    # Serialization
    serializer: MessageSerializer | None = None

    # Monitoring
    enable_metrics: bool = True


class MessageHandler(ABC):
    """Abstract message handler."""

    @abstractmethod
    async def handle(self, message: Message) -> bool:
        """
        Handle a message.

        Args:
            message: Message to handle

        Returns:
            True if message was processed successfully, False otherwise
        """

    async def on_error(self, message: Message, error: Exception):
        """Handle processing error."""
        logger.error(f"Error processing message {message.id}: {error}")


class Producer:
    """Message producer with pattern support."""

    def __init__(self, config: ProducerConfig, backend=None):
        self.config = config
        self.backend = backend
        self.serializer = config.serializer or JSONSerializer()

        # State
        self._connected = False
        self._message_buffer = []
        self._batch_timer = None

        # Metrics
        self._published_count = 0
        self._confirmed_count = 0
        self._failed_count = 0
        self._total_publish_time = 0.0

    async def connect(self):
        """Connect producer to backend."""
        if self.backend:
            await self.backend.connect()
        self._connected = True
        logger.info(f"Producer '{self.config.name}' connected")

    async def disconnect(self):
        """Disconnect producer from backend."""
        if self._batch_timer:
            self._batch_timer.cancel()

        if self._message_buffer:
            await self._flush_batch()

        if self.backend:
            await self.backend.disconnect()

        self._connected = False
        logger.info(f"Producer '{self.config.name}' disconnected")

    async def publish(
        self,
        body: Any,
        routing_key: str | None = None,
        headers: builtins.dict[str, Any] | None = None,
        priority: MessagePriority | None = None,
        exchange: str | None = None,
    ) -> str:
        """
        Publish a message.

        Args:
            body: Message body
            routing_key: Routing key (overrides config default)
            headers: Custom headers
            priority: Message priority (overrides config default)
            exchange: Exchange name (overrides config default)

        Returns:
            Message ID
        """
        start_time = time.time()

        # Create message
        message_headers = MessageHeaders(
            routing_key=routing_key or self.config.routing_key,
            exchange=exchange or self.config.exchange,
            priority=priority or self.config.default_priority,
        )

        if headers:
            message_headers.custom.update(headers)

        if self.config.default_ttl:
            message_headers.expiration = self.config.default_ttl

        message = Message(body=body, headers=message_headers)

        try:
            # Serialize message body
            serialized_body = self.serializer.serialize(body)
            message.body = serialized_body
            message.headers.content_type = self.serializer.get_content_type()

            # Batch or immediate publish
            if self.config.batch_size > 1:
                await self._add_to_batch(message)
            else:
                await self._publish_message(message)

            self._published_count += 1
            self._total_publish_time += time.time() - start_time

            return message.id

        except Exception as e:
            self._failed_count += 1
            logger.error(f"Failed to publish message: {e}")
            raise

    async def _add_to_batch(self, message: Message):
        """Add message to batch."""
        self._message_buffer.append(message)

        if len(self._message_buffer) >= self.config.batch_size:
            await self._flush_batch()
        elif not self._batch_timer:
            self._batch_timer = asyncio.create_task(self._batch_timeout_handler())

    async def _batch_timeout_handler(self):
        """Handle batch timeout."""
        await asyncio.sleep(self.config.batch_timeout)
        if self._message_buffer:
            await self._flush_batch()
        self._batch_timer = None

    async def _flush_batch(self):
        """Flush message batch."""
        if not self._message_buffer:
            return

        messages = self._message_buffer.copy()
        self._message_buffer.clear()

        if self._batch_timer:
            self._batch_timer.cancel()
            self._batch_timer = None

        # Publish batch
        for message in messages:
            await self._publish_message(message)

    async def _publish_message(self, message: Message):
        """Publish single message."""
        if not self.backend:
            raise RuntimeError("No backend configured")

        success = await self.backend.publish(message)

        if success and self.config.confirm_delivery:
            self._confirmed_count += 1
        elif not success:
            raise RuntimeError("Failed to publish message")

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get producer statistics."""
        avg_publish_time = self._total_publish_time / max(1, self._published_count)

        return {
            "name": self.config.name,
            "connected": self._connected,
            "published_count": self._published_count,
            "confirmed_count": self._confirmed_count,
            "failed_count": self._failed_count,
            "buffered_messages": len(self._message_buffer),
            "average_publish_time": avg_publish_time,
            "config": {
                "exchange": self.config.exchange,
                "routing_key": self.config.routing_key,
                "batch_size": self.config.batch_size,
                "confirm_delivery": self.config.confirm_delivery,
            },
        }


class Consumer:
    """Message consumer with pattern support."""

    def __init__(self, config: ConsumerConfig, handler: MessageHandler, backend=None):
        self.config = config
        self.handler = handler
        self.backend = backend
        self.serializer = config.serializer or JSONSerializer()

        # State
        self._connected = False
        self._consuming = False
        self._workers = []

        # Metrics
        self._consumed_count = 0
        self._processed_count = 0
        self._failed_count = 0
        self._total_process_time = 0.0

    async def connect(self):
        """Connect consumer to backend."""
        if self.backend:
            await self.backend.connect()
        self._connected = True
        logger.info(f"Consumer '{self.config.name}' connected")

    async def disconnect(self):
        """Disconnect consumer from backend."""
        await self.stop_consuming()

        if self.backend:
            await self.backend.disconnect()

        self._connected = False
        logger.info(f"Consumer '{self.config.name}' disconnected")

    async def start_consuming(self):
        """Start consuming messages."""
        if not self._connected:
            await self.connect()

        self._consuming = True

        # Start worker tasks
        for i in range(self.config.max_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.append(worker)

        logger.info(f"Consumer '{self.config.name}' started with {self.config.max_workers} workers")

    async def stop_consuming(self):
        """Stop consuming messages."""
        self._consuming = False

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        logger.info(f"Consumer '{self.config.name}' stopped")

    async def _worker_loop(self, worker_id: str):
        """Worker loop for processing messages."""
        logger.info(f"Worker {worker_id} started")

        try:
            while self._consuming:
                try:
                    # Get message from backend
                    message = await self._get_message()

                    if message:
                        await self._process_message(message, worker_id)
                    else:
                        # No message available, brief sleep
                        await asyncio.sleep(0.1)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}")
                    await asyncio.sleep(1.0)  # Brief pause on error

        except asyncio.CancelledError:
            pass
        finally:
            logger.info(f"Worker {worker_id} stopped")

    async def _get_message(self) -> Message | None:
        """Get message from backend."""
        if not self.backend:
            return None

        return await self.backend.consume(timeout=1.0)

    async def _process_message(self, message: Message, worker_id: str):
        """Process a single message."""
        start_time = time.time()
        self._consumed_count += 1

        try:
            # Deserialize message body
            if isinstance(message.body, bytes):
                message.body = self.serializer.deserialize(message.body)

            # Mark as processing
            message.mark_processing()

            # Handle message with timeout
            success = await asyncio.wait_for(
                self.handler.handle(message), timeout=self.config.worker_timeout
            )

            if success:
                message.mark_completed()
                if not self.config.auto_ack and self.backend:
                    await self.backend.ack(message)
                self._processed_count += 1
            else:
                message.mark_failed()
                await self._handle_failed_message(message)

        except asyncio.TimeoutError:
            logger.warning(f"Message {message.id} processing timeout in {worker_id}")
            message.mark_failed()
            await self._handle_failed_message(message)

        except Exception as e:
            logger.error(f"Error processing message {message.id} in {worker_id}: {e}")
            message.mark_failed()
            await self.handler.on_error(message, e)
            await self._handle_failed_message(message)
            self._failed_count += 1

        finally:
            process_time = time.time() - start_time
            self._total_process_time += process_time

    async def _handle_failed_message(self, message: Message):
        """Handle failed message processing."""
        if message.should_retry():
            # Retry message
            message.status = message.status.RETRYING
            if self.backend:
                await self.backend.nack(message, requeue=True)
        else:
            # Send to dead letter queue
            if self.config.dead_letter_enabled and self.backend:
                await self.backend.send_to_dlq(message)

            if self.backend:
                await self.backend.nack(message, requeue=False)

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get consumer statistics."""
        avg_process_time = self._total_process_time / max(1, self._consumed_count)

        success_rate = self._processed_count / max(1, self._consumed_count)

        return {
            "name": self.config.name,
            "connected": self._connected,
            "consuming": self._consuming,
            "active_workers": len(self._workers),
            "consumed_count": self._consumed_count,
            "processed_count": self._processed_count,
            "failed_count": self._failed_count,
            "success_rate": success_rate,
            "average_process_time": avg_process_time,
            "config": {
                "queue": self.config.queue,
                "max_workers": self.config.max_workers,
                "prefetch_count": self.config.prefetch_count,
                "auto_ack": self.config.auto_ack,
            },
        }


# Message Pattern Implementations


class RequestReplyPattern:
    """Request-reply messaging pattern."""

    def __init__(self, producer: Producer, consumer: Consumer, timeout: float = 30.0):
        self.producer = producer
        self.consumer = consumer
        self.timeout = timeout
        self._pending_requests: builtins.dict[str, asyncio.Future] = {}

    async def request(self, body: Any, routing_key: str = "") -> Any:
        """Send request and wait for reply."""
        # Create correlation ID
        correlation_id = str(uuid.uuid4())
        reply_queue = f"reply.{correlation_id}"

        # Create future for response
        future = asyncio.Future()
        self._pending_requests[correlation_id] = future

        try:
            # Send request
            await self.producer.publish(
                body=body,
                routing_key=routing_key,
                headers={"correlation_id": correlation_id, "reply_to": reply_queue},
            )

            # Wait for response
            response = await asyncio.wait_for(future, timeout=self.timeout)
            return response

        except asyncio.TimeoutError:
            raise TimeoutError(f"Request timeout after {self.timeout} seconds")
        finally:
            self._pending_requests.pop(correlation_id, None)

    async def handle_reply(self, message: Message):
        """Handle reply message."""
        correlation_id = message.headers.correlation_id

        if correlation_id in self._pending_requests:
            future = self._pending_requests[correlation_id]
            if not future.done():
                future.set_result(message.body)


class PublishSubscribePattern:
    """Publish-subscribe messaging pattern."""

    def __init__(self, producer: Producer, exchange: str):
        self.producer = producer
        self.exchange = exchange
        self.subscribers: builtins.list[Consumer] = []

    async def publish(self, body: Any, topic: str = "") -> str:
        """Publish message to topic."""
        return await self.producer.publish(body=body, routing_key=topic, exchange=self.exchange)

    def add_subscriber(self, consumer: Consumer):
        """Add subscriber."""
        self.subscribers.append(consumer)

    def remove_subscriber(self, consumer: Consumer):
        """Remove subscriber."""
        if consumer in self.subscribers:
            self.subscribers.remove(consumer)


class WorkQueuePattern:
    """Work queue messaging pattern."""

    def __init__(self, producer: Producer, queue: str):
        self.producer = producer
        self.queue = queue
        self.workers: builtins.list[Consumer] = []

    async def add_work(self, body: Any, priority: MessagePriority = MessagePriority.NORMAL) -> str:
        """Add work to queue."""
        return await self.producer.publish(body=body, routing_key=self.queue, priority=priority)

    def add_worker(self, consumer: Consumer):
        """Add worker."""
        self.workers.append(consumer)

    def remove_worker(self, consumer: Consumer):
        """Remove worker."""
        if consumer in self.workers:
            self.workers.remove(consumer)


class RoutingPattern:
    """Routing messaging pattern."""

    def __init__(self, producer: Producer, exchange: str):
        self.producer = producer
        self.exchange = exchange
        self.routes: builtins.dict[str, builtins.list[Consumer]] = {}

    async def send(self, body: Any, routing_key: str) -> str:
        """Send message with routing key."""
        return await self.producer.publish(
            body=body, routing_key=routing_key, exchange=self.exchange
        )

    def add_route(self, routing_key: str, consumer: Consumer):
        """Add route."""
        if routing_key not in self.routes:
            self.routes[routing_key] = []
        self.routes[routing_key].append(consumer)

    def remove_route(self, routing_key: str, consumer: Consumer):
        """Remove route."""
        if routing_key in self.routes and consumer in self.routes[routing_key]:
            self.routes[routing_key].remove(consumer)
