"""Language-neutral behavioral contract for the built-in identity service port."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mmf.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)
CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "identity-service-behavior.json").read_text(
        encoding="utf-8"
    )
)


def _user() -> AuthenticatedUser:
    case = CONTRACT["user"]
    return AuthenticatedUser(
        user_id=case["user_id"],
        username=case["username"],
        email=case["email"],
        roles=set(case["roles"]),
        permissions=set(case["permissions"]),
    )


def test_authentication_result_contract() -> None:
    case = CONTRACT["results"]
    success = AuthenticationResult.create_success(_user())
    assert success.status.value == case["success_status"]
    assert success.is_successful
    assert not success.failed

    failure = AuthenticationResult.failure(
        case["failure_message"], AuthenticationErrorCode(case["failure_code"])
    )
    assert failure.status.value == case["failure_status"]
    assert failure.error_code.value == case["failure_code"]
    assert failure.failed

    mfa = AuthenticationResult.pending_mfa()
    assert mfa.status.value == case["mfa_status"]
    assert mfa.error_code.value == case["mfa_code"]
    assert mfa.requires_action


def test_invalid_result_combinations_fail_closed() -> None:
    with pytest.raises(ValueError):
        AuthenticationResult(status=AuthenticationStatus.SUCCESS)
    with pytest.raises(ValueError):
        AuthenticationResult(status=AuthenticationStatus.FAILED)
