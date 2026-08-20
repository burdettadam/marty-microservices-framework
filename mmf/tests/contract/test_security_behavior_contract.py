"""Cross-language security behavior contract for the Python-to-Rust port."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from mmf.core.security.domain.models.rate_limit import (
    RateLimitQuota,
    RateLimitRule,
    RateLimitScope,
    RateLimitStrategy,
    RateLimitWindow,
)
from mmf.core.security.domain.models.session import (
    SessionData,
    SessionLifecycle,
    SessionSecurityPolicy,
)
from mmf.core.security.domain.models.user import AuthenticatedUser
from mmf.core.security.domain.services.rate_limiting import RateLimitEngine
from mmf.framework.authorization.domain.models import Permission


CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "security-behavior.json").read_text(
        encoding="utf-8"
    )
)


def test_authenticated_user_contract() -> None:
    case = CONTRACT["user"]
    user = AuthenticatedUser(
        user_id=case["user_id"],
        roles=set(case["roles"]),
        permissions=set(case["permissions"]),
    )
    for role, expected in case["role_checks"].items():
        assert user.has_role(role) is expected
    for permission, expected in case["permission_checks"].items():
        assert user.has_permission(permission) is expected


def test_rate_limit_key_contract() -> None:
    scopes = {scope.value: scope for scope in RateLimitScope}
    for case in CONTRACT["rate_limit_keys"]:
        rule = RateLimitRule(
            name="api",
            scope=scopes[case["scope"]],
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=1,
            window_seconds=1,
        )
        quota = RateLimitQuota(
            user_id=case.get("user_id"),
            ip_address=case.get("ip_address"),
            endpoint=case.get("endpoint"),
            service=case.get("service"),
        )
        assert quota.get_cache_key(rule) == case["expected"]


def test_fixed_window_contract() -> None:
    case = CONTRACT["fixed_window"]
    rule = RateLimitRule(
        name="contract",
        scope=RateLimitScope.GLOBAL,
        strategy=RateLimitStrategy.FIXED_WINDOW,
        limit=case["limit"],
        window_seconds=case["window_ms"] // 1000,
    )
    quota = RateLimitQuota(rules=[rule])
    window = RateLimitWindow(
        key=quota.get_cache_key(rule),
        current_count=0,
        reset_time=datetime.utcnow() + timedelta(seconds=1),
    )
    engine = RateLimitEngine()
    results = []
    for index, _timestamp in enumerate(case["timestamps_ms"]):
        if index == len(case["timestamps_ms"]) - 1:
            window.reset_time = datetime.utcnow() - timedelta(milliseconds=1)
        results.append(engine.check_limit(rule, quota, window))
    assert [result.allowed for result in results] == case["allowed"]
    assert [result.remaining for result in results] == case["remaining"]


def test_session_contract() -> None:
    case = CONTRACT["session"]
    lifecycle = SessionLifecycle(
        default_timeout_minutes=case["default_timeout_ms"] // 60_000,
        max_timeout_minutes=case["max_timeout_ms"] // 60_000,
        idle_timeout_minutes=case["idle_timeout_ms"] // 60_000,
        absolute_timeout_minutes=case["absolute_timeout_ms"] // 60_000,
    )
    epoch = datetime(1970, 1, 1)
    expiration = lifecycle.calculate_expiration(
        epoch + timedelta(milliseconds=case["created_at_ms"]),
        epoch + timedelta(milliseconds=case["last_accessed_ms"]),
        requested_timeout=case["requested_timeout_ms"] // 60_000,
    )
    assert expiration == epoch + timedelta(milliseconds=case["expected_expiration_ms"])

    session = SessionData.create("user", ip_address="192.0.2.1", user_agent="agent-a")
    policy = SessionSecurityPolicy(detect_session_hijacking=True)
    assert policy.validate_session_request(session, "192.0.2.2", "agent-b") == [
        case["ip_violation"],
        case["user_agent_violation"],
    ]


def test_authorization_wildcard_contract() -> None:
    case = CONTRACT["authorization"]
    assert case["default_decision"] == "deny"
    assert case["deny_overrides_allow"] is True
    permission = Permission(resource_type="credentials", resource_id="*", action="read")
    matching_type, matching_id = case["matching_resource"].split("/", 1)
    other_type, other_id = case["non_matching_resource"].split("/", 1)
    assert permission.matches(matching_type, matching_id, "read")
    assert not permission.matches(other_type, other_id, "read")
