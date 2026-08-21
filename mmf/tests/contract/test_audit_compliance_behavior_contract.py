import json
from pathlib import Path

import pytest

from mmf.core.domain import ComplianceFramework, SecurityThreatLevel
from mmf.core.domain.audit_types import AuditSeverity
from mmf.services.audit.domain.entities import RequestAuditEvent
from mmf.services.audit_compliance.domain.models.compliance_scan_result import (
    ComplianceScanResult,
    Finding,
)
from mmf.services.audit_compliance.domain.models.threat_pattern import ThreatPattern


FIXTURE = json.loads(
    (Path(__file__).parents[3] / "contracts" / "audit-compliance-behavior.json").read_text()
)


def test_high_severity_forwarding_contract() -> None:
    assert FIXTURE["schema_version"] == 1
    for case in FIXTURE["forwarding"]:
        event = RequestAuditEvent(severity=AuditSeverity(case["severity"]))
        assert event.should_forward_to_compliance() is case["forward"]


def test_compliance_calculation_contract() -> None:
    case = FIXTURE["compliance"]
    findings = [
        Finding(
            rule_id=finding["rule_id"],
            rule_name=finding["rule_name"],
            severity=finding["severity"],
            status=finding["status"],
        )
        for finding in case["findings"]
    ]
    result = ComplianceScanResult(
        framework=ComplianceFramework(case["framework"]),
        scan_name="nightly",
        target_resource="gateway",
        target_type="service",
        overall_status=case["overall_status"],
        score=case["score"],
        findings=findings,
    )
    assert result.get_compliance_percentage() == pytest.approx(case["compliance_percentage"])
    assert len(result.get_critical_findings()) == case["critical_findings"]


def test_threat_pattern_accuracy_contract() -> None:
    case = FIXTURE["threat_pattern"]
    pattern = ThreatPattern(
        pattern_name="brute force",
        pattern_type="brute_force",
        threat_level=SecurityThreatLevel(case["threat_level"]),
        confidence_threshold=case["confidence_threshold"],
        trigger_count=case["trigger_count"],
        false_positive_count=case["false_positive_count"],
    )
    assert pattern.get_accuracy_rate() == pytest.approx(case["accuracy_rate"])
    assert pattern.is_high_confidence() is case["high_confidence"]
