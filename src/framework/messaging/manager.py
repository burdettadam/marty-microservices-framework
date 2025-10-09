"""
Messaging Manager

Comprehensive messaging manager that orchestrates all messaging components including
backends, producers, consumers, routing, middleware, DLQ, and monitoring.
"""

import asyncio
import builtins
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, dict, list

from .backends import BackendConfig, BackendFactory, BackendType, MessageBackend
from .core import (
    ExchangeConfig,
    Message,
    MessageExchange,
    MessagePriority,
    MessageQueue,
    QueueConfig,
)
from .dlq import DLQConfig, DLQManager
from .middleware import MiddlewareChain, MiddlewareStage, MiddlewareType
from .patterns import (
    Consumer,
    ConsumerConfig,
    MessageHandler,
    Producer,
    ProducerConfig,
    PublishSubscribePattern,
    RequestReplyPattern,
    RoutingPattern,
    WorkQueuePattern,
)
from .routing import MessageRouter, RoutingConfig, RoutingEngine, RoutingRule
from .serialization import SerializationConfig, SerializerFactory

logger = logging.getLogger(__name__)


class MessagingState(Enum):
    """Messaging manager states."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class MessagingConfig:
    """Configuration for messaging manager."""

    # Backend configuration
    backend_config: BackendConfig

    # Default settings
    default_serialization: SerializationConfig = field(
        default_factory=SerializationConfig
    )
    default_routing: RoutingConfig = field(default_factory=RoutingConfig)
    default_dlq: DLQConfig = field(default_factory=DLQConfig)

    # Manager settings
    auto_start_consumers: bool = True
    auto_create_queues: bool = True
    auto_create_exchanges: bool = True

    # Performance settings
    max_concurrent_messages: int = 1000
    message_buffer_size: int = 10000
    health_check_interval: float = 30.0

    # Monitoring
    enable_metrics: bool = True
    metrics_interval: float = 60.0
    enable_health_checks: bool = True

    # Error handling
    global_error_handler: Callable[[Exception], None] | None = None
    shutdown_timeout: float = 30.0


class MessagingManager:
    """Comprehensive messaging manager."""

    def __init__(self, config: MessagingConfig):
        self.config = config
        self.state = MessagingState.INITIALIZING

        # Core components
        self.backend: MessageBackend | None = None
        self.router = MessageRouter()
        self.middleware_chain = MiddlewareChain()
        self.dlq_manager: DLQManager | None = None

        # Collections
        self.producers: builtins.dict[str, Producer] = {}
        self.consumers: builtins.dict[str, Consumer] = {}
        self.queues: builtins.dict[str, MessageQueue] = {}
        self.exchanges: builtins.dict[str, MessageExchange] = {}

        # Patterns
        self.request_reply_patterns: builtins.dict[str, RequestReplyPattern] = {}
        self.pubsub_patterns: builtins.dict[str, PublishSubscribePattern] = {}
        self.work_queue_patterns: builtins.dict[str, WorkQueuePattern] = {}
        self.routing_patterns: builtins.dict[str, RoutingPattern] = {}

        # Monitoring and management
        self._health_check_task: asyncio.Task | None = None
        self._metrics_task: asyncio.Task | None = None
        self._message_buffer: builtins.list[Message] = []
        self._processing_semaphore: asyncio.Semaphore | None = None

        # Statistics
        self._stats = {
            "start_time": time.time(),
            "messages_processed": 0,
            "messages_failed": 0,
            "producers_created": 0,
            "consumers_created": 0,
            "queues_created": 0,
            "exchanges_created": 0,
        }

    async def initialize(self):
        """Initialize messaging manager."""
        try:
            self.state = MessagingState.INITIALIZING
            logger.info("Initializing messaging manager")

            # Initialize backend
            self.backend = BackendFactory.create_backend(self.config.backend_config)
            await self.backend.connect()

            # Initialize DLQ manager
            self.dlq_manager = DLQManager(self.config.default_dlq, self.backend)

            # Initialize routing engine
            default_engine = RoutingEngine(self.config.default_routing)
            self.router.add_engine("default", default_engine, is_default=True)

            # Initialize processing semaphore
            self._processing_semaphore = asyncio.Semaphore(
                self.config.max_concurrent_messages
            )

            # Start monitoring tasks
            if self.config.enable_health_checks:
                self._health_check_task = asyncio.create_task(self._health_check_loop())

            if self.config.enable_metrics:
                self._metrics_task = asyncio.create_task(self._metrics_loop())

            self.state = MessagingState.RUNNING
            logger.info("Messaging manager initialized successfully")

        except Exception as e:
            self.state = MessagingState.ERROR
            logger.error("Failed to initialize messaging manager: %s", e)
            if self.config.global_error_handler:
                self.config.global_error_handler(e)
            raise

    async def shutdown(self):
        """Shutdown messaging manager."""
        try:
            self.state = MessagingState.STOPPING
            logger.info("Shutting down messaging manager")

            # Stop all consumers
            for consumer in self.consumers.values():
                await consumer.stop_consuming()

            # Cancel monitoring tasks
            if self._health_check_task:
                self._health_check_task.cancel()
            if self._metrics_task:
                self._metrics_task.cancel()

            # Disconnect all producers
            for producer in self.producers.values():
                await producer.disconnect()

            # Shutdown DLQ manager
            if self.dlq_manager:
                await self.dlq_manager.shutdown()

            # Disconnect backend
            if self.backend:
                await self.backend.disconnect()

            self.state = MessagingState.STOPPED
            logger.info("Messaging manager shutdown complete")

        except Exception as e:
            self.state = MessagingState.ERROR
            logger.error("Error during messaging manager shutdown: %s", e)
            raise

    # Queue Management

    async def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create a message queue."""
        if not self.backend:
            raise RuntimeError("Backend not initialized")

        queue = await self.backend.create_queue(config)
        self.queues[config.name] = queue
        self._stats["queues_created"] += 1

        logger.info("Created queue: %s", config.name)
        return queue

    async def get_or_create_queue(self, config: QueueConfig) -> MessageQueue:
        """Get existing queue or create new one."""
        if config.name in self.queues:
            return self.queues[config.name]

        if self.config.auto_create_queues:
            return await self.create_queue(config)

        raise ValueError(
            f"Queue {config.name} does not exist and auto_create_queues is disabled"
        )

    async def delete_queue(self, queue_name: str, if_empty: bool = False) -> bool:
        """Delete a queue."""
        if queue_name in self.queues:
            queue = self.queues[queue_name]

            if if_empty:
                message_count = await queue.get_message_count()
                if message_count > 0:
                    logger.warning("Cannot delete non-empty queue: %s", queue_name)
                    return False

            # Clean up any associated consumers
            consumers_to_remove = []
            for name, consumer in self.consumers.items():
                if consumer.config.queue == queue_name:
                    consumers_to_remove.append(name)

            for consumer_name in consumers_to_remove:
                await self.remove_consumer(consumer_name)

            del self.queues[queue_name]
            logger.info("Deleted queue: %s", queue_name)
            return True

        return False

    # Exchange Management

    async def create_exchange(self, config: ExchangeConfig) -> MessageExchange:
        """Create a message exchange."""
        if not self.backend:
            raise RuntimeError("Backend not initialized")

        exchange = await self.backend.create_exchange(config)
        self.exchanges[config.name] = exchange
        self._stats["exchanges_created"] += 1

        logger.info("Created exchange: %s", config.name)
        return exchange

    async def get_or_create_exchange(self, config: ExchangeConfig) -> MessageExchange:
        """Get existing exchange or create new one."""
        if config.name in self.exchanges:
            return self.exchanges[config.name]

        if self.config.auto_create_exchanges:
            return await self.create_exchange(config)

        raise ValueError(
            f"Exchange {config.name} does not exist and auto_create_exchanges is disabled"
        )

    # Producer Management

    async def create_producer(self, config: ProducerConfig) -> Producer:
        """Create a message producer."""
        if not self.backend:
            raise RuntimeError("Backend not initialized")

        # Set default serializer if not provided
        if not config.serializer:
            config.serializer = SerializerFactory.create_serializer(
                self.config.default_serialization
            )

        producer = Producer(config, self.backend)
        await producer.connect()

        self.producers[config.name] = producer
        self._stats["producers_created"] += 1

        logger.info("Created producer: %s", config.name)
        return producer

    async def get_producer(self, name: str) -> Producer | None:
        """Get producer by name."""
        return self.producers.get(name)

    async def remove_producer(self, name: str) -> bool:
        """Remove a producer."""
        if name in self.producers:
            producer = self.producers[name]
            await producer.disconnect()
            del self.producers[name]
            logger.info("Removed producer: %s", name)
            return True
        return False

    # Consumer Management

    async def create_consumer(
        self, config: ConsumerConfig, handler: MessageHandler
    ) -> Consumer:
        """Create a message consumer."""
        if not self.backend:
            raise RuntimeError("Backend not initialized")

        # Set default serializer if not provided
        if not config.serializer:
            config.serializer = SerializerFactory.create_serializer(
                self.config.default_serialization
            )

        # Wrap handler with middleware processing
        wrapped_handler = self._wrap_handler_with_middleware(handler)

        consumer = Consumer(config, wrapped_handler, self.backend)
        await consumer.connect()

        if self.config.auto_start_consumers:
            await consumer.start_consuming()

        self.consumers[config.name] = consumer
        self._stats["consumers_created"] += 1

        logger.info("Created consumer: %s", config.name)
        return consumer

    def _wrap_handler_with_middleware(self, handler: MessageHandler) -> MessageHandler:
        """Wrap message handler with middleware processing."""

        class MiddlewareWrappedHandler(MessageHandler):
            def __init__(
                self,
                original_handler: MessageHandler,
                middleware_chain: MiddlewareChain,
            ):
                self.original_handler = original_handler
                self.middleware_chain = middleware_chain

            async def handle(self, message: Message) -> bool:
                try:
                    # Pre-process middleware
                    success = await self.middleware_chain.process(
                        message, MiddlewareStage.PRE_PROCESS, MiddlewareType.INBOUND
                    )

                    if not success:
                        return False

                    # Process message
                    result = await self.original_handler.handle(message)

                    # Post-process middleware
                    await self.middleware_chain.process(
                        message, MiddlewareStage.POST_PROCESS, MiddlewareType.INBOUND
                    )

                    return result

                except Exception as e:
                    # Error middleware
                    await self.middleware_chain.process(
                        message, MiddlewareStage.ON_ERROR, MiddlewareType.INBOUND
                    )
                    await self.original_handler.on_error(message, e)
                    return False

            async def on_error(self, message: Message, error: Exception):
                await self.original_handler.on_error(message, error)

        return MiddlewareWrappedHandler(handler, self.middleware_chain)

    async def get_consumer(self, name: str) -> Consumer | None:
        """Get consumer by name."""
        return self.consumers.get(name)

    async def remove_consumer(self, name: str) -> bool:
        """Remove a consumer."""
        if name in self.consumers:
            consumer = self.consumers[name]
            await consumer.stop_consuming()
            await consumer.disconnect()
            del self.consumers[name]
            logger.info("Removed consumer: %s", name)
            return True
        return False

    # Message Publishing

    async def publish(
        self,
        body: Any,
        routing_key: str = "",
        exchange: str | None = None,
        producer_name: str | None = None,
        headers: builtins.dict[str, Any] | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """Publish a message."""
        # Get or create default producer
        if producer_name:
            producer = self.producers.get(producer_name)
            if not producer:
                raise ValueError(f"Producer {producer_name} not found")
        # Use first available producer or create default
        elif self.producers:
            producer = next(iter(self.producers.values()))
        else:
            # Create default producer
            config = ProducerConfig(
                name="default", routing_key=routing_key, exchange=exchange
            )
            producer = await self.create_producer(config)

        # Create message
        message = Message(body=body)
        message.headers.routing_key = routing_key
        message.headers.exchange = exchange
        message.headers.priority = priority

        if headers:
            message.headers.custom.update(headers)

        # Process through middleware
        success = await self.middleware_chain.process(
            message, MiddlewareStage.PRE_PUBLISH, MiddlewareType.OUTBOUND
        )

        if not success:
            raise RuntimeError("Message failed middleware processing")

        # Route message
        try:
            targets = self.router.route(message)
            if not targets:
                logger.warning("No routing targets found for message %s", message.id)
                return message.id

            # Use first target for routing key
            message.headers.routing_key = targets[0]

        except Exception as e:
            logger.error("Routing failed for message %s: %s", message.id, e)
            # Continue with original routing key

        # Publish message
        message_id = await producer.publish(
            body=message.body,
            routing_key=message.headers.routing_key,
            headers=message.headers.custom,
            priority=message.headers.priority,
            exchange=message.headers.exchange,
        )

        # Post-publish middleware
        await self.middleware_chain.process(
            message, MiddlewareStage.POST_PUBLISH, MiddlewareType.OUTBOUND
        )

        self._stats["messages_processed"] += 1
        return message_id

    # Pattern Management

    def create_request_reply_pattern(
        self, name: str, producer: Producer, consumer: Consumer, timeout: float = 30.0
    ) -> RequestReplyPattern:
        """Create request-reply pattern."""
        pattern = RequestReplyPattern(producer, consumer, timeout)
        self.request_reply_patterns[name] = pattern
        return pattern

    def create_pubsub_pattern(
        self, name: str, producer: Producer, exchange: str
    ) -> PublishSubscribePattern:
        """Create publish-subscribe pattern."""
        pattern = PublishSubscribePattern(producer, exchange)
        self.pubsub_patterns[name] = pattern
        return pattern

    def create_work_queue_pattern(
        self, name: str, producer: Producer, queue: str
    ) -> WorkQueuePattern:
        """Create work queue pattern."""
        pattern = WorkQueuePattern(producer, queue)
        self.work_queue_patterns[name] = pattern
        return pattern

    def create_routing_pattern(
        self, name: str, producer: Producer, exchange: str
    ) -> RoutingPattern:
        """Create routing pattern."""
        pattern = RoutingPattern(producer, exchange)
        self.routing_patterns[name] = pattern
        return pattern

    # Routing Management

    def add_routing_rule(self, engine_name: str, rule: RoutingRule):
        """Add routing rule to engine."""
        engine = self.router.get_engine(engine_name)
        if engine:
            engine.add_rule(rule)
        else:
            raise ValueError(f"Routing engine {engine_name} not found")

    def add_routing_engine(
        self, name: str, config: RoutingConfig, is_default: bool = False
    ):
        """Add routing engine."""
        engine = RoutingEngine(config)
        self.router.add_engine(name, engine, is_default)

    # Health Monitoring

    async def _health_check_loop(self):
        """Background health check loop."""
        while self.state == MessagingState.RUNNING:
            try:
                await self._perform_health_check()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check error: %s", e)
                await asyncio.sleep(self.config.health_check_interval)

    async def _perform_health_check(self):
        """Perform health check."""
        if self.backend and not self.backend.is_connected:
            logger.warning("Backend connection lost, attempting reconnection")
            try:
                await self.backend.connect()
                logger.info("Backend reconnected successfully")
            except Exception as e:
                logger.error("Backend reconnection failed: %s", e)

    async def _metrics_loop(self):
        """Background metrics collection loop."""
        while self.state == MessagingState.RUNNING:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.config.metrics_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Metrics collection error: %s", e)
                await asyncio.sleep(self.config.metrics_interval)

    async def _collect_metrics(self):
        """Collect system metrics."""
        # This would integrate with your metrics system
        logger.debug("Collecting messaging metrics")

    # Statistics and Monitoring

    def get_comprehensive_stats(self) -> builtins.dict[str, Any]:
        """Get comprehensive system statistics."""
        uptime = time.time() - self._stats["start_time"]

        producer_stats = {}
        for name, producer in self.producers.items():
            producer_stats[name] = producer.get_stats()

        consumer_stats = {}
        for name, consumer in self.consumers.items():
            consumer_stats[name] = consumer.get_stats()

        routing_stats = self.router.get_all_stats()
        middleware_stats = self.middleware_chain.get_middleware_stats()

        dlq_stats = None
        if self.dlq_manager:
            dlq_stats = self.dlq_manager.get_stats()

        return {
            "manager": {
                "state": self.state.value,
                "uptime": uptime,
                "backend_type": self.config.backend_config.backend_type.value,
                "backend_connected": self.backend.is_connected
                if self.backend
                else False,
                **self._stats,
            },
            "producers": producer_stats,
            "consumers": consumer_stats,
            "queues": {name: {"name": name} for name in self.queues.keys()},
            "exchanges": {name: {"name": name} for name in self.exchanges.keys()},
            "routing": routing_stats,
            "middleware": middleware_stats,
            "dlq": dlq_stats.__dict__ if dlq_stats else None,
            "patterns": {
                "request_reply": len(self.request_reply_patterns),
                "pubsub": len(self.pubsub_patterns),
                "work_queue": len(self.work_queue_patterns),
                "routing": len(self.routing_patterns),
            },
        }

    def get_health_status(self) -> builtins.dict[str, Any]:
        """Get health status."""
        healthy = True
        issues = []

        if self.state != MessagingState.RUNNING:
            healthy = False
            issues.append(f"Manager state is {self.state.value}")

        if not self.backend or not self.backend.is_connected:
            healthy = False
            issues.append("Backend not connected")

        # Check consumer health
        unhealthy_consumers = []
        for name, consumer in self.consumers.items():
            if not consumer._connected:
                unhealthy_consumers.append(name)

        if unhealthy_consumers:
            healthy = False
            issues.append(f"Disconnected consumers: {unhealthy_consumers}")

        return {
            "healthy": healthy,
            "state": self.state.value,
            "uptime": time.time() - self._stats["start_time"],
            "issues": issues,
            "component_count": {
                "producers": len(self.producers),
                "consumers": len(self.consumers),
                "queues": len(self.queues),
                "exchanges": len(self.exchanges),
            },
        }


# Context manager for messaging manager
class MessagingContext:
    """Context manager for messaging manager lifecycle."""

    def __init__(self, config: MessagingConfig):
        self.config = config
        self.manager: MessagingManager | None = None

    async def __aenter__(self) -> MessagingManager:
        """Enter context and initialize manager."""
        self.manager = MessagingManager(self.config)
        await self.manager.initialize()
        return self.manager

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context and shutdown manager."""
        if self.manager:
            await self.manager.shutdown()


# Utility functions


async def create_simple_messaging_manager(
    backend_type: BackendType = BackendType.MEMORY,
    host: str = "localhost",
    port: int = 5672,
) -> MessagingManager:
    """Create a simple messaging manager with default settings."""
    backend_config = BackendConfig(backend_type=backend_type, host=host, port=port)

    messaging_config = MessagingConfig(backend_config=backend_config)
    manager = MessagingManager(messaging_config)
    await manager.initialize()
    return manager


def create_messaging_config_from_dict(
    config_dict: builtins.dict[str, Any]
) -> MessagingConfig:
    """Create messaging config from dictionary."""
    backend_config = BackendConfig(**config_dict.get("backend", {}))

    messaging_config = MessagingConfig(
        backend_config=backend_config,
        **{k: v for k, v in config_dict.items() if k != "backend"},
    )

    return messaging_config
