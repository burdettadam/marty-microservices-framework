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

# Legacy event system
from ..events import (
    BaseEvent,
    EventBus,
    EventHandler,
    EventMetadata,
    publish_domain_event,
    publish_system_event,
)

# Backend implementations
from .backends import (
    BackendConfig,
    BackendFactory,
    InMemoryBackend,
    MessageBackend,
    RabbitMQBackend,
    RedisBackend,
)

# Core messaging infrastructure
from .core import (
    ExchangeConfig,
    ExchangeType,
    MessageBus,
    MessageExchange,
    MessageHeaders,
    MessageStatus,
)

# Dead letter queue support
from .dlq import DLQConfig, DLQManager, DLQMessage, RetryStrategy

# Messaging management
from .manager import (
    MessagingConfig,
    MessagingManager,
    create_messaging_config_from_dict,
)

# Middleware support
from .middleware import (
    AuthenticationMiddleware,
    CompressionMiddleware,
    MessageMiddleware,
    MetricsMiddleware,
    MiddlewareChain,
    ValidationMiddleware,
)

# Additional patterns
# Communication patterns
from .patterns import (
    Consumer,
    ConsumerConfig,
    Producer,
    ProducerConfig,
    PublishSubscribePattern,
    RequestReplyPattern,
    RoutingPattern,
    WorkQueuePattern,
)

# Core messaging imports
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

# Message routing
from .routing import MessageRouter, RoutingConfig, RoutingEngine, RoutingRule

# Serialization support
from .serialization import (
    AvroSerializer,
    JSONSerializer,
    MessageSerializer,
    PickleSerializer,
    ProtobufSerializer,
    SerializationError,
)

# Event streaming imports
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

# Consolidated exports - only items that are actually imported
__all__ = [
    # Core message queue components
    "Message",
    "MessageBroker",
    "MessageConfig",
    "MessageHandler",
    "MessagePattern",
    "MessagePriority",
    "MessageQueue",
    "MessageStats",

    # Event streaming components
    "Aggregate",
    "EventProcessor",
    "EventSourcedRepository",
    "EventStore",
    "EventStream",
    "EventStreamManager",
    "EventType",
    "InMemoryEventStore",
    "Repository",
    "StreamEvent",
    "StreamEventBus",
    "StreamEventHandler",
    "StreamProjection",

    # Legacy event system
    "BaseEvent",
    "EventBus",
    "EventHandler",
    "EventMetadata",

    # Backend implementations
    "BackendConfig",
    "BackendFactory",
    "InMemoryBackend",
    "MessageBackend",
    "RabbitMQBackend",
    "RedisBackend",

    # Communication patterns
    "Consumer",
    "Producer",
    "RequestReplyPattern",
    "WorkQueuePattern",
    "ConsumerConfig",
    "ProducerConfig",
    "PublishSubscribePattern",
    "RoutingPattern",

    # Core infrastructure
    "ExchangeConfig",
    "ExchangeType",
    "MessageBus",
    "MessageExchange",
    "MessageHeaders",
    "MessageStatus",

    # Dead letter queue
    "DLQConfig",
    "DLQManager",
    "DLQMessage",
    "RetryStrategy",

    # Management
    "MessagingConfig",
    "MessagingManager",

    # Middleware
    "AuthenticationMiddleware",
    "CompressionMiddleware",
    "MessageMiddleware",
    "MetricsMiddleware",
    "MiddlewareChain",
    "ValidationMiddleware",

    # Routing
    "MessageRouter",
    "RoutingConfig",
    "RoutingEngine",
    "RoutingRule",

    # Serialization
    "AvroSerializer",
    "JSONSerializer",
    "MessageSerializer",
    "PickleSerializer",
    "ProtobufSerializer",
    "SerializationError",

    # Factory functions
    "create_event_manager",
    "create_message_queue",
    "create_messaging_config_from_dict",

    # Context managers
    "event_streaming_context",
    "message_queue_context",

    # Utility functions
    "domain_event",
    "get_event_manager",
    "get_message_queue",
    "message_handler",
    "publish_domain_event",
    "publish_message",
    "publish_system_event",
    "stream_event_handler",
]
