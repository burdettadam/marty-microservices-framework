"""
Advanced Data Management Patterns for Marty Microservices Framework

This module implements sophisticated data management patterns including event sourcing,
CQRS, distributed transactions, saga patterns, and data consistency strategies.
"""

import asyncio
import copy
import hashlib
import json
import logging

# For database operations
import sqlite3
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

import redis
from pymongo import MongoClient


class EventType(Enum):
    """Event types for event sourcing."""

    DOMAIN_EVENT = "domain_event"
    INTEGRATION_EVENT = "integration_event"
    SYSTEM_EVENT = "system_event"
    FAILURE_EVENT = "failure_event"
    COMPENSATION_EVENT = "compensation_event"


class TransactionState(Enum):
    """Distributed transaction states."""

    STARTED = "started"
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ABORTING = "aborting"
    ABORTED = "aborted"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SagaState(Enum):
    """Saga execution states."""

    CREATED = "created"
    EXECUTING = "executing"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


class ConsistencyLevel(Enum):
    """Data consistency levels."""

    STRONG = "strong"
    EVENTUAL = "eventual"
    WEAK = "weak"
    SESSION = "session"
    BOUNDED_STALENESS = "bounded_staleness"


T = TypeVar("T")


@dataclass
class DomainEvent:
    """Domain event for event sourcing."""

    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    version: int
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainEvent":
        """Create event from dictionary."""
        data = data.copy()
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class EventStream:
    """Event stream for aggregate."""

    aggregate_id: str
    aggregate_type: str
    events: List[DomainEvent] = field(default_factory=list)
    version: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Snapshot:
    """Aggregate snapshot for optimization."""

    snapshot_id: str
    aggregate_id: str
    aggregate_type: str
    version: int
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Command:
    """Command for CQRS pattern."""

    command_id: str
    command_type: str
    aggregate_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expected_version: Optional[int] = None


@dataclass
class Query:
    """Query for CQRS pattern."""

    query_id: str
    query_type: str
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReadModel:
    """Read model for CQRS."""

    model_id: str
    model_type: str
    data: Dict[str, Any]
    version: int
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TransactionParticipant:
    """Participant in distributed transaction."""

    participant_id: str
    service_name: str
    endpoint: str
    resource_manager: str
    timeout: int = 30
    retries: int = 3


@dataclass
class DistributedTransaction:
    """Distributed transaction definition."""

    transaction_id: str
    coordinator: str
    participants: List[TransactionParticipant]
    state: TransactionState = TransactionState.STARTED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timeout: int = 300  # seconds
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SagaStep:
    """Step in a saga transaction."""

    step_id: str
    step_name: str
    service_name: str
    action: str  # forward action
    compensation: str  # compensation action
    timeout: int = 30
    retries: int = 3
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SagaTransaction:
    """Saga transaction definition."""

    saga_id: str
    saga_type: str
    steps: List[SagaStep]
    state: SagaState = SagaState.CREATED
    current_step: int = 0
    completed_steps: List[str] = field(default_factory=list)
    compensated_steps: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventStore(ABC):
    """Abstract event store interface."""

    @abstractmethod
    async def append_events(
        self, aggregate_id: str, events: List[DomainEvent], expected_version: int
    ) -> bool:
        """Append events to aggregate stream."""
        pass

    @abstractmethod
    async def get_events(
        self, aggregate_id: str, from_version: int = 0
    ) -> List[DomainEvent]:
        """Get events for aggregate."""
        pass

    @abstractmethod
    async def get_events_by_type(
        self, event_type: str, from_timestamp: Optional[datetime] = None
    ) -> List[DomainEvent]:
        """Get events by type."""
        pass

    @abstractmethod
    async def save_snapshot(self, snapshot: Snapshot) -> bool:
        """Save aggregate snapshot."""
        pass

    @abstractmethod
    async def get_snapshot(self, aggregate_id: str) -> Optional[Snapshot]:
        """Get latest snapshot for aggregate."""
        pass


