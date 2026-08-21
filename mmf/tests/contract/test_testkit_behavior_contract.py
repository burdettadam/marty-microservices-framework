"""Cross-language behavior contract for MMF test tooling."""

from __future__ import annotations

import json
from pathlib import Path

from mmf.framework.testing.application.contract_verifier import ContractValidator
from mmf.framework.testing.application.performance_runner import MetricsCollector
from mmf.framework.testing.domain.contract import (
    ContractInteraction,
    ContractRequest,
    ContractResponse,
    VerificationLevel,
)
from mmf.framework.testing.domain.performance import ResponseMetric


CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "testkit-behavior.json").read_text(
        encoding="utf-8"
    )
)


def test_performance_metric_aggregation_and_interpolated_percentiles() -> None:
    case = CONTRACT["metrics"]
    collector = MetricsCollector()
    collector.start_time = 1.0
    collector.end_time = 1.0 + case["elapsed_ms"] / 1000
    for response in case["responses"]:
        collector.record_response(
            ResponseMetric(
                timestamp=0.0,
                response_time=response["duration_ms"],
                status_code=response.get("status_code", 0),
                error=response.get("error"),
                request_size=0,
                response_size=response["bytes"],
            )
        )
    metrics = collector.get_aggregated_metrics()
    assert metrics.total_requests == case["total"]
    assert metrics.successful_requests == case["successful"]
    assert metrics.failed_requests == case["failed"]
    assert metrics.avg_response_time == case["mean_ms"]
    assert metrics.median_response_time == case["p50_ms"]
    assert metrics.p95_response_time == case["p95_ms"]
    assert metrics.p99_response_time == case["p99_ms"]
    assert metrics.requests_per_second == case["requests_per_second"]
    assert metrics.error_rate == case["error_rate"]


def test_contract_strictness_vectors() -> None:
    case = CONTRACT["contract"]
    interaction = ContractInteraction(
        description="get user",
        request=ContractRequest(method="GET", path="/users/123"),
        response=ContractResponse(status_code=case["expected_status"], body=case["expected_body"]),
    )
    actual_body = {**case["expected_body"], **case["extra_body"]}
    valid, errors = ContractValidator(VerificationLevel.PERMISSIVE).validate_response(
        interaction, {"status_code": case["actual_status"], "body": actual_body}
    )
    assert valid and len(errors) == case["lenient_mismatches"]
    valid, errors = ContractValidator(VerificationLevel.STRICT).validate_response(
        interaction, {"status_code": case["actual_status"], "body": actual_body}
    )
    assert not valid and len(errors) == case["strict_mismatches"]


def test_fault_and_chaos_vectors_are_explicit_and_bounded() -> None:
    faults = CONTRACT["faults"]
    assert len(faults["results"]) == 5
    assert all(call > 0 for call in faults["fail_on_calls"])
    chaos = CONTRACT["chaos"]
    assert chaos["duration_ms"] > 0
    assert 0.0 <= chaos["intensity"] <= 1.0
    assert chaos["recovery_required"] and chaos["cleanup_required"]
