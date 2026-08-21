"""Cross-language observability behavior contract for the Python-to-Rust port."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opentelemetry.trace import get_current_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from mmf.framework.observability.correlation import CorrelationContext
from mmf.framework.observability.slo import (
    SLICollector,
    SLISpecification,
    SLIType,
    SLODefinition,
    SLOTarget,
    SLOTracker,
)


CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "observability-behavior.json").read_text(
        encoding="utf-8"
    )
)


def test_correlation_contract() -> None:
    case = CONTRACT["correlation"]
    context = CorrelationContext(**case["context"])
    assert context.to_headers() == case["headers"]
    assert context.to_log_context() == case["log_fields"]


def test_traceparent_contract() -> None:
    propagator = TraceContextTextMapPropagator()
    for traceparent in CONTRACT["traceparent"]["valid"]:
        context = propagator.extract({"traceparent": traceparent})
        assert get_current_span(context).get_span_context().is_valid, traceparent
    for traceparent in CONTRACT["traceparent"]["invalid"]:
        context = propagator.extract({"traceparent": traceparent})
        assert not get_current_span(context).get_span_context().is_valid, traceparent


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CONTRACT["slo_cases"])
async def test_error_budget_contract(case: dict[str, float]) -> None:
    tracker = SLOTracker(SLICollector())
    tracker.register_slo(
        SLODefinition(
            name="contract",
            service_name="gateway",
            sli=SLISpecification(
                name="availability",
                sli_type=SLIType.AVAILABILITY,
                description="Contract availability",
                query="contract",
            ),
            target=SLOTarget(target=case["target_percentage"], window="30d"),
        )
    )
    await tracker._update_error_budget("contract", case["compliance_percentage"])
    budget = tracker.error_budgets["contract"]
    assert budget.total_budget == pytest.approx(case["total_budget"])
    assert budget.budget_consumed == pytest.approx(case["consumed"])
    assert budget.budget_remaining == pytest.approx(case["remaining"])