class InMemoryEventStore(EventStore):
    """In-memory event store implementation."""

    def __init__(self):
        """Initialize in-memory event store."""
        self.event_streams: Dict[str, EventStream] = {}
        self.snapshots: Dict[str, Snapshot] = {}
        self.event_index: Dict[str, List[DomainEvent]] = defaultdict(list)
        self._lock = threading.RLock()

    async def append_events(
        self, aggregate_id: str, events: List[DomainEvent], expected_version: int
    ) -> bool:
        """Append events to aggregate stream."""
        with self._lock:
            if aggregate_id not in self.event_streams:
                self.event_streams[aggregate_id] = EventStream(
                    aggregate_id=aggregate_id,
                    aggregate_type=events[0].aggregate_type if events else "unknown",
                )

            stream = self.event_streams[aggregate_id]

            # Check expected version
            if stream.version != expected_version:
                return False

            # Append events
            for event in events:
                event.version = stream.version + 1
                stream.events.append(event)
                stream.version += 1

                # Update event index
                self.event_index[event.event_type].append(event)

            stream.updated_at = datetime.now(timezone.utc)
            return True

    async def get_events(
        self, aggregate_id: str, from_version: int = 0
    ) -> List[DomainEvent]:
        """Get events for aggregate."""
        with self._lock:
            if aggregate_id not in self.event_streams:
                return []

            stream = self.event_streams[aggregate_id]
            return [event for event in stream.events if event.version > from_version]

    async def get_events_by_type(
        self, event_type: str, from_timestamp: Optional[datetime] = None
    ) -> List[DomainEvent]:
        """Get events by type."""
        with self._lock:
            events = self.event_index.get(event_type, [])

            if from_timestamp:
                events = [
                    event for event in events if event.timestamp >= from_timestamp
                ]

            return events

    async def save_snapshot(self, snapshot: Snapshot) -> bool:
        """Save aggregate snapshot."""
        with self._lock:
            self.snapshots[snapshot.aggregate_id] = snapshot
            return True

    async def get_snapshot(self, aggregate_id: str) -> Optional[Snapshot]:
        """Get latest snapshot for aggregate."""
        with self._lock:
            return self.snapshots.get(aggregate_id)


class AggregateRoot(ABC):
    """Base class for aggregate roots."""

    def __init__(self, aggregate_id: str):
        """Initialize aggregate root."""
        self.aggregate_id = aggregate_id
        self.version = 0
        self.uncommitted_events: List[DomainEvent] = []

    def apply_event(self, event: DomainEvent):
        """Apply event to aggregate."""
        self._apply_event(event)
        self.version = event.version

    def raise_event(
        self, event_type: str, data: Dict[str, Any], metadata: Dict[str, Any] = None
    ):
        """Raise new domain event."""
        event = DomainEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_id=self.aggregate_id,
            aggregate_type=self.__class__.__name__,
            version=self.version + 1,
            data=data,
            metadata=metadata or {},
        )

        self.uncommitted_events.append(event)
        self.apply_event(event)

    def get_uncommitted_events(self) -> List[DomainEvent]:
        """Get uncommitted events."""
        return self.uncommitted_events.copy()

    def mark_events_as_committed(self):
        """Mark events as committed."""
        self.uncommitted_events.clear()

    @abstractmethod
    def _apply_event(self, event: DomainEvent):
        """Apply specific event to aggregate state."""
        pass

    @abstractmethod
    def create_snapshot(self) -> Dict[str, Any]:
        """Create snapshot of aggregate state."""
        pass

    @abstractmethod
    def restore_from_snapshot(self, snapshot_data: Dict[str, Any]):
        """Restore aggregate from snapshot."""
        pass


class Repository(ABC, Generic[T]):
    """Abstract repository interface."""

    @abstractmethod
    async def get_by_id(self, aggregate_id: str) -> Optional[T]:
        """Get aggregate by ID."""
        pass

    @abstractmethod
    async def save(self, aggregate: T) -> bool:
        """Save aggregate."""
        pass

    @abstractmethod
    async def delete(self, aggregate_id: str) -> bool:
        """Delete aggregate."""
        pass


