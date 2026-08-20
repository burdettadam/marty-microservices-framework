use std::collections::{BTreeMap, BTreeSet};

use async_trait::async_trait;
use mmf_security::{AuditEvent as SecurityAuditEvent, ThreatDetectionResult, ThreatLevel};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::ServiceError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AuditSeverity {
    Info,
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AuditOutcome {
    Success,
    Failure,
    Error,
    Partial,
    Unknown,
}

#[derive(Clone, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(transparent)]
pub struct AuditEventType(pub String);

impl AuditEventType {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.0.trim().is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "audit event type is required".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct RequestContext {
    pub method: String,
    pub endpoint: String,
    pub source_ip: Option<String>,
    pub user_agent: Option<String>,
    pub request_id: Option<String>,
    pub correlation_id: Option<String>,
    pub trace_id: Option<String>,
    pub span_id: Option<String>,
    #[serde(default)]
    pub query_params: BTreeMap<String, Value>,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ResponseMetadata {
    pub status_code: u16,
    pub response_size: Option<u64>,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct PerformanceMetrics {
    pub duration_ms: f64,
    pub started_at_ms: u64,
    pub completed_at_ms: u64,
    #[serde(default)]
    pub is_slow_request: bool,
    #[serde(default)]
    pub is_large_response: bool,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ActorInfo {
    pub user_id: Option<String>,
    pub username: Option<String>,
    pub session_id: Option<String>,
    pub api_key_id: Option<String>,
    pub client_id: Option<String>,
    #[serde(default)]
    pub roles: BTreeSet<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ResourceInfo {
    pub resource_type: String,
    pub resource_id: Option<String>,
    #[serde(default)]
    pub action: String,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ServiceContext {
    pub service_name: String,
    pub environment: String,
    pub version: String,
    pub instance_id: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct RequestAuditEvent {
    pub event_id: String,
    pub event_type: AuditEventType,
    pub severity: AuditSeverity,
    pub outcome: AuditOutcome,
    pub timestamp_ms: u64,
    #[serde(default)]
    pub message: String,
    pub request_context: Option<RequestContext>,
    pub response_metadata: Option<ResponseMetadata>,
    pub performance_metrics: Option<PerformanceMetrics>,
    pub actor_info: Option<ActorInfo>,
    pub resource_info: Option<ResourceInfo>,
    pub service_context: Option<ServiceContext>,
    #[serde(default)]
    pub details: BTreeMap<String, Value>,
    #[serde(default)]
    pub encrypted_fields: BTreeSet<String>,
    pub security_event_id: Option<String>,
}

impl RequestAuditEvent {
    pub fn validate(&self) -> Result<(), ServiceError> {
        self.event_type.validate()?;
        if self.event_id.trim().is_empty() {
            return Err(ServiceError::InvalidConfiguration(
                "audit event id is required".into(),
            ));
        }
        if let Some(request) = &self.request_context
            && (request.method.trim().is_empty() || request.endpoint.trim().is_empty())
        {
            return Err(ServiceError::InvalidConfiguration(
                "audit request method and endpoint are required".into(),
            ));
        }
        if let Some(performance) = &self.performance_metrics
            && (!performance.duration_ms.is_finite()
                || performance.duration_ms < 0.0
                || performance.completed_at_ms < performance.started_at_ms)
        {
            return Err(ServiceError::InvalidConfiguration(
                "audit performance metrics are invalid".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub const fn should_forward_to_compliance(&self) -> bool {
        matches!(self.severity, AuditSeverity::High | AuditSeverity::Critical)
    }

    #[must_use]
    pub fn security_event(&self) -> SecurityAuditEvent {
        SecurityAuditEvent {
            event_id: self.event_id.clone(),
            event_type: self.event_type.0.clone(),
            timestamp_ms: self.timestamp_ms,
            actor_id: self
                .actor_info
                .as_ref()
                .and_then(|actor| actor.user_id.clone()),
            action: self
                .resource_info
                .as_ref()
                .map_or_else(String::new, |resource| resource.action.clone()),
            resource: self
                .resource_info
                .as_ref()
                .map_or_else(String::new, |resource| resource.resource_type.clone()),
            outcome: serde_json::to_value(self.outcome)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_else(|| "unknown".into()),
            request_id: self
                .request_context
                .as_ref()
                .and_then(|request| request.request_id.clone()),
            source_ip: self
                .request_context
                .as_ref()
                .and_then(|request| request.source_ip.clone()),
            details: self.details.clone(),
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ComplianceFramework {
    Gdpr,
    Hipaa,
    Sox,
    PciDss,
    Iso27001,
    Nist,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FindingStatus {
    Pass,
    Fail,
    Warning,
    Info,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Finding {
    pub rule_id: String,
    pub rule_name: String,
    pub severity: AuditSeverity,
    pub status: FindingStatus,
    pub resource_id: Option<String>,
    pub resource_type: Option<String>,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub remediation: String,
    #[serde(default)]
    pub evidence: BTreeMap<String, Value>,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ComplianceStatus {
    Compliant,
    NonCompliant,
    PartiallyCompliant,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ComplianceScanResult {
    pub scan_id: String,
    pub framework: ComplianceFramework,
    pub scan_name: String,
    pub target_resource: String,
    pub target_type: String,
    pub overall_status: ComplianceStatus,
    pub score: f64,
    #[serde(default)]
    pub findings: Vec<Finding>,
    #[serde(default)]
    pub recommendations: Vec<String>,
    pub scan_duration_seconds: Option<f64>,
    pub scanned_by: Option<String>,
    #[serde(default)]
    pub scan_configuration: BTreeMap<String, Value>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl ComplianceScanResult {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.scan_id.trim().is_empty()
            || self.scan_name.trim().is_empty()
            || self.target_resource.trim().is_empty()
            || self.target_type.trim().is_empty()
            || !self.score.is_finite()
            || !(0.0..=100.0).contains(&self.score)
            || self
                .scan_duration_seconds
                .is_some_and(|duration| !duration.is_finite() || duration < 0.0)
            || self.findings.iter().any(|finding| {
                finding.rule_id.trim().is_empty() || finding.rule_name.trim().is_empty()
            })
        {
            return Err(ServiceError::InvalidConfiguration(
                "compliance scan result is invalid".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn compliance_percentage(&self) -> f64 {
        if self.findings.is_empty() {
            return 100.0;
        }
        #[allow(clippy::cast_precision_loss)]
        let passed = self
            .findings
            .iter()
            .filter(|finding| finding.status == FindingStatus::Pass)
            .count() as f64;
        #[allow(clippy::cast_precision_loss)]
        let total = self.findings.len() as f64;
        passed / total * 100.0
    }

    #[must_use]
    pub fn critical_findings(&self) -> Vec<&Finding> {
        self.findings
            .iter()
            .filter(|finding| finding.severity == AuditSeverity::Critical)
            .collect()
    }

    #[must_use]
    pub const fn is_compliant(&self) -> bool {
        matches!(self.overall_status, ComplianceStatus::Compliant)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ThreatIndicator {
    pub indicator_type: String,
    pub value: String,
    pub weight: f64,
    #[serde(default)]
    pub description: String,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ThreatPattern {
    pub pattern_id: String,
    pub pattern_name: String,
    pub pattern_type: String,
    pub threat_level: ThreatLevel,
    pub confidence_threshold: f64,
    #[serde(default)]
    pub indicators: Vec<ThreatIndicator>,
    #[serde(default)]
    pub associated_event_types: BTreeSet<String>,
    pub time_window_minutes: u64,
    pub minimum_events: usize,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub remediation_steps: Vec<String>,
    pub is_active: bool,
    pub created_by: Option<String>,
    pub last_triggered_ms: Option<u64>,
    pub trigger_count: u64,
    pub false_positive_count: u64,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl ThreatPattern {
    pub fn validate(&self) -> Result<(), ServiceError> {
        if self.pattern_id.trim().is_empty()
            || self.pattern_name.trim().is_empty()
            || self.pattern_type.trim().is_empty()
            || !self.confidence_threshold.is_finite()
            || !(0.0..=1.0).contains(&self.confidence_threshold)
            || self.time_window_minutes == 0
            || self.minimum_events == 0
            || self.indicators.iter().any(|indicator| {
                indicator.indicator_type.trim().is_empty()
                    || indicator.value.trim().is_empty()
                    || !indicator.weight.is_finite()
                    || !(0.0..=1.0).contains(&indicator.weight)
            })
        {
            return Err(ServiceError::InvalidConfiguration(
                "threat pattern is invalid".into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn accuracy_rate(&self) -> f64 {
        let total = self.trigger_count.saturating_add(self.false_positive_count);
        if total == 0 {
            1.0
        } else {
            #[allow(clippy::cast_precision_loss)]
            let triggers = self.trigger_count as f64;
            #[allow(clippy::cast_precision_loss)]
            let total = total as f64;
            triggers / total
        }
    }

    pub fn record_trigger(&mut self, now_ms: u64) {
        self.last_triggered_ms = Some(now_ms);
        self.trigger_count = self.trigger_count.saturating_add(1);
    }

    pub fn record_false_positive(&mut self) {
        self.false_positive_count = self.false_positive_count.saturating_add(1);
    }

    pub fn deactivate(&mut self, reason: Option<String>) {
        self.is_active = false;
        if let Some(reason) = reason {
            self.metadata
                .insert("deactivation_reason".into(), Value::String(reason));
        }
    }

    pub fn activate(&mut self) {
        self.is_active = true;
        self.metadata.remove("deactivation_reason");
    }
}

#[async_trait]
pub trait AuditRepository: Send + Sync {
    async fn save(&self, event: &RequestAuditEvent) -> Result<(), ServiceError>;
    async fn query(&self, query: &AuditQuery) -> Result<Vec<RequestAuditEvent>, ServiceError>;
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct AuditQuery {
    pub event_types: BTreeSet<AuditEventType>,
    pub severities: BTreeSet<AuditSeverity>,
    pub actor_id: Option<String>,
    pub resource: Option<String>,
    pub from_ms: Option<u64>,
    pub to_ms: Option<u64>,
    pub limit: usize,
    pub offset: usize,
}

#[async_trait]
pub trait AuditDestination: Send + Sync {
    async fn write(&self, event: &RequestAuditEvent) -> Result<(), ServiceError>;
    async fn flush(&self) -> Result<(), ServiceError>;
}

#[async_trait]
pub trait AuditEncryptionProvider: Send + Sync {
    async fn encrypt_fields(
        &self,
        event: &RequestAuditEvent,
        fields: &BTreeSet<String>,
    ) -> Result<RequestAuditEvent, ServiceError>;
}

#[async_trait]
pub trait ComplianceScanner: Send + Sync {
    async fn scan(
        &self,
        framework: ComplianceFramework,
        target_resource: &str,
        target_type: &str,
    ) -> Result<ComplianceScanResult, ServiceError>;
}

#[async_trait]
pub trait SiemAdapter: Send + Sync {
    async fn send_audit_event(&self, event: &SecurityAuditEvent) -> Result<(), ServiceError>;
    async fn send_threat_result(&self, result: &ThreatDetectionResult) -> Result<(), ServiceError>;
}

#[async_trait]
pub trait SecurityReportGenerator: Send + Sync {
    async fn generate(
        &self,
        events: &[SecurityAuditEvent],
        scans: &[ComplianceScanResult],
        threats: &[ThreatDetectionResult],
    ) -> Result<Value, ServiceError>;
}
