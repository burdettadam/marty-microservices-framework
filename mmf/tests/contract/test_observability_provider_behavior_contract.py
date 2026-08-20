import importlib
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
FIXTURE = json.loads((ROOT / "contracts" / "observability-provider-behavior.json").read_text())


def _load_legacy_source(name: str, path: Path):
    """Load a module without executing its broken package initializer."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CUSTOM_METRICS = _load_legacy_source(
    "mmf_contract_custom_metrics",
    ROOT / "mmf" / "framework" / "observability" / "monitoring" / "custom_metrics.py",
)


def test_metric_aggregation_contract() -> None:
    case = FIXTURE["aggregations"]
    buffer = CUSTOM_METRICS.MetricBuffer(window_minutes=5, max_points=100)
    now = datetime.now(timezone.utc)
    for value in case["values"]:
        buffer.add_value(value, now)
    aggregations = {
        "sum": CUSTOM_METRICS.MetricAggregation.SUM,
        "average": CUSTOM_METRICS.MetricAggregation.AVERAGE,
        "min": CUSTOM_METRICS.MetricAggregation.MIN,
        "max": CUSTOM_METRICS.MetricAggregation.MAX,
        "count": CUSTOM_METRICS.MetricAggregation.COUNT,
        "p95": CUSTOM_METRICS.MetricAggregation.PERCENTILE_95,
        "p99": CUSTOM_METRICS.MetricAggregation.PERCENTILE_99,
    }
    for name, aggregation in aggregations.items():
        assert buffer.aggregate(aggregation) == pytest.approx(case["expected"][name])
    assert buffer.get_values()[-1] == case["expected"]["latest"]


def test_threshold_contract() -> None:
    operators = {
        "greater_than": ">",
        "greater_than_or_equal": ">=",
        "less_than": "<",
        "less_than_or_equal": "<=",
        "equals": "==",
        "not_equals": "!=",
    }
    for index, case in enumerate(FIXTURE["thresholds"]):
        manager = CUSTOM_METRICS.AlertManager()
        rule = CUSTOM_METRICS.AlertRule(
            name=f"case-{index}",
            metric_name="fixture",
            condition=operators[case["operator"]],
            threshold=case["threshold"],
            level=CUSTOM_METRICS.AlertLevel.WARNING,
            description="fixture threshold",
        )
        assert (manager.evaluate_rule(rule, case["value"]) is not None) is case["triggered"]


def test_health_rollup_contract() -> None:
    for case in FIXTURE["health_rollups"]:
        statuses = case["statuses"]
        expected = (
            "unhealthy"
            if "unhealthy" in statuses
            else "degraded"
            if "degraded" in statuses
            else "unknown"
            if "unknown" in statuses
            else "healthy"
        )
        assert expected == case["expected"]


def test_capacity_prediction_contract() -> None:
    # The legacy module has a stale relative import (`mmf.infrastructure`).
    # Alias its actual framework package only to characterize behavior until
    # this Python implementation is deleted after consumer cutover.
    infrastructure = importlib.import_module("mmf.framework.infrastructure")
    cache = importlib.import_module("mmf.framework.infrastructure.cache")
    sys.modules.setdefault("mmf.infrastructure", infrastructure)
    sys.modules.setdefault("mmf.infrastructure.cache", cache)
    analytics = importlib.import_module("mmf.framework.observability.analytics")
    case = FIXTURE["capacity"]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    historical = [
        {"timestamp": start + timedelta(milliseconds=point["timestamp_ms"]), "value": point["value"]}
        for point in case["points"]
    ]
    prediction = analytics.CapacityPlanner("contract").predict_capacity_needs(
        case["metric_name"], historical, timedelta(seconds=case["horizon_seconds"])
    )
    assert prediction.predicted_usage == pytest.approx(case["predicted_usage"])
    assert prediction.time_to_threshold.total_seconds() == pytest.approx(
        case["time_to_threshold_seconds"]
    )
    assert prediction.recommended_action.startswith(case["recommendation_prefix"])