class EventSourcingRepository(Repository[T]):
    """Event sourcing repository implementation."""

    def __init__(
        self,
        event_store: EventStore,
        aggregate_class: type,
        snapshot_frequency: int = 10,
    ):
        """Initialize event sourcing repository."""
        self.event_store = event_store
        self.aggregate_class = aggregate_class
        self.snapshot_frequency = snapshot_frequency

    async def get_by_id(self, aggregate_id: str) -> Optional[T]:
        """Get aggregate by ID using event sourcing."""
        # Try to get snapshot first
        snapshot = await self.event_store.get_snapshot(aggregate_id)

        if snapshot:
            # Restore from snapshot
            aggregate = self.aggregate_class(aggregate_id)
            aggregate.restore_from_snapshot(snapshot.data)
            aggregate.version = snapshot.version

            # Get events after snapshot
            events = await self.event_store.get_events(aggregate_id, snapshot.version)
        else:
            # Create new aggregate
            aggregate = self.aggregate_class(aggregate_id)

            # Get all events
            events = await self.event_store.get_events(aggregate_id)

        # Apply events
        for event in events:
            aggregate.apply_event(event)

        return aggregate if events or snapshot else None

    async def save(self, aggregate: T) -> bool:
        """Save aggregate using event sourcing."""
        uncommitted_events = aggregate.get_uncommitted_events()

        if not uncommitted_events:
            return True

        # Save events
        success = await self.event_store.append_events(
            aggregate.aggregate_id,
            uncommitted_events,
            aggregate.version - len(uncommitted_events),
        )

        if success:
            aggregate.mark_events_as_committed()

            # Create snapshot if needed
            if aggregate.version % self.snapshot_frequency == 0:
                snapshot = Snapshot(
                    snapshot_id=str(uuid.uuid4()),
                    aggregate_id=aggregate.aggregate_id,
                    aggregate_type=aggregate.__class__.__name__,
                    version=aggregate.version,
                    data=aggregate.create_snapshot(),
                )
                await self.event_store.save_snapshot(snapshot)

        return success

    async def delete(self, aggregate_id: str) -> bool:
        """Delete aggregate (not supported in event sourcing)."""
        # In event sourcing, we don't delete but mark as deleted
        # This would be implemented by raising a "deleted" event
        raise NotImplementedError("Direct deletion not supported in event sourcing")


class CommandHandler(ABC):
    """Abstract command handler."""

    @abstractmethod
    async def handle(self, command: Command) -> bool:
        """Handle command."""
        pass


class QueryHandler(ABC):
    """Abstract query handler."""

    @abstractmethod
    async def handle(self, query: Query) -> Any:
        """Handle query."""
        pass


class EventHandler(ABC):
    """Abstract event handler."""

    @abstractmethod
    async def handle(self, event: DomainEvent) -> bool:
        """Handle event."""
        pass


class ProjectionManager:
    """Manages read model projections."""

    def __init__(self, event_store: EventStore):
        """Initialize projection manager."""
        self.event_store = event_store
        self.projections: Dict[str, Dict[str, Any]] = {}
        self.projection_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.projection_checkpoints: Dict[str, datetime] = {}

        # Projection tasks
        self.projection_tasks: Dict[str, asyncio.Task] = {}

    def register_projection_handler(
        self,
        event_type: str,
        projection_name: str,
        handler: Callable[[DomainEvent], Dict[str, Any]],
    ):
        """Register projection handler for event type."""
        handler_info = {"projection_name": projection_name, "handler": handler}
        self.projection_handlers[event_type].append(handler_info)

    async def start_projection(self, projection_name: str):
        """Start projection processing."""
        if projection_name in self.projection_tasks:
            return  # Already running

        task = asyncio.create_task(self._projection_loop(projection_name))
        self.projection_tasks[projection_name] = task

        logging.info(f"Started projection: {projection_name}")

    async def stop_projection(self, projection_name: str):
        """Stop projection processing."""
        if projection_name in self.projection_tasks:
            task = self.projection_tasks[projection_name]
            task.cancel()
            del self.projection_tasks[projection_name]

            logging.info(f"Stopped projection: {projection_name}")

    async def _projection_loop(self, projection_name: str):
        """Projection processing loop."""
        while True:
            try:
                await self._process_projection(projection_name)
                await asyncio.sleep(5)  # Process every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Projection error for {projection_name}: {e}")
                await asyncio.sleep(10)

    async def _process_projection(self, projection_name: str):
        """Process projection for new events."""
        checkpoint = self.projection_checkpoints.get(projection_name)

        # Get all event types this projection handles
        relevant_event_types = [
            event_type
            for event_type, handlers in self.projection_handlers.items()
            if any(h["projection_name"] == projection_name for h in handlers)
        ]

        for event_type in relevant_event_types:
            events = await self.event_store.get_events_by_type(event_type, checkpoint)

            for event in events:
                await self._apply_event_to_projection(projection_name, event)

                # Update checkpoint
                self.projection_checkpoints[projection_name] = event.timestamp

    async def _apply_event_to_projection(
        self, projection_name: str, event: DomainEvent
    ):
        """Apply event to specific projection."""
        handlers = self.projection_handlers.get(event.event_type, [])

        for handler_info in handlers:
            if handler_info["projection_name"] == projection_name:
                try:
                    projection_data = handler_info["handler"](event)

                    # Update projection
                    if projection_name not in self.projections:
                        self.projections[projection_name] = {}

                    self.projections[projection_name].update(projection_data)

                except Exception as e:
                    logging.error(f"Projection handler error: {e}")

    def get_projection(self, projection_name: str) -> Dict[str, Any]:
        """Get projection data."""
        return self.projections.get(projection_name, {})


