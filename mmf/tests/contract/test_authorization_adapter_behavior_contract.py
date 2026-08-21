"""Behavior contract retained while authorization consumers move to Rust."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mmf.framework.authorization.adapters.abac_engine import AttributeCondition
from mmf.framework.authorization.adapters.rbac_engine import RBACManager, Role
from mmf.framework.authorization.api import ConditionOperator
from mmf.framework.authorization.domain.models import Permission
from mmf.framework.authorization.engines.acl import ACLEntry
from mmf.framework.authorization.engines.base import SecurityContext, SecurityPrincipal
from mmf.framework.authorization.engines.opa import OPAPolicyEngine


CONTRACT = json.loads(
    (Path(__file__).parents[3] / "contracts" / "authorization-adapter-behavior.json").read_text(
        encoding="utf-8"
    )
)


def test_structured_permission_vectors() -> None:
    for case in CONTRACT["structured_permissions"]:
        permission = Permission.from_string(case["permission"])
        assert permission.matches(*case["request"]) is case["allowed"]
        assert Permission.from_string(permission.to_string()) == permission


def test_rbac_system_roles_assignment_and_inheritance() -> None:
    case = CONTRACT["rbac"]
    rbac = RBACManager()
    assert set(case["system_roles"]) <= set(rbac.roles)
    role = Role(
        name=case["assigned_role"],
        description="Can deploy releases",
        permissions={Permission.from_string("service:*:deploy")},
        inherits_from={case["parent_role"]},
    )
    assert rbac.add_role(role)
    assert rbac.assign_role_to_user(case["user"], case["assigned_role"])
    assert case["parent_role"] in rbac.get_user_effective_roles(case["user"])
    assert rbac.check_permission(case["user"], *case["allowed_request"])
    assert rbac.check_permission(case["user"], *case["inherited_request"])
    assert not rbac.check_permission(case["user"], *case["denied_request"])


def test_nested_and_regex_abac_conditions() -> None:
    case = CONTRACT["abac"]
    nested = AttributeCondition(case["nested_path"], ConditionOperator.EQUALS, case["nested_value"])
    regex = AttributeCondition(case["regex_path"], ConditionOperator.REGEX, case["regex"])
    assert nested.evaluate({"profile": {"department": case["nested_value"]}})
    assert regex.evaluate({"email": case["matching_email"]})
    assert not regex.evaluate({"email": case["non_matching_email"]})


def test_acl_resource_principal_ip_method_and_attribute_conditions() -> None:
    case = CONTRACT["acl"]
    entry = ACLEntry(
        resource_pattern=case["resource_pattern"],
        principal=case["principal"],
        permissions={case["permission"]},
        conditions={
            "ip_range": [case["ip_range"]],
            "request_method": [case["request_method"]],
            "resource_attributes": case["resource_attribute"],
        },
    )
    principal = SecurityPrincipal(id="alice", type="user", roles={"editor"})
    context = SecurityContext(
        principal=principal,
        resource=case["matching_resource"],
        action=case["permission"],
        request_metadata={
            "client_ip": case["matching_ip"],
            "request_method": case["request_method"].lower(),
            "resource_attributes": {"classification": "internal"},
        },
    )
    assert entry.matches_resource(case["matching_resource"])
    assert not entry.matches_resource(case["non_matching_resource"])
    assert entry.matches_principal("alice", {"editor"}, set())
    assert entry.evaluate_conditions(context)
    context.request_metadata["client_ip"] = case["non_matching_ip"]
    assert not entry.evaluate_conditions(context)


def test_unimplemented_python_external_engine_denies() -> None:
    context = SecurityContext(
        principal=SecurityPrincipal(id="alice", type="user"), resource="document", action="read"
    )
    decision = asyncio.run(OPAPolicyEngine().evaluate_policy(context))
    assert decision.allowed is CONTRACT["external_policy_backend"]["python_placeholder_decision"]
