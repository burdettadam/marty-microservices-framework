"""
Messaging Infrastructure Package.

Provides comprehensive messaging capabilities including:
- Message queues with multiple brokers (RabbitMQ, Kafka, Redis, In-Memory)
- Event streaming and processing
- Event sourcing and CQRS patterns
- Reliable async communication patterns

Usage Examples:

1. Basic Message Queue:
```python
from framework.messaging import MessageConfig, MessageQueue, MessageHandler, Message

# Configure message queue
config = MessageConfig(
    broker=MessageBroker.RABBITMQ,
    host="localhost",
    port=5672,
    username="guest",
    password="guest"
)

# Create queue
queue = MessageQueue(config)
await queue.start()

# Publish message
await queue.publish("user.events", {"user_id": 123, "action": "created"})

# Handle messages
class UserEventHandler(MessageHandler):
    async def handle(self, message: Message) -> bool:
        print(f"Processing user event: {message.payload}")
        return True

    def get_topics(self) -> List[str]:
        return ["user.events"]

await queue.subscribe("user.events", UserEventHandler())
```

2. Event Streaming:
```python
from framework.messaging import EventStreamManager, StreamEvent, StreamProjection

# Create event manager
manager = EventStreamManager()
await manager.start()

# Define domain event
@domain_event("user_created")
class UserCreatedEvent(StreamEvent):
    def __init__(self, user_id: str, email: str):
        super().__init__()
        self.data = {"user_id": user_id, "email": email}

# Create projection
class UserCountProjection(StreamProjection):
    def __init__(self):
        super().__init__("user_count")
        self.count = 0

    async def project(self, event: StreamEvent) -> None:
        if event.event_type == "user_created":
            self.count += 1

    def can_handle(self, event: StreamEvent) -> bool:
        return event.event_type in ["user_created", "user_deleted"]

# Add projection
projection = UserCountProjection()
manager.add_projection(projection)

# Append events
event = UserCreatedEvent("123", "user@example.com")
await manager.append_events("user-stream", [event])
```

3. Request/Reply Pattern:
```python
# Send request and wait for reply
result = await queue.request_reply(
    "user.commands",
    {"command": "get_user", "user_id": 123},
    timeout=30.0
)
```

4. Context Managers:
```python
# Message queue with automatic lifecycle
async with message_queue_context("default", config) as queue:
    await queue.publish("events", {"message": "Hello World"})

# Event streaming with automatic lifecycle
async with event_streaming_context() as manager:
    await manager.append_events("stream", [event])
```

Available Classes:
- MessageQueue: High-level message queue interface
- MessageConfig: Configuration for message brokers
- Message: Message container with metadata
- MessageHandler: Abstract handler interface
- EventStreamManager: Event streaming manager
- StreamEvent: Base event class for event sourcing
- EventStore: Abstract event storage interface
- Aggregate: Base aggregate root for DDD
- Repository: Abstract repository interface
- EventBus: Event publish/subscribe bus

Supported Brokers:
- RabbitMQ (requires aio-pika)
- Apache Kafka (requires aiokafka)
- Redis Streams (requires aioredis)
- In-Memory (for development/testing)

Messaging Patterns:
- Publish/Subscribe
- Request/Reply (RPC)
- Work Queues
- Topic Routing
- Event Sourcing
- CQRS
"""

# New enterprise messaging components
# (Removed incorrect/unused typing import for built-in List; use builtins.list annotations directly if needed)

from .queue import (
    Message,
    MessageBroker,
    MessageConfig,
    MessageHandler,
    MessagePattern,
    MessagePriority,
    MessageQueue,
    MessageStats,
    create_message_queue,
    get_message_queue,
    message_handler,
    message_queue_context,
    publish_message,
)
from .streams import Aggregate
from .streams import Event as StreamEvent
from .streams import EventBus as StreamEventBus
from .streams import EventHandler as StreamEventHandler
from .streams import (
    EventProcessor,
    EventSourcedRepository,
    EventStore,
    EventStream,
    EventStreamManager,
    EventType,
    InMemoryEventStore,
    Repository,
    StreamProjection,
    create_event_manager,
    domain_event,
)
from .streams import event_handler as stream_event_handler
from .streams import event_streaming_context, get_event_manager

__all__ = [
    "Aggregate",
    "EventProcessor",
    "EventSourcedRepository",
    "EventStore",
    "EventStream",
    "EventStreamManager",
    # Event Streaming Components
    "EventType",
    "InMemoryEventStore",
    "Message",
    # Message Queue Components
    "MessageBroker",
    "MessageConfig",
    "MessageHandler",
    "MessagePattern",
    "MessagePriority",
    "MessageQueue",
    "MessageStats",
    "Repository",
    "StreamEvent",
    "StreamEventBus",
    "StreamEventHandler",
    "StreamProjection",
    "create_event_manager",
    "create_message_queue",
    "domain_event",
    "event_streaming_context",
    "get_event_manager",
    "get_message_queue",
    "message_handler",
    "message_queue_context",
    "publish_message",
    "stream_event_handler",
]

# New enterprise messaging components

__all__ = [
    "Aggregate",
    "EventProcessor",
    "EventSourcedRepository",
    "EventStore",
    "EventStream",
    "EventStreamManager",
    # Event Streaming Components
    "EventType",
    "InMemoryEventStore",
    "Message",
    # Message Queue Components
    "MessageBroker",
    "MessageConfig",
    "MessageHandler",
    "MessagePattern",
    "MessagePriority",
    "MessageQueue",
    "MessageStats",
    "Repository",
    "StreamEvent",
    "StreamEventBus",
    "StreamEventHandler",
    "StreamProjection",
    "create_event_manager",
    "create_message_queue",
    "domain_event",
    "event_streaming_context",
    "get_event_manager",
    "get_message_queue",
    "message_handler",
    "message_queue_context",
    "publish_message",
    "stream_event_handler",
]