class DistributedTransactionCoordinator:
    """Coordinates distributed transactions using 2PC protocol."""

    def __init__(self):
        """Initialize transaction coordinator."""
        self.transactions: Dict[str, DistributedTransaction] = {}
        self.transaction_locks: Dict[str, asyncio.Lock] = {}

        # Transaction timeouts
        self.timeout_tasks: Dict[str, asyncio.Task] = {}

    async def begin_transaction(self, transaction: DistributedTransaction) -> bool:
        """Begin distributed transaction."""
        try:
            self.transactions[transaction.transaction_id] = transaction
            self.transaction_locks[transaction.transaction_id] = asyncio.Lock()

            # Start timeout monitoring
            timeout_task = asyncio.create_task(
                self._monitor_transaction_timeout(transaction.transaction_id)
            )
            self.timeout_tasks[transaction.transaction_id] = timeout_task

            transaction.state = TransactionState.STARTED
            transaction.updated_at = datetime.now(timezone.utc)

            logging.info(
                f"Started distributed transaction: {transaction.transaction_id}"
            )
            return True

        except Exception as e:
            logging.error(f"Failed to begin transaction: {e}")
            return False

    async def commit_transaction(self, transaction_id: str) -> bool:
        """Commit distributed transaction using 2PC."""
        if transaction_id not in self.transactions:
            return False

        async with self.transaction_locks[transaction_id]:
            transaction = self.transactions[transaction_id]

            try:
                # Phase 1: Prepare
                transaction.state = TransactionState.PREPARING

                prepare_success = await self._prepare_phase(transaction)

                if not prepare_success:
                    await self._abort_transaction(transaction)
                    return False

                transaction.state = TransactionState.PREPARED

                # Phase 2: Commit
                transaction.state = TransactionState.COMMITTING

                commit_success = await self._commit_phase(transaction)

                if commit_success:
                    transaction.state = TransactionState.COMMITTED
                    logging.info(f"Committed transaction: {transaction_id}")
                else:
                    transaction.state = TransactionState.FAILED
                    logging.error(f"Failed to commit transaction: {transaction_id}")

                transaction.updated_at = datetime.now(timezone.utc)

                # Clean up
                self._cleanup_transaction(transaction_id)

                return commit_success

            except Exception as e:
                logging.error(f"Transaction commit error: {e}")
                await self._abort_transaction(transaction)
                return False

    async def abort_transaction(self, transaction_id: str) -> bool:
        """Abort distributed transaction."""
        if transaction_id not in self.transactions:
            return False

        async with self.transaction_locks[transaction_id]:
            transaction = self.transactions[transaction_id]
            await self._abort_transaction(transaction)
            self._cleanup_transaction(transaction_id)
            return True

    async def _prepare_phase(self, transaction: DistributedTransaction) -> bool:
        """Execute prepare phase of 2PC."""
        prepare_results = []

        for participant in transaction.participants:
            try:
                # Send prepare request to participant
                result = await self._send_prepare_request(participant, transaction)
                prepare_results.append(result)

                if not result:
                    logging.warning(
                        f"Participant {participant.participant_id} failed to prepare"
                    )

            except Exception as e:
                logging.error(
                    f"Prepare error for participant {participant.participant_id}: {e}"
                )
                prepare_results.append(False)

        return all(prepare_results)

    async def _commit_phase(self, transaction: DistributedTransaction) -> bool:
        """Execute commit phase of 2PC."""
        commit_results = []

        for participant in transaction.participants:
            try:
                # Send commit request to participant
                result = await self._send_commit_request(participant, transaction)
                commit_results.append(result)

                if not result:
                    logging.warning(
                        f"Participant {participant.participant_id} failed to commit"
                    )

            except Exception as e:
                logging.error(
                    f"Commit error for participant {participant.participant_id}: {e}"
                )
                commit_results.append(False)

        return all(commit_results)

    async def _abort_transaction(self, transaction: DistributedTransaction):
        """Abort transaction and notify participants."""
        transaction.state = TransactionState.ABORTING

        for participant in transaction.participants:
            try:
                await self._send_abort_request(participant, transaction)
            except Exception as e:
                logging.error(
                    f"Abort error for participant {participant.participant_id}: {e}"
                )

        transaction.state = TransactionState.ABORTED
        transaction.updated_at = datetime.now(timezone.utc)

        logging.info(f"Aborted transaction: {transaction.transaction_id}")

    async def _send_prepare_request(
        self, participant: TransactionParticipant, transaction: DistributedTransaction
    ) -> bool:
        """Send prepare request to participant."""
        # Simulate prepare request
        # In practice, this would make HTTP/gRPC call to participant
        await asyncio.sleep(0.1)  # Simulate network delay

        # Simulate 90% success rate
        import random

        return random.random() < 0.9

    async def _send_commit_request(
        self, participant: TransactionParticipant, transaction: DistributedTransaction
    ) -> bool:
        """Send commit request to participant."""
        # Simulate commit request
        await asyncio.sleep(0.1)  # Simulate network delay

        # Simulate 95% success rate
        import random

        return random.random() < 0.95

    async def _send_abort_request(
        self, participant: TransactionParticipant, transaction: DistributedTransaction
    ) -> bool:
        """Send abort request to participant."""
        # Simulate abort request
        await asyncio.sleep(0.1)  # Simulate network delay
        return True  # Abort usually succeeds

    async def _monitor_transaction_timeout(self, transaction_id: str):
        """Monitor transaction timeout."""
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            return

        try:
            await asyncio.sleep(transaction.timeout)

            # Check if transaction is still active
            if transaction_id in self.transactions and self.transactions[
                transaction_id
            ].state not in [TransactionState.COMMITTED, TransactionState.ABORTED]:
                logging.warning(f"Transaction timeout: {transaction_id}")
                await self.abort_transaction(transaction_id)

        except asyncio.CancelledError:
            pass

    def _cleanup_transaction(self, transaction_id: str):
        """Clean up transaction resources."""
        self.transactions.pop(transaction_id, None)
        self.transaction_locks.pop(transaction_id, None)

        if transaction_id in self.timeout_tasks:
            self.timeout_tasks[transaction_id].cancel()
            del self.timeout_tasks[transaction_id]

    def get_transaction_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get transaction status."""
        transaction = self.transactions.get(transaction_id)

        if not transaction:
            return None

        return {
            "transaction_id": transaction.transaction_id,
            "state": transaction.state.value,
            "participants": len(transaction.participants),
            "created_at": transaction.created_at.isoformat(),
            "updated_at": transaction.updated_at.isoformat(),
            "timeout": transaction.timeout,
        }


class SagaOrchestrator:
    """Orchestrates saga transactions for long-running processes."""

    def __init__(self):
        """Initialize saga orchestrator."""
        self.sagas: Dict[str, SagaTransaction] = {}
        self.saga_locks: Dict[str, asyncio.Lock] = {}

        # Saga execution tasks
        self.saga_tasks: Dict[str, asyncio.Task] = {}

    async def start_saga(self, saga: SagaTransaction) -> bool:
        """Start saga execution."""
        try:
            self.sagas[saga.saga_id] = saga
            self.saga_locks[saga.saga_id] = asyncio.Lock()

            # Start saga execution
            task = asyncio.create_task(self._execute_saga(saga.saga_id))
            self.saga_tasks[saga.saga_id] = task

            saga.state = SagaState.EXECUTING
            saga.updated_at = datetime.now(timezone.utc)

            logging.info(f"Started saga: {saga.saga_id}")
            return True

        except Exception as e:
            logging.error(f"Failed to start saga: {e}")
            return False

    async def _execute_saga(self, saga_id: str):
        """Execute saga steps."""
        async with self.saga_locks[saga_id]:
            saga = self.sagas[saga_id]

            try:
                # Execute forward steps
                for i, step in enumerate(saga.steps):
                    saga.current_step = i

                    success = await self._execute_step(step, saga.context)

                    if success:
                        saga.completed_steps.append(step.step_id)
                        logging.info(f"Completed saga step: {step.step_id}")
                    else:
                        logging.error(f"Failed saga step: {step.step_id}")

                        # Start compensation
                        await self._compensate_saga(saga)
                        return

                # All steps completed successfully
                saga.state = SagaState.COMPLETED
                saga.updated_at = datetime.now(timezone.utc)

                logging.info(f"Saga completed successfully: {saga_id}")

            except Exception as e:
                logging.error(f"Saga execution error: {e}")
                saga.state = SagaState.FAILED
                await self._compensate_saga(saga)

            finally:
                # Clean up
                self._cleanup_saga(saga_id)

    async def _execute_step(self, step: SagaStep, context: Dict[str, Any]) -> bool:
        """Execute individual saga step."""
        try:
            # Simulate step execution
            # In practice, this would make service calls
            await asyncio.sleep(0.1)  # Simulate processing time

            # Update context with step results
            context[f"{step.step_id}_result"] = {
                "success": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Simulate 85% success rate
            import random

            return random.random() < 0.85

        except Exception as e:
            logging.error(f"Step execution error: {e}")
            return False

    async def _compensate_saga(self, saga: SagaTransaction):
        """Compensate saga by undoing completed steps."""
        saga.state = SagaState.COMPENSATING

        # Compensate in reverse order
        for step_id in reversed(saga.completed_steps):
            step = next((s for s in saga.steps if s.step_id == step_id), None)

            if step:
                success = await self._compensate_step(step, saga.context)

                if success:
                    saga.compensated_steps.append(step_id)
                    logging.info(f"Compensated saga step: {step_id}")
                else:
                    logging.error(f"Failed to compensate step: {step_id}")

        saga.state = SagaState.COMPENSATED
        saga.updated_at = datetime.now(timezone.utc)

        logging.info(f"Saga compensated: {saga.saga_id}")

    async def _compensate_step(self, step: SagaStep, context: Dict[str, Any]) -> bool:
        """Compensate individual saga step."""
        try:
            # Simulate compensation
            await asyncio.sleep(0.1)  # Simulate processing time

            # Update context with compensation results
            context[f"{step.step_id}_compensation"] = {
                "success": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Compensation usually has higher success rate
            import random

            return random.random() < 0.95

        except Exception as e:
            logging.error(f"Step compensation error: {e}")
            return False

    def _cleanup_saga(self, saga_id: str):
        """Clean up saga resources."""
        if saga_id in self.saga_tasks:
            del self.saga_tasks[saga_id]

        # Keep saga record for audit trail
        # In production, might move to completed sagas storage

    def get_saga_status(self, saga_id: str) -> Optional[Dict[str, Any]]:
        """Get saga status."""
        saga = self.sagas.get(saga_id)

        if not saga:
            return None

        return {
            "saga_id": saga.saga_id,
            "saga_type": saga.saga_type,
            "state": saga.state.value,
            "current_step": saga.current_step,
            "total_steps": len(saga.steps),
            "completed_steps": len(saga.completed_steps),
            "compensated_steps": len(saga.compensated_steps),
            "created_at": saga.created_at.isoformat(),
            "updated_at": saga.updated_at.isoformat(),
        }


class DistributedCache:
    """Distributed caching with consistency management."""

    def __init__(self, redis_client=None):
        """Initialize distributed cache."""
        self.redis_client = redis_client
        self.local_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.cache_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Cache statistics
        self.cache_stats = {"hits": 0, "misses": 0, "invalidations": 0, "evictions": 0}

    async def get(
        self, key: str, consistency_level: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    ) -> Optional[Any]:
        """Get value from cache with consistency level."""
        async with self.cache_locks[key]:
            # Check local cache first
            if key in self.local_cache:
                cache_entry = self.local_cache[key]

                # Check if entry is still valid based on consistency level
                if self._is_cache_entry_valid(key, consistency_level):
                    self.cache_stats["hits"] += 1
                    return cache_entry["value"]
                else:
                    # Remove stale entry
                    del self.local_cache[key]
                    self.cache_timestamps.pop(key, None)

            # Try distributed cache (Redis)
            if self.redis_client:
                try:
                    cached_value = self.redis_client.get(key)
                    if cached_value:
                        value = json.loads(cached_value)

                        # Update local cache
                        self._set_local_cache(key, value)

                        self.cache_stats["hits"] += 1
                        return value
                except Exception as e:
                    logging.error(f"Redis cache error: {e}")

            self.cache_stats["misses"] += 1
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache."""
        async with self.cache_locks[key]:
            try:
                # Set in distributed cache (Redis)
                if self.redis_client:
                    try:
                        serialized_value = json.dumps(value)
                        self.redis_client.setex(key, ttl, serialized_value)
                    except Exception as e:
                        logging.error(f"Redis cache set error: {e}")

                # Set in local cache
                self._set_local_cache(key, value)

                return True

            except Exception as e:
                logging.error(f"Cache set error: {e}")
                return False

    async def invalidate(self, key: str) -> bool:
        """Invalidate cache entry."""
        async with self.cache_locks[key]:
            try:
                # Remove from distributed cache
                if self.redis_client:
                    try:
                        self.redis_client.delete(key)
                    except Exception as e:
                        logging.error(f"Redis cache delete error: {e}")

                # Remove from local cache
                self.local_cache.pop(key, None)
                self.cache_timestamps.pop(key, None)

                self.cache_stats["invalidations"] += 1
                return True

            except Exception as e:
                logging.error(f"Cache invalidation error: {e}")
                return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern."""
        invalidated_count = 0

        # Invalidate local cache entries
        keys_to_remove = [
            key
            for key in self.local_cache.keys()
            if self._matches_pattern(key, pattern)
        ]

        for key in keys_to_remove:
            await self.invalidate(key)
            invalidated_count += 1

        # Invalidate distributed cache entries
        if self.redis_client:
            try:
                redis_keys = self.redis_client.keys(pattern)
                if redis_keys:
                    self.redis_client.delete(*redis_keys)
                    invalidated_count += len(redis_keys)
            except Exception as e:
                logging.error(f"Redis pattern invalidation error: {e}")

        return invalidated_count

    def _set_local_cache(self, key: str, value: Any):
        """Set value in local cache."""
        self.local_cache[key] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc),
        }
        self.cache_timestamps[key] = datetime.now(timezone.utc)

    def _is_cache_entry_valid(
        self, key: str, consistency_level: ConsistencyLevel
    ) -> bool:
        """Check if cache entry is valid based on consistency level."""
        if key not in self.cache_timestamps:
            return False

        entry_time = self.cache_timestamps[key]
        now = datetime.now(timezone.utc)
        age = (now - entry_time).total_seconds()

        # Different TTL based on consistency level
        ttl_limits = {
            ConsistencyLevel.STRONG: 1,  # 1 second
            ConsistencyLevel.SESSION: 30,  # 30 seconds
            ConsistencyLevel.BOUNDED_STALENESS: 300,  # 5 minutes
            ConsistencyLevel.EVENTUAL: 3600,  # 1 hour
            ConsistencyLevel.WEAK: 7200,  # 2 hours
        }

        ttl_limit = ttl_limits.get(consistency_level, 3600)
        return age <= ttl_limit

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern."""
        # Simple pattern matching (could be enhanced with regex)
        return pattern.replace("*", "") in key

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (
            self.cache_stats["hits"] / total_requests if total_requests > 0 else 0
        )

        return {
            "hit_rate": hit_rate,
            "total_entries": len(self.local_cache),
            "stats": self.cache_stats.copy(),
        }


