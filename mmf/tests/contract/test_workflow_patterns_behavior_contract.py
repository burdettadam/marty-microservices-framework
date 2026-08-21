"""Behavior contract for the workflow and consistency-pattern consolidation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mmf.framework.patterns.distributed_transactions import (
    DistributedTransactionCoordinator,
    TransactionState,
)
from mmf.framework.patterns.event_sourcing import DomainEvent, InMemoryEventStore, Snapshot
from mmf.framework.workflow.application.engine import WorkflowEngine
from mmf.framework.workflow.domain.entities import WorkflowStatus


CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "workflow-patterns-behavior.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.asyncio
async def test_event_stream_versions_concurrency_and_snapshot() -> None:
    case = CONTRACT["event_stream"]
    store = InMemoryEventStore()
    events = [
        DomainEvent("event-1", case["event_types"][0], "order-1", "Order", 0, {"status": "created", "amount": 1250}),
        DomainEvent("event-2", case["event_types"][1], "order-1", "Order", 0, {"status": "paid"}),
    ]
    assert await store.append_events(case["stream_id"], events, 0)
    assert [event.version for event in events] == case["versions"]
    assert not await store.append_events(case["stream_id"], [events[0]], case["stale_expected_version"])
    assert await store.get_events(case["stream_id"]) == events

    snapshot = Snapshot("snapshot-1", "order-1", "Order", case["snapshot_version"], case["final_state"])
    assert await store.save_snapshot(snapshot)
    assert await store.get_snapshot("order-1") == snapshot


class RecordingWorkflowRepository:
    def __init__(self) -> None:
        self.statuses: list[WorkflowStatus] = []

    async def save_workflow(self, _context, status: WorkflowStatus) -> None:
        self.statuses.append(status)

    async def update_status(self, _workflow_id: str, status: WorkflowStatus) -> None:
        self.statuses.append(status)


@pytest.mark.asyncio
async def test_legacy_workflow_runs_steps_and_records_terminal_status() -> None:
    case = CONTRACT["workflow"]
    repository = RecordingWorkflowRepository()
    called: list[str] = []

    async def reserve(_context) -> None:
        called.append("reserve")

    def charge(_context) -> None:
        called.append("charge")

    context = await WorkflowEngine(repository).start_workflow(
        case["definition_id"], [reserve, charge], {"amount": 1250}
    )
    assert called == ["reserve", "charge"]
    assert context.data == {"amount": 1250}
    assert repository.statuses == [WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED]


class FailingPrepareCoordinator(DistributedTransactionCoordinator):
    async def _prepare_participant(self, _transaction_id, participant) -> bool:
        return participant.service_name != "payments"


@pytest.mark.asyncio
async def test_two_phase_commit_and_failed_prepare_are_explicit() -> None:
    case = CONTRACT["transaction"]
    participants = [
        {"service_name": name, "endpoint": f"https://{name}"} for name in case["participants"]
    ]
    coordinator = DistributedTransactionCoordinator("coordinator", case["timeout_ms"] // 1000)
    transaction_id = await coordinator.begin_transaction(participants)
    assert await coordinator.prepare_transaction(transaction_id)
    assert await coordinator.get_transaction_status(transaction_id) == TransactionState.PREPARED
    assert await coordinator.commit_transaction(transaction_id)
    assert await coordinator.get_transaction_status(transaction_id) == TransactionState.COMMITTED

    failing = FailingPrepareCoordinator("coordinator", case["timeout_ms"] // 1000)
    failed_id = await failing.begin_transaction(participants)
    assert not await failing.prepare_transaction(failed_id)
    assert await failing.get_transaction_status(failed_id) == TransactionState.FAILED
    assert await failing.abort_transaction(failed_id)
    assert await failing.get_transaction_status(failed_id) == TransactionState.ABORTED


def test_intended_cqrs_and_strong_consistency_contract_is_fail_closed() -> None:
    cqrs = CONTRACT["cqrs"]
    consistency = CONTRACT["consistency"]
    assert cqrs["same_command_result_on_replay"] is True
    assert cqrs["handler_invocations"] == 1
    assert consistency["read_quorum"] + consistency["write_quorum"] > consistency["replication_factor"]
    assert consistency["production_requires_encrypted_transport"] is True
