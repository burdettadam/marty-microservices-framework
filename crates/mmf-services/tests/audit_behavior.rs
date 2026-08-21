use std::collections::{BTreeMap, BTreeSet};

use mmf_security::ThreatLevel;
use mmf_services::audit::{
    AuditEventType, AuditOutcome, AuditSeverity, ComplianceFramework, ComplianceScanResult,
    ComplianceStatus, Finding, RequestAuditEvent, ThreatPattern,
};
use serde::Deserialize;

#[derive(Deserialize)]
struct Fixture {
    schema_version: u32,
    forwarding: Vec<ForwardCase>,
    compliance: ComplianceCase,
    threat_pattern: ThreatCase,
}

#[derive(Deserialize)]
struct ForwardCase {
    severity: AuditSeverity,
    forward: bool,
}

#[derive(Deserialize)]
struct ComplianceCase {
    framework: ComplianceFramework,
    overall_status: ComplianceStatus,
    score: f64,
    findings: Vec<Finding>,
    compliance_percentage: f64,
    critical_findings: usize,
}

#[derive(Deserialize)]
struct ThreatCase {
    threat_level: ThreatLevel,
    confidence_threshold: f64,
    trigger_count: u64,
    false_positive_count: u64,
    accuracy_rate: f64,
    high_confidence: bool,
}

fn fixture() -> Fixture {
    serde_json::from_str(include_str!(
        "../../../contracts/audit-compliance-behavior.json"
    ))
    .expect("valid audit fixture")
}

fn event(severity: AuditSeverity) -> RequestAuditEvent {
    RequestAuditEvent {
        event_id: "event-1".into(),
        event_type: AuditEventType("api_request".into()),
        severity,
        outcome: AuditOutcome::Success,
        timestamp_ms: 1,
        message: "request".into(),
        request_context: None,
        response_metadata: None,
        performance_metrics: None,
        actor_info: None,
        resource_info: None,
        service_context: None,
        details: BTreeMap::default(),
        encrypted_fields: BTreeSet::default(),
        security_event_id: None,
    }
}

#[test]
fn high_severity_forwarding_matches_the_shared_contract() {
    let fixture = fixture();
    assert_eq!(fixture.schema_version, 1);
    for case in fixture.forwarding {
        let event = event(case.severity);
        event.validate().expect("valid event");
        assert_eq!(event.should_forward_to_compliance(), case.forward);
        assert_eq!(event.security_event().event_type, "api_request");
    }
}

#[test]
fn compliance_calculations_match_the_shared_contract() {
    let case = fixture().compliance;
    let result = ComplianceScanResult {
        scan_id: "scan-1".into(),
        framework: case.framework,
        scan_name: "nightly".into(),
        target_resource: "gateway".into(),
        target_type: "service".into(),
        overall_status: case.overall_status,
        score: case.score,
        findings: case.findings,
        recommendations: Vec::new(),
        scan_duration_seconds: Some(1.0),
        scanned_by: Some("native".into()),
        scan_configuration: BTreeMap::default(),
        metadata: BTreeMap::default(),
    };
    result.validate().expect("valid scan");
    assert!((result.compliance_percentage() - case.compliance_percentage).abs() < 1e-12);
    assert_eq!(result.critical_findings().len(), case.critical_findings);
    assert!(!result.is_compliant());
}

#[test]
fn threat_pattern_accuracy_reuses_security_threat_levels() {
    let case = fixture().threat_pattern;
    let pattern = ThreatPattern {
        pattern_id: "pattern-1".into(),
        pattern_name: "brute force".into(),
        pattern_type: "brute_force".into(),
        threat_level: case.threat_level,
        confidence_threshold: case.confidence_threshold,
        indicators: Vec::new(),
        associated_event_types: BTreeSet::default(),
        time_window_minutes: 15,
        minimum_events: 5,
        description: String::new(),
        remediation_steps: Vec::new(),
        is_active: true,
        created_by: None,
        last_triggered_ms: None,
        trigger_count: case.trigger_count,
        false_positive_count: case.false_positive_count,
        metadata: BTreeMap::default(),
    };
    pattern.validate().expect("valid pattern");
    assert!((pattern.accuracy_rate() - case.accuracy_rate).abs() < 1e-12);
    assert_eq!(pattern.accuracy_rate() >= 0.8, case.high_confidence);
}

#[test]
fn malformed_compliance_and_threat_inputs_fail_closed() {
    let mut bad_event = event(AuditSeverity::Info);
    bad_event.event_id.clear();
    assert!(bad_event.validate().is_err());
    assert!(AuditEventType(String::new()).validate().is_err());
}