class DataConsistencyManager:
    """Manages data consistency across microservices."""

    def __init__(self):
        """Initialize consistency manager."""
        self.consistency_policies: Dict[str, ConsistencyLevel] = {}
        self.conflict_resolution_strategies: Dict[str, Callable] = {}
        self.consistency_monitors: Dict[str, asyncio.Task] = {}

        # Consistency events
        self.consistency_events: deque = deque(maxlen=1000)

    def set_consistency_policy(self, resource: str, level: ConsistencyLevel):
        """Set consistency level for a resource."""
        self.consistency_policies[resource] = level
        logging.info(f"Set consistency policy for {resource}: {level.value}")

    def register_conflict_resolution(
        self, resource: str, strategy: Callable[[List[Any]], Any]
    ):
        """Register conflict resolution strategy."""
        self.conflict_resolution_strategies[resource] = strategy
        logging.info(f"Registered conflict resolution for {resource}")

    async def check_consistency(
        self, resource: str, replicas: List[Any]
    ) -> Dict[str, Any]:
        """Check consistency across replicas."""
        if not replicas:
            return {"consistent": True, "conflicts": []}

        # Compare all replicas
        base_replica = replicas[0]
        conflicts = []

        for i, replica in enumerate(replicas[1:], 1):
            if not self._are_replicas_consistent(base_replica, replica):
                conflicts.append(
                    {
                        "replica_index": i,
                        "base_value": base_replica,
                        "conflicting_value": replica,
                    }
                )

        consistent = len(conflicts) == 0

        # Record consistency event
        self._record_consistency_event(resource, consistent, conflicts)

        result = {
            "consistent": consistent,
            "conflicts": conflicts,
            "total_replicas": len(replicas),
            "consistency_level": self.consistency_policies.get(
                resource, ConsistencyLevel.EVENTUAL
            ).value,
        }

        return result

    async def resolve_conflicts(
        self, resource: str, conflicts: List[Dict[str, Any]]
    ) -> Any:
        """Resolve conflicts using registered strategy."""
        if not conflicts:
            return None

        strategy = self.conflict_resolution_strategies.get(resource)

        if not strategy:
            # Default: last writer wins
            strategy = self._last_writer_wins_strategy

        try:
            # Extract conflicting values
            values = [conflict["conflicting_value"] for conflict in conflicts]

            # Apply resolution strategy
            resolved_value = strategy(values)

            logging.info(f"Resolved conflicts for {resource} using strategy")
            return resolved_value

        except Exception as e:
            logging.error(f"Conflict resolution error for {resource}: {e}")
            return None

    def _are_replicas_consistent(self, replica1: Any, replica2: Any) -> bool:
        """Check if two replicas are consistent."""
        # Simple equality check (could be enhanced for complex objects)
        if isinstance(replica1, dict) and isinstance(replica2, dict):
            return self._deep_dict_compare(replica1, replica2)
        else:
            return replica1 == replica2

    def _deep_dict_compare(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> bool:
        """Deep comparison of dictionaries."""
        if set(dict1.keys()) != set(dict2.keys()):
            return False

        for key in dict1:
            if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                if not self._deep_dict_compare(dict1[key], dict2[key]):
                    return False
            elif dict1[key] != dict2[key]:
                return False

        return True

    def _last_writer_wins_strategy(self, values: List[Any]) -> Any:
        """Last writer wins conflict resolution."""
        # Assume values have timestamps
        if all(isinstance(v, dict) and "timestamp" in v for v in values):
            return max(values, key=lambda v: v["timestamp"])
        else:
            return values[-1]  # Return last value

    def _record_consistency_event(
        self, resource: str, consistent: bool, conflicts: List[Dict[str, Any]]
    ):
        """Record consistency event."""
        event = {
            "timestamp": datetime.now(timezone.utc),
            "resource": resource,
            "consistent": consistent,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
        }

        self.consistency_events.append(event)

    def get_consistency_report(self, resource: str = None) -> Dict[str, Any]:
        """Get consistency report."""
        if resource:
            events = [e for e in self.consistency_events if e["resource"] == resource]
        else:
            events = list(self.consistency_events)

        if not events:
            return {"total_events": 0, "consistency_rate": 0}

        consistent_events = sum(1 for e in events if e["consistent"])
        consistency_rate = consistent_events / len(events)

        return {
            "total_events": len(events),
            "consistent_events": consistent_events,
            "inconsistent_events": len(events) - consistent_events,
            "consistency_rate": consistency_rate,
            "recent_events": events[-10:],  # Last 10 events
        }


def create_advanced_data_management() -> Dict[str, Any]:
    """Create advanced data management components."""
    event_store = InMemoryEventStore()
    projection_manager = ProjectionManager(event_store)
    transaction_coordinator = DistributedTransactionCoordinator()
    saga_orchestrator = SagaOrchestrator()
    distributed_cache = DistributedCache()
    consistency_manager = DataConsistencyManager()

    return {
        "event_store": event_store,
        "projection_manager": projection_manager,
        "transaction_coordinator": transaction_coordinator,
        "saga_orchestrator": saga_orchestrator,
        "distributed_cache": distributed_cache,
        "consistency_manager": consistency_manager,
    }
