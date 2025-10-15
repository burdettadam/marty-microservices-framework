"""
Unified Event Bus Implementation

Provides a unified interface for all messaging patterns across different backends.
Automatically selects appropriate backends and patterns based on use case requirements.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from .extended_architecture import (
    DeliveryGuarantee,
    EnhancedMessageBackend,
    GenericMessage,
    MessageBackendType,
    MessageMetadata,
    MessagingPattern,
    MessagingPatternConfig,
    PatternSelector,
    UnifiedEventBus,
)

logger = logging.getLogger(__name__)


class DefaultMessage(GenericMessage):
    """Default message implementation for unified event bus."""

    def __init__(self, payload: Any, metadata: MessageMetadata, pattern: MessagingPattern):
        super().__init__(payload, metadata, pattern)

    async def ack(self) -> bool:
        """Default acknowledge implementation."""
        self._acknowledged = True
        return True

    async def nack(self, requeue: bool = True) -> bool:
        """Default negative acknowledge implementation."""
        return True

    async def reject(self, requeue: bool = False) -> bool:
        """Default reject implementation."""
        return True


class UnifiedEventBusImpl(UnifiedEventBus):
    """Implementation of unified event bus supporting all messaging patterns."""

    def __init__(self):
        self._backends: dict[MessageBackendType, EnhancedMessageBackend] = {}
        self._default_backend_type = MessageBackendType.MEMORY
        self._pattern_configs: dict[MessagingPattern, MessagingPatternConfig] = {}
        self._subscriptions: dict[str, dict] = {}  # subscription_id -> subscription_info
        self._running = False

        # Initialize default pattern configurations
        self._setup_default_patterns()

    def _setup_default_patterns(self):
        """Setup default pattern configurations."""
        self._pattern_configs = {
            MessagingPattern.PUBLISH_SUBSCRIBE: MessagingPatternConfig(
                pattern=MessagingPattern.PUBLISH_SUBSCRIBE,
                delivery_guarantee=DeliveryGuarantee.AT_LEAST_ONCE,
                timeout=timedelta(seconds=30),
                retry_count=3,
                dead_letter_enabled=True
            ),
            MessagingPattern.REQUEST_RESPONSE: MessagingPatternConfig(
                pattern=MessagingPattern.REQUEST_RESPONSE,
                delivery_guarantee=DeliveryGuarantee.AT_LEAST_ONCE,
                timeout=timedelta(seconds=30),
                retry_count=3,
                dead_letter_enabled=False
            ),
            MessagingPattern.STREAM_PROCESSING: MessagingPatternConfig(
                pattern=MessagingPattern.STREAM_PROCESSING,
                delivery_guarantee=DeliveryGuarantee.AT_LEAST_ONCE,
                timeout=timedelta(minutes=5),
                retry_count=5,
                dead_letter_enabled=True,
                ordering_enabled=True
            ),
            MessagingPattern.POINT_TO_POINT: MessagingPatternConfig(
                pattern=MessagingPattern.POINT_TO_POINT,
                delivery_guarantee=DeliveryGuarantee.AT_LEAST_ONCE,
                timeout=timedelta(seconds=60),
                retry_count=3,
                dead_letter_enabled=True
            ),
            MessagingPattern.BROADCAST: MessagingPatternConfig(
                pattern=MessagingPattern.BROADCAST,
                delivery_guarantee=DeliveryGuarantee.AT_MOST_ONCE,
                timeout=timedelta(seconds=10),
                retry_count=1,
                dead_letter_enabled=False
            )
        }

    def register_backend(self, backend_type: MessageBackendType, backend: EnhancedMessageBackend):
        """Register a messaging backend."""
        self._backends[backend_type] = backend
        logger.info(f"Registered backend: {backend_type}")

    def set_default_backend(self, backend_type: MessageBackendType):
        """Set default backend for messaging operations."""
        if backend_type not in self._backends:
            raise ValueError(f"Backend {backend_type} not registered")
        self._default_backend_type = backend_type
        logger.info(f"Set default backend to: {backend_type}")

    def update_pattern_config(self, pattern: MessagingPattern, config: MessagingPatternConfig):
        """Update configuration for a messaging pattern."""
        self._pattern_configs[pattern] = config

    async def start(self):
        """Start the unified event bus."""
        if self._running:
            return

        # Connect all registered backends
        connection_tasks = []
        for backend_type, backend in self._backends.items():
            task = asyncio.create_task(self._connect_backend(backend_type, backend))
            connection_tasks.append(task)

        if connection_tasks:
            await asyncio.gather(*connection_tasks, return_exceptions=True)

        self._running = True
        logger.info("Unified event bus started")

    async def stop(self):
        """Stop the unified event bus."""
        if not self._running:
            return

        # Disconnect all backends
        disconnection_tasks = []
        for backend_type, backend in self._backends.items():
            task = asyncio.create_task(self._disconnect_backend(backend_type, backend))
            disconnection_tasks.append(task)

        if disconnection_tasks:
            await asyncio.gather(*disconnection_tasks, return_exceptions=True)

        self._running = False
        logger.info("Unified event bus stopped")

    async def _connect_backend(self, backend_type: MessageBackendType, backend: EnhancedMessageBackend):
        """Connect a specific backend."""
        try:
            success = await backend.connect()
            if success:
                logger.info(f"Connected backend: {backend_type}")
            else:
                logger.error(f"Failed to connect backend: {backend_type}")
        except Exception as e:
            logger.error(f"Error connecting backend {backend_type}: {e}")

    async def _disconnect_backend(self, backend_type: MessageBackendType, backend: EnhancedMessageBackend):
        """Disconnect a specific backend."""
        try:
            success = await backend.disconnect()
            if success:
                logger.info(f"Disconnected backend: {backend_type}")
            else:
                logger.error(f"Failed to disconnect backend: {backend_type}")
        except Exception as e:
            logger.error(f"Error disconnecting backend {backend_type}: {e}")

    def _select_backend(self, pattern: MessagingPattern, topic: str = "") -> EnhancedMessageBackend:
        """Select appropriate backend for the messaging pattern."""
        # Smart backend selection based on pattern and availability
        recommended_type = PatternSelector.recommend_backend(pattern)

        # Try recommended backend first
        if recommended_type in self._backends:
            backend = self._backends[recommended_type]
            if backend.supports_pattern(pattern):
                return backend

        # Fall back to any backend that supports the pattern
        for _backend_type, backend in self._backends.items():
            if backend.supports_pattern(pattern):
                return backend

        # Last resort: use default backend
        if self._default_backend_type in self._backends:
            return self._backends[self._default_backend_type]

        raise RuntimeError(f"No backend available for pattern: {pattern}")

    def _create_message(self, data: Any, metadata: MessageMetadata, pattern: MessagingPattern) -> GenericMessage:
        """Create a generic message."""
        return DefaultMessage(payload=data, metadata=metadata, pattern=pattern)

    async def publish_event(self,
                           event_type: str,
                           data: Any,
                           metadata: MessageMetadata | None = None) -> bool:
        """Publish domain event (pub/sub pattern)."""
        if not self._running:
            logger.error("Event bus not started")
            return False

        try:
            if metadata is None:
                metadata = MessageMetadata(
                    message_id=str(uuid.uuid4()),
                    message_type=event_type,
                    timestamp=datetime.utcnow()
                )

            pattern = MessagingPattern.PUBLISH_SUBSCRIBE
            backend = self._select_backend(pattern)
            pattern_config = self._pattern_configs[pattern]

            message = self._create_message(data, metadata, pattern)

            # Use event type as topic
            topic = f"events.{event_type}"
            success = await backend.publish(topic, message, pattern_config)

            if success:
                logger.debug(f"Published event: {event_type}")
            else:
                logger.error(f"Failed to publish event: {event_type}")

            return success

        except Exception as e:
            logger.error(f"Error publishing event {event_type}: {e}")
            return False

    async def send_command(self,
                          command_type: str,
                          data: Any,
                          target_service: str,
                          metadata: MessageMetadata | None = None) -> bool:
        """Send command (point-to-point pattern)."""
        if not self._running:
            logger.error("Event bus not started")
            return False

        try:
            if metadata is None:
                metadata = MessageMetadata(
                    message_id=str(uuid.uuid4()),
                    message_type=command_type,
                    timestamp=datetime.utcnow()
                )

            pattern = MessagingPattern.POINT_TO_POINT
            backend = self._select_backend(pattern)
            pattern_config = self._pattern_configs[pattern]

            message = self._create_message(data, metadata, pattern)

            # Use service-specific topic
            topic = f"commands.{target_service}.{command_type}"
            success = await backend.publish(topic, message, pattern_config)

            if success:
                logger.debug(f"Sent command: {command_type} to {target_service}")
            else:
                logger.error(f"Failed to send command: {command_type} to {target_service}")

            return success

        except Exception as e:
            logger.error(f"Error sending command {command_type} to {target_service}: {e}")
            return False

    async def query(self,
                   query_type: str,
                   data: Any,
                   target_service: str,
                   timeout: timedelta = timedelta(seconds=30)) -> Any:
        """Send query and wait for response (request/response pattern)."""
        if not self._running:
            logger.error("Event bus not started")
            return None

        try:
            metadata = MessageMetadata(
                message_id=str(uuid.uuid4()),
                message_type=query_type,
                timestamp=datetime.utcnow()
            )

            pattern = MessagingPattern.REQUEST_RESPONSE
            backend = self._select_backend(pattern)

            message = self._create_message(data, metadata, pattern)

            # Use service-specific topic
            topic = f"queries.{target_service}.{query_type}"
            response_message = await backend.request(topic, message, timeout)

            logger.debug(f"Received query response: {query_type} from {target_service}")
            return response_message.payload

        except Exception as e:
            logger.error(f"Error sending query {query_type} to {target_service}: {e}")
            return None

    async def stream_events(self,
                           stream_name: str,
                           events: list[Any],
                           partition_key: str | None = None) -> bool:
        """Stream events for processing (streaming pattern)."""
        if not self._running:
            logger.error("Event bus not started")
            return False

        try:
            pattern = MessagingPattern.STREAM_PROCESSING
            backend = self._select_backend(pattern, stream_name)
            pattern_config = self._pattern_configs[pattern]

            success_count = 0
            for event in events:
                metadata = MessageMetadata(
                    message_id=str(uuid.uuid4()),
                    timestamp=datetime.utcnow(),
                    routing_key=partition_key
                )

                message = self._create_message(event, metadata, pattern)

                if await backend.publish(stream_name, message, pattern_config):
                    success_count += 1

            logger.debug(f"Streamed {success_count}/{len(events)} events to {stream_name}")
            return success_count == len(events)

        except Exception as e:
            logger.error(f"Error streaming events to {stream_name}: {e}")
            return False

    async def subscribe_to_events(self,
                                 event_types: list[str],
                                 handler: Callable[[str, Any, MessageMetadata], Awaitable[bool]],
                                 consumer_group: str | None = None) -> str:
        """Subscribe to domain events."""
        if not self._running:
            logger.error("Event bus not started")
            return ""

        try:
            pattern = MessagingPattern.PUBLISH_SUBSCRIBE
            backend = self._select_backend(pattern)
            pattern_config = self._pattern_configs[pattern]

            subscription_id = str(uuid.uuid4())

            async def message_handler(message: GenericMessage) -> bool:
                try:
                    # Extract event type from topic or metadata
                    event_type = message.metadata.message_type or "unknown"
                    return await handler(event_type, message.payload, message.metadata)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")
                    return False

            # Subscribe to each event type
            backend_subscriptions = []
            for event_type in event_types:
                topic = f"events.{event_type}"
                backend_sub_id = await backend.subscribe(topic, message_handler, pattern_config)
                if backend_sub_id:
                    backend_subscriptions.append(backend_sub_id)

            if backend_subscriptions:
                self._subscriptions[subscription_id] = {
                    "backend": backend,
                    "backend_subscriptions": backend_subscriptions,
                    "event_types": event_types,
                    "consumer_group": consumer_group
                }
                logger.info(f"Subscribed to events: {event_types}")
                return subscription_id
            else:
                logger.error(f"Failed to subscribe to events: {event_types}")
                return ""

        except Exception as e:
            logger.error(f"Error subscribing to events {event_types}: {e}")
            return ""

    async def handle_commands(self,
                             command_types: list[str],
                             handler: Callable[[str, Any, MessageMetadata], Awaitable[bool]],
                             service_name: str) -> str:
        """Handle incoming commands."""
        if not self._running:
            logger.error("Event bus not started")
            return ""

        try:
            pattern = MessagingPattern.POINT_TO_POINT
            backend = self._select_backend(pattern)
            pattern_config = self._pattern_configs[pattern]

            subscription_id = str(uuid.uuid4())

            async def message_handler(message: GenericMessage) -> bool:
                try:
                    command_type = message.metadata.message_type or "unknown"
                    return await handler(command_type, message.payload, message.metadata)
                except Exception as e:
                    logger.error(f"Error in command handler: {e}")
                    return False

            # Subscribe to each command type
            backend_subscriptions = []
            for command_type in command_types:
                topic = f"commands.{service_name}.{command_type}"
                backend_sub_id = await backend.subscribe(topic, message_handler, pattern_config)
                if backend_sub_id:
                    backend_subscriptions.append(backend_sub_id)

            if backend_subscriptions:
                self._subscriptions[subscription_id] = {
                    "backend": backend,
                    "backend_subscriptions": backend_subscriptions,
                    "command_types": command_types,
                    "service_name": service_name
                }
                logger.info(f"Handling commands: {command_types} for service: {service_name}")
                return subscription_id
            else:
                logger.error(f"Failed to handle commands: {command_types}")
                return ""

        except Exception as e:
            logger.error(f"Error handling commands {command_types}: {e}")
            return ""

    async def handle_queries(self,
                            query_types: list[str],
                            handler: Callable[[str, Any, MessageMetadata], Awaitable[Any]],
                            service_name: str) -> str:
        """Handle incoming queries."""
        if not self._running:
            logger.error("Event bus not started")
            return ""

        try:
            pattern = MessagingPattern.REQUEST_RESPONSE
            backend = self._select_backend(pattern)
            pattern_config = self._pattern_configs[pattern]

            subscription_id = str(uuid.uuid4())

            async def message_handler(message: GenericMessage) -> bool:
                try:
                    query_type = message.metadata.message_type or "unknown"
                    response_data = await handler(query_type, message.payload, message.metadata)

                    # Send response back
                    response_metadata = MessageMetadata(
                        message_id=str(uuid.uuid4()),
                        correlation_id=message.metadata.correlation_id,
                        causation_id=message.metadata.message_id,
                        timestamp=datetime.utcnow()
                    )

                    response_message = self._create_message(
                        response_data,
                        response_metadata,
                        MessagingPattern.REQUEST_RESPONSE
                    )

                    await backend.reply(message, response_message)
                    return True

                except Exception as e:
                    logger.error(f"Error in query handler: {e}")
                    return False

            # Subscribe to each query type
            backend_subscriptions = []
            for query_type in query_types:
                topic = f"queries.{service_name}.{query_type}"
                backend_sub_id = await backend.subscribe(topic, message_handler, pattern_config)
                if backend_sub_id:
                    backend_subscriptions.append(backend_sub_id)

            if backend_subscriptions:
                self._subscriptions[subscription_id] = {
                    "backend": backend,
                    "backend_subscriptions": backend_subscriptions,
                    "query_types": query_types,
                    "service_name": service_name
                }
                logger.info(f"Handling queries: {query_types} for service: {service_name}")
                return subscription_id
            else:
                logger.error(f"Failed to handle queries: {query_types}")
                return ""

        except Exception as e:
            logger.error(f"Error handling queries {query_types}: {e}")
            return ""

    async def process_stream(self,
                            stream_name: str,
                            processor: Callable[[list[Any]], Awaitable[bool]],
                            consumer_group: str,
                            batch_size: int = 100) -> str:
        """Process event stream."""
        if not self._running:
            logger.error("Event bus not started")
            return ""

        try:
            pattern = MessagingPattern.STREAM_PROCESSING
            backend = self._select_backend(pattern, stream_name)
            pattern_config = self._pattern_configs[pattern]

            subscription_id = str(uuid.uuid4())

            # For stream processing, we need to implement batching logic
            message_batch = []
            batch_lock = asyncio.Lock()

            async def message_handler(message: GenericMessage) -> bool:
                async with batch_lock:
                    message_batch.append(message.payload)

                    if len(message_batch) >= batch_size:
                        # Process batch
                        try:
                            batch_data = message_batch.copy()
                            message_batch.clear()
                            success = await processor(batch_data)
                            return success
                        except Exception as e:
                            logger.error(f"Error processing stream batch: {e}")
                            return False

                return True

            # Subscribe to stream
            backend_sub_id = await backend.subscribe(stream_name, message_handler, pattern_config)

            if backend_sub_id:
                self._subscriptions[subscription_id] = {
                    "backend": backend,
                    "backend_subscriptions": [backend_sub_id],
                    "stream_name": stream_name,
                    "consumer_group": consumer_group,
                    "batch_size": batch_size
                }
                logger.info(f"Processing stream: {stream_name} with batch size: {batch_size}")
                return subscription_id
            else:
                logger.error(f"Failed to process stream: {stream_name}")
                return ""

        except Exception as e:
            logger.error(f"Error processing stream {stream_name}: {e}")
            return ""

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from a subscription."""
        if subscription_id not in self._subscriptions:
            return False

        try:
            subscription_info = self._subscriptions[subscription_id]
            backend = subscription_info["backend"]

            # Unsubscribe from all backend subscriptions
            for backend_sub_id in subscription_info["backend_subscriptions"]:
                await backend.unsubscribe(backend_sub_id)

            del self._subscriptions[subscription_id]
            logger.info(f"Unsubscribed: {subscription_id}")
            return True

        except Exception as e:
            logger.error(f"Error unsubscribing {subscription_id}: {e}")
            return False


def create_unified_event_bus() -> UnifiedEventBusImpl:
    """Factory function to create unified event bus."""
    return UnifiedEventBusImpl()
