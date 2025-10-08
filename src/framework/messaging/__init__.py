"""
Message Queue Abstractions Framework

Provides comprehensive message queue management utilities including:
- Queue patterns and abstractions
- Message routing and exchange management
- Dead letter queues and error handling
- Message serialization and deserialization
- Producer/consumer abstractions
- Multiple backend support (RabbitMQ, Redis, AWS SQS)
"""

from .backends import (
    BackendConfig,
    InMemoryBackend,
    MessageBackend,
    RabbitMQBackend,
    RedisBackend,
    SQSBackend,
    create_backend,
)
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
