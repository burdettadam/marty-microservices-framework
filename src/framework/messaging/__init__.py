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
    # Message Queue Components
    "MessageBroker",
    "MessagePattern",
    "MessagePriority",
    "MessageConfig",
    "Message",
    "MessageStats",
    "MessageHandler",
    "MessageQueue",
    "get_message_queue",
    "create_message_queue",
    "message_queue_context",
    "message_handler",
    "publish_message",
    # Event Streaming Components
    "EventType",
    "StreamEvent",
    "EventStream",
    "EventStore",
    "InMemoryEventStore",
    "StreamEventHandler",
    "EventProcessor",
    "Aggregate",
    "Repository",
    "EventSourcedRepository",
    "StreamEventBus",
    "StreamProjection",
    "EventStreamManager",
    "get_event_manager",
    "create_event_manager",
    "event_streaming_context",
    "stream_event_handler",
    "domain_event",
]

# New enterprise messaging components
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
    # Message Queue Components
    "MessageBroker",
    "MessagePattern",
    "MessagePriority",
    "MessageConfig",
    "Message",
    "MessageStats",
    "MessageHandler",
    "MessageQueue",
    "get_message_queue",
    "create_message_queue",
    "message_queue_context",
    "message_handler",
    "publish_message",
    # Event Streaming Components
    "EventType",
    "StreamEvent",
    "EventStream",
    "EventStore",
    "InMemoryEventStore",
    "StreamEventHandler",
    "EventProcessor",
    "Aggregate",
    "Repository",
    "EventSourcedRepository",
    "StreamEventBus",
    "StreamProjection",
    "EventStreamManager",
    "get_event_manager",
    "create_event_manager",
    "event_streaming_context",
    "stream_event_handler",
    "domain_event",
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
    DeadLetterQueue,
    DelayedMessage,
    MessagePattern,
    PatternHandler,
    PubSubPattern,
    RequestReplyPattern,
    WorkQueuePattern,
)

# New enterprise messaging components
from .queue import BaseMessage
from .queue import Message as NewMessage
from .queue import MessageBroker, MessageConfig, MessageConsumer
from .queue import MessageHandler as NewMessageHandler
from .queue import MessagePattern as NewMessagePattern
from .queue import MessagePriority, MessageProducer
from .queue import MessageQueue
from .queue import MessageQueue as NewMessageQueue
from .queue import (
    MessageRouter,
    MessageStats,
    QueueConfig,
    QueueManager,
    QueueMetrics,
    create_message_queue,
    get_message_queue,
)
from .queue import message_handler as new_message_handler
from .queue import message_queue_context, publish_message
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
    # Legacy Backend Components
    "BackendConfig",
    "InMemoryBackend",
    "MessageBackend",
    "RabbitMQBackend",
    "RedisBackend",
    "SQSBackend",
    "create_backend",
    # Legacy Event Components
    "EventBus",
    "Event",
    "EventHandler",
    "EventMetadata",
    "event_handler",
    "publish_event",
    # Legacy Pattern Components
    "DeadLetterQueue",
    "DelayedMessage",
    "MessagePattern",
    "PatternHandler",
    "PubSubPattern",
    "RequestReplyPattern",
    "WorkQueuePattern",
    # Legacy Queue Components
    "BaseMessage",
    "MessageConsumer",
    "MessageProducer",
    "MessageQueue",
    "MessageRouter",
    "QueueConfig",
    "QueueManager",
    "QueueMetrics",
    # New Message Queue Components
    "MessageBroker",
    "NewMessagePattern",
    "MessagePriority",
    "MessageConfig",
    "NewMessage",
    "MessageStats",
    "NewMessageHandler",
    "NewMessageQueue",
    "get_message_queue",
    "create_message_queue",
    "message_queue_context",
    "new_message_handler",
    "publish_message",
    # Event Streaming Components
    "EventType",
    "StreamEvent",
    "EventStream",
    "EventStore",
    "InMemoryEventStore",
    "StreamEventHandler",
    "EventProcessor",
    "Aggregate",
    "Repository",
    "EventSourcedRepository",
    "StreamEventBus",
    "StreamProjection",
    "EventStreamManager",
    "get_event_manager",
    "create_event_manager",
    "event_streaming_context",
    "stream_event_handler",
    "domain_event",
]

from .core import (
    ExchangeConfig,
    ExchangeType,
    Message,
    MessageExchange,
    MessageHeaders,
    MessagePriority,
    MessageQueue,
    MessageStatus,
    QueueConfig,
    QueueManager,
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
    MessageHandler,
    MessagePattern,
    Producer,
    ProducerConfig,
    PublishSubscribePattern,
    RequestReplyPattern,
    RoutingPattern,
    WorkQueuePattern,
)
from .routing import (
    DirectRouter,
    FanoutRouter,
    MessageRouter,
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
    # Core
    "Message",
    "MessageHeaders",
    "MessagePriority",
    "MessageStatus",
    "QueueConfig",
    "ExchangeConfig",
    "ExchangeType",
    "MessageQueue",
    "MessageExchange",
    "QueueManager",
    # Serialization
    "MessageSerializer",
    "JSONSerializer",
    "PickleSerializer",
    "ProtobufSerializer",
    "AvroSerializer",
    "SerializationError",
    # Patterns
    "Producer",
    "Consumer",
    "MessageHandler",
    "ConsumerConfig",
    "ProducerConfig",
    "MessagePattern",
    "RequestReplyPattern",
    "PublishSubscribePattern",
    "WorkQueuePattern",
    "RoutingPattern",
    # Backends
    "MessageBackend",
    "RedisBackend",
    "RabbitMQBackend",
    "SQSBackend",
    "InMemoryBackend",
    "BackendConfig",
    "create_backend",
    # Dead Letter Queue
    "DeadLetterQueue",
    "DLQConfig",
    "DLQStrategy",
    "RetryStrategy",
    "MessageFailureHandler",
    # Routing
    "Router",
    "Route",
    "RoutingKey",
    "RoutingStrategy",
    "MessageRouter",
    "TopicRouter",
    "DirectRouter",
    "FanoutRouter",
    # Middleware
    "MessageMiddleware",
    "AuthenticationMiddleware",
    "EncryptionMiddleware",
    "CompressionMiddleware",
    "MetricsMiddleware",
    "TracingMiddleware",
    "MiddlewareChain",
    # Manager
    "MessagingManager",
    "MessagingConfig",
    "initialize_messaging",
    "get_messaging_manager",
]
