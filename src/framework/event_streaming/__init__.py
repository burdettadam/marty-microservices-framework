"""
Event Streaming Framework Module

Advanced event streaming capabilities with event sourcing, CQRS patterns,
saga orchestration, and comprehensive event management for microservices.
"""

# Configuration and factory
from .config import EventStoreConfig, EventStreamingConfig, KafkaConfig, SagaConfig

# Core event abstractions
from .core import (
    Event,
    EventBus,
    EventDispatcher,
    EventHandler,
    EventMetadata,
    EventSerializer,
    EventStore,
    EventStream,
)

# CQRS components
from .cqrs import (
    Command,
    CommandBus,
    CommandHandler,
    CQRSEngine,
    Projection,
    ProjectionHandler,
    Query,
    QueryBus,
    QueryHandler,
    ReadModel,
)

# Dead letter and error handling
from .error_handling import (
    DeadLetterQueue,
    ErrorClassifier,
    ErrorHandler,
    EventRecovery,
    RetryPolicy,
)

# Event sourcing components
from .event_sourcing import (
    Aggregate,
    AggregateRoot,
    EventSourcedRepository,
    EventSourcingEngine,
    Snapshot,
    SnapshotStore,
)
from .factory import (
    EventStreamingFactory,
    create_cqrs_engine,
    create_event_bus,
    create_event_store,
    create_saga_orchestrator,
)

# Kafka integration
from .kafka_integration import (
    KafkaConnector,
    KafkaConsumerGroup,
    KafkaEventBus,
    KafkaEventStore,
    KafkaProducer,
    KafkaStreams,
)

# Monitoring and observability
from .monitoring import (
    EventLogger,
    EventMetrics,
    EventTracing,
    PerformanceMonitor,
    StreamingDashboard,
)

# Event replay and time travel
from .replay import (
    EventProjector,
    EventReplay,
    ReplayEngine,
    StateReconstruction,
    TimeTravel,
)

# Saga orchestration
from .saga import (
    CompensationAction,
    Saga,
    SagaManager,
    SagaOrchestrator,
    SagaRepository,
    SagaState,
    SagaStep,
)

# Event versioning and schema
from .versioning import (
    EventMigration,
    EventSchema,
    EventVersion,
    SchemaEvolution,
    SchemaRegistry,
    VersionManager,
)

__all__ = [
    # Event Sourcing
    "Aggregate",
    "AggregateRoot",
    "CQRSEngine",
    # CQRS
    "Command",
    "CommandBus",
    "CommandHandler",
    "CompensationAction",
    # Error Handling
    "DeadLetterQueue",
    "ErrorClassifier",
    "ErrorHandler",
    # Core
    "Event",
    "EventBus",
    "EventDispatcher",
    "EventHandler",
    "EventLogger",
    "EventMetadata",
    # Monitoring
    "EventMetrics",
    "EventMigration",
    "EventProjector",
    "EventRecovery",
    # Replay
    "EventReplay",
    "EventSchema",
    "EventSerializer",
    "EventSourcedRepository",
    "EventSourcingEngine",
    "EventStore",
    "EventStoreConfig",
    "EventStream",
    # Config & Factory
    "EventStreamingConfig",
    "EventStreamingFactory",
    "EventTracing",
    # Versioning
    "EventVersion",
    "KafkaConfig",
    "KafkaConnector",
    "KafkaConsumerGroup",
    "KafkaEventBus",
    # Kafka
    "KafkaEventStore",
    "KafkaProducer",
    "KafkaStreams",
    "PerformanceMonitor",
    "Projection",
    "ProjectionHandler",
    "Query",
    "QueryBus",
    "QueryHandler",
    "ReadModel",
    "ReplayEngine",
    "RetryPolicy",
    # Saga
    "Saga",
    "SagaConfig",
    "SagaManager",
    "SagaOrchestrator",
    "SagaRepository",
    "SagaState",
    "SagaStep",
    "SchemaEvolution",
    "SchemaRegistry",
    "Snapshot",
    "SnapshotStore",
    "StateReconstruction",
    "StreamingDashboard",
    "TimeTravel",
    "VersionManager",
    "create_cqrs_engine",
    "create_event_bus",
    "create_event_store",
    "create_saga_orchestrator",
]