# Legacy backend imports
from .backends import (
    BackendConfig,
    InMemoryBackend,
    MessageBackend,
    RabbitMQBackend,
    RedisBackend,
    SQSBackend,
    create_backend,
)
from .events import (
    Event,
    EventBus,
    EventHandler,
    EventMetadata,
    event_handler,
    publish_event,
)
from .patterns import (
    DelayedMessage,
    PatternHandler,
    PubSubPattern,
    RequestReplyPattern,
    WorkQueuePattern,
)

# New enterprise messaging components
from .queue import BaseMessage
from .queue import Message as NewMessage
from .queue import MessageConsumer
from .queue import MessageHandler as NewMessageHandler
from .queue import MessagePattern as NewMessagePattern
from .queue import MessageProducer
from .queue import MessageQueue as NewMessageQueue
from .queue import MessageRouter, QueueConfig, QueueManager, QueueMetrics
from .queue import message_handler as new_message_handler

__all__ = [
    "Aggregate",
    # Legacy Backend Components
    "BackendConfig",
    # Legacy Queue Components
    "BaseMessage",
    # Legacy Pattern Components
    "DeadLetterQueue",
    "DelayedMessage",
    "Event",
    # Legacy Event Components
    "EventBus",
    "EventHandler",
    "EventMetadata",
    "EventProcessor",
    "EventSourcedRepository",
    "EventStore",
    "EventStream",
    "EventStreamManager",
    # Event Streaming Components
    "EventType",
    "InMemoryBackend",
    "InMemoryEventStore",
    "MessageBackend",
    # New Message Queue Components
    "MessageBroker",
    "MessageConfig",
    "MessageConsumer",
    "MessagePattern",
    "MessagePriority",
    "MessageProducer",
    "MessageQueue",
    "MessageRouter",
    "MessageStats",
    "NewMessage",
    "NewMessageHandler",
    "NewMessagePattern",
    "NewMessageQueue",
    "PatternHandler",
    "PubSubPattern",
    "QueueConfig",
    "QueueManager",
    "QueueMetrics",
    "RabbitMQBackend",
    "RedisBackend",
    "Repository",
    "RequestReplyPattern",
    "SQSBackend",
    "StreamEvent",
    "StreamEventBus",
    "StreamEventHandler",
    "StreamProjection",
    "WorkQueuePattern",
    "create_backend",
    "create_event_manager",
    "create_message_queue",
    "domain_event",
    "event_handler",
    "event_streaming_context",
    "get_event_manager",
    "get_message_queue",
    "message_queue_context",
    "new_message_handler",
    "publish_event",
    "publish_message",
    "stream_event_handler",
]

from .core import (
    ExchangeConfig,
    ExchangeType,
    MessageExchange,
    MessageHeaders,
    MessageStatus,
)
from .dlq import (
    DeadLetterQueue,
    DLQConfig,
    DLQStrategy,
    MessageFailureHandler,
    RetryStrategy,
)
from .manager import (
    MessagingConfig,
    MessagingManager,
    get_messaging_manager,
    initialize_messaging,
)
from .middleware import (
    AuthenticationMiddleware,
    CompressionMiddleware,
    EncryptionMiddleware,
    MessageMiddleware,
    MetricsMiddleware,
    MiddlewareChain,
    TracingMiddleware,
)
from .patterns import (
    Consumer,
    ConsumerConfig,
    Producer,
    ProducerConfig,
    PublishSubscribePattern,
    RoutingPattern,
)
from .routing import (
    DirectRouter,
    FanoutRouter,
    Route,
    Router,
    RoutingKey,
    RoutingStrategy,
    TopicRouter,
)
from .serialization import (
    AvroSerializer,
    JSONSerializer,
    MessageSerializer,
    PickleSerializer,
    ProtobufSerializer,
    SerializationError,
)

__all__ = [
    "AuthenticationMiddleware",
    "AvroSerializer",
    "BackendConfig",
    "CompressionMiddleware",
    "Consumer",
    "ConsumerConfig",
    "DLQConfig",
    "DLQStrategy",
    # Dead Letter Queue
    "DeadLetterQueue",
    "DirectRouter",
    "EncryptionMiddleware",
    "ExchangeConfig",
    "ExchangeType",
    "FanoutRouter",
    "InMemoryBackend",
    "JSONSerializer",
    # Core
    "Message",
    # Backends
    "MessageBackend",
    "MessageExchange",
    "MessageFailureHandler",
    "MessageHandler",
    "MessageHeaders",
    # Middleware
    "MessageMiddleware",
    "MessagePattern",
    "MessagePriority",
    "MessageQueue",
    "MessageRouter",
    # Serialization
    "MessageSerializer",
    "MessageStatus",
    "MessagingConfig",
    # Manager
    "MessagingManager",
    "MetricsMiddleware",
    "MiddlewareChain",
    "PickleSerializer",
    # Patterns
    "Producer",
    "ProducerConfig",
    "ProtobufSerializer",
    "PublishSubscribePattern",
    "QueueConfig",
    "QueueManager",
    "RabbitMQBackend",
    "RedisBackend",
    "RequestReplyPattern",
    "RetryStrategy",
    "Route",
    # Routing
    "Router",
    "RoutingKey",
    "RoutingPattern",
    "RoutingStrategy",
    "SQSBackend",
    "SerializationError",
    "TopicRouter",
    "TracingMiddleware",
    "WorkQueuePattern",
    "create_backend",
    "get_messaging_manager",
    "initialize_messaging",
]
