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
    # Core
    "Event",
    "EventMetadata",
    "EventStore",
    "EventStream",
    "EventBus",
    "EventHandler",
    "EventDispatcher",
    "EventSerializer",
    # Event Sourcing
    "Aggregate",
    "AggregateRoot",
    "EventSourcedRepository",
    "Snapshot",
    "SnapshotStore",
    "EventSourcingEngine",
    # CQRS
    "Command",
    "Query",
    "CommandHandler",
    "QueryHandler",
    "CommandBus",
    "QueryBus",
    "Projection",
    "ProjectionHandler",
    "ReadModel",
    "CQRSEngine",
    # Saga
    "Saga",
    "SagaStep",
    "SagaOrchestrator",
    "SagaManager",
    "CompensationAction",
    "SagaState",
    "SagaRepository",
    # Versioning
    "EventVersion",
    "EventSchema",
    "SchemaRegistry",
    "EventMigration",
    "VersionManager",
    "SchemaEvolution",
    # Error Handling
    "DeadLetterQueue",
    "ErrorHandler",
    "RetryPolicy",
    "ErrorClassifier",
    "EventRecovery",
    # Replay
    "EventReplay",
    "TimeTravel",
    "ReplayEngine",
    "EventProjector",
    "StateReconstruction",
    # Kafka
    "KafkaEventStore",
    "KafkaEventBus",
    "KafkaConsumerGroup",
    "KafkaProducer",
    "KafkaStreams",
    "KafkaConnector",
    # Monitoring
    "EventMetrics",
    "EventTracing",
    "EventLogger",
    "StreamingDashboard",
    "PerformanceMonitor",
    # Config & Factory
    "EventStreamingConfig",
    "EventStoreConfig",
    "SagaConfig",
    "KafkaConfig",
    "EventStreamingFactory",
    "create_event_store",
    "create_event_bus",
    "create_saga_orchestrator",
    "create_cqrs_engine",
]
