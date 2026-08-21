"""Language-neutral behavioral contract for the Python-to-Rust messaging port."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mmf.core.messaging import Message, MessagePriority, RoutingConfig, RoutingRule
from mmf.framework.messaging.application.router import MessageRouter
from mmf.framework.messaging.domain.extended import MessagingPattern, PatternSelector


CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "messaging-behavior.json").read_text(
        encoding="utf-8"
    )
)


def test_priority_contract() -> None:
    priorities = {priority.name.lower(): priority.value for priority in MessagePriority}
    assert priorities == {case["name"]: case["value"] for case in CONTRACT["priorities"]}


def test_message_expiry_and_retry_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    case = CONTRACT["message_state"]
    monkeypatch.setattr("mmf.core.messaging.time.time", lambda: case["now_ms"] / 1000)
    assert not Message().is_expired()
    assert not Message(expiration=case["future_expiry_ms"] / 1000).is_expired()
    assert Message(expiration=case["past_expiry_ms"] / 1000).is_expired()
    for retry in case["retry_cases"]:
        message = Message(
            retry_count=retry["retry_count"], max_retries=retry["max_retries"]
        )
        assert message.can_retry() is retry["expected"]


@pytest.mark.asyncio
async def test_routing_contract() -> None:
    case = CONTRACT["routing"]
    router = MessageRouter(
        RoutingConfig(
            rules=[
                RoutingRule(
                    pattern=rule["pattern"],
                    exchange=rule["topic"],
                    routing_key=rule["routing_key"],
                    priority=rule["priority"],
                    metadata={"contract_name": rule["name"]},
                )
                for rule in case["rules"]
            ],
            default_exchange=case["default_topic"],
            default_routing_key=case["default_key"],
        )
    )
    for route_case in case["cases"]:
        topic, routing_key = await router.route(Message(routing_key=route_case["input"]))
        assert (topic, routing_key) == (route_case["topic"], route_case["routing_key"])


def test_pattern_recommendation_contract() -> None:
    expected_patterns = {
        "publish_subscribe": MessagingPattern.PUBLISH_SUBSCRIBE,
        "request_reply": MessagingPattern.REQUEST_RESPONSE,
        "stream_processing": MessagingPattern.STREAM_PROCESSING,
        "point_to_point": MessagingPattern.POINT_TO_POINT,
        "broadcast": MessagingPattern.BROADCAST,
    }
    for case in CONTRACT["pattern_recommendations"]:
        actual = PatternSelector.recommend_pattern(
            case["use_case"],
            ordering_required=case["ordering_required"],
            response_needed=case["response_needed"],
            high_throughput=case["high_throughput"],
        )
        assert actual is expected_patterns[case["expected"]]
