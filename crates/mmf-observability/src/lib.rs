//! Canonical MMF observability contracts and provider-neutral implementation.
//!
//! Provider adapters may export these records to OpenTelemetry, Prometheus,
//! Jaeger, or platform logging, but correlation, redaction, metric semantics,
//! SLO math, and metadata have one implementation here.

#![forbid(unsafe_code)]

mod correlation;
mod metrics;
mod redaction;
mod slo;

use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Mutex};

pub use correlation::*;
pub use metrics::*;
use mmf_core::{ErrorCode, MmfError};
pub use redaction::*;
use serde::{Deserialize, Serialize};
use serde_json::Value;
pub use slo::*;
use thiserror::Error;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TelemetryExporter {
    Disabled,
    Stdout,
    OtlpGrpc,
    OtlpHttp,
    Jaeger,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LogFormat {
    Json,
    Text,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct ObservabilityConfig {
    pub service_name: String,
    pub service_version: String,
    pub environment: String,
    pub exporter: TelemetryExporter,
    pub endpoint: Option<String>,
    pub trace_sample_ratio: f64,
    pub log_format: LogFormat,
    pub metrics_enabled: bool,
    pub traces_enabled: bool,
    pub logs_enabled: bool,
    pub propagation: BTreeSet<String>,
    pub resource_attributes: BTreeMap<String, String>,
}

impl Default for ObservabilityConfig {
    fn default() -> Self {
        Self {
            service_name: "unknown".to_owned(),
            service_version: "0.0.0".to_owned(),
            environment: "development".to_owned(),
            exporter: TelemetryExporter::Disabled,
            endpoint: None,
            trace_sample_ratio: 1.0,
            log_format: LogFormat::Json,
            metrics_enabled: true,
            traces_enabled: true,
            logs_enabled: true,
            propagation: ["tracecontext", "baggage"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            resource_attributes: BTreeMap::new(),
        }
    }
}

impl ObservabilityConfig {
    pub fn validate(&self) -> Result<(), ObservabilityError> {
        if self.service_name.trim().is_empty()
            || self.service_version.trim().is_empty()
            || self.environment.trim().is_empty()
        {
            return Err(ObservabilityError::InvalidConfiguration(
                "service name, version, and environment are required".to_owned(),
            ));
        }
        if !self.trace_sample_ratio.is_finite() || !(0.0..=1.0).contains(&self.trace_sample_ratio) {
            return Err(ObservabilityError::InvalidConfiguration(
                "trace_sample_ratio must be between 0.0 and 1.0".to_owned(),
            ));
        }
        if matches!(
            self.exporter,
            TelemetryExporter::OtlpGrpc | TelemetryExporter::OtlpHttp | TelemetryExporter::Jaeger
        ) && self
            .endpoint
            .as_deref()
            .is_none_or(|endpoint| endpoint.trim().is_empty())
        {
            return Err(ObservabilityError::ExporterUnavailable(
                "selected exporter requires an endpoint".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LogLevel {
    Trace,
    Debug,
    Info,
    Warning,
    Error,
    Critical,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct LogEvent {
    pub timestamp: String,
    pub level: LogLevel,
    pub service: String,
    pub logger: String,
    pub message: String,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub correlation: BTreeMap<String, String>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub fields: BTreeMap<String, Value>,
}

impl LogEvent {
    #[must_use]
    pub fn redacted(&self, policy: &RedactionPolicy) -> Self {
        let fields = self
            .fields
            .iter()
            .map(|(key, value)| {
                let redacted = if policy.is_sensitive_key(key) {
                    Value::String(policy.replacement.clone())
                } else {
                    policy.redact(value)
                };
                (key.clone(), redacted)
            })
            .collect();
        Self {
            fields,
            ..self.clone()
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SpanKind {
    Internal,
    Server,
    Client,
    Producer,
    Consumer,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SpanStatus {
    Unset,
    Ok,
    Error,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SpanRecord {
    pub trace_id: String,
    pub span_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent_span_id: Option<String>,
    pub name: String,
    pub kind: SpanKind,
    pub status: SpanStatus,
    pub started_unix_nanos: u64,
    pub duration_nanos: u64,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
    #[serde(default)]
    pub events: Vec<SpanEvent>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SpanEvent {
    pub name: String,
    pub timestamp_unix_nanos: u64,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct BusinessMetric {
    pub name: String,
    pub value: f64,
    #[serde(default)]
    pub unit: String,
    #[serde(default)]
    pub dimensions: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AlertRule {
    pub name: String,
    pub expression: String,
    pub duration_seconds: u64,
    pub severity: AlertSeverity,
    pub summary: String,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
    #[serde(default)]
    pub annotations: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct DashboardDefinition {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub tags: BTreeSet<String>,
    #[serde(default)]
    pub panels: Vec<DashboardPanel>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct DashboardPanel {
    pub title: String,
    pub query: String,
    pub visualization: String,
    #[serde(default)]
    pub unit: String,
}

/// Provider boundary. Exporters consume already-normalized and redacted data.
pub trait TelemetrySink: Send + Sync {
    fn emit_log(&self, event: LogEvent) -> Result<(), ObservabilityError>;
    fn emit_span(&self, span: SpanRecord) -> Result<(), ObservabilityError>;
    fn emit_business_metric(&self, metric: BusinessMetric) -> Result<(), ObservabilityError>;
    fn flush(&self) -> Result<(), ObservabilityError>;
}

#[derive(Clone, Debug, Default)]
pub struct InMemoryTelemetrySink {
    logs: Arc<Mutex<Vec<LogEvent>>>,
    spans: Arc<Mutex<Vec<SpanRecord>>>,
    business_metrics: Arc<Mutex<Vec<BusinessMetric>>>,
}

impl InMemoryTelemetrySink {
    #[must_use]
    pub fn logs(&self) -> Vec<LogEvent> {
        lock(&self.logs).clone()
    }

    #[must_use]
    pub fn spans(&self) -> Vec<SpanRecord> {
        lock(&self.spans).clone()
    }

    #[must_use]
    pub fn business_metrics(&self) -> Vec<BusinessMetric> {
        lock(&self.business_metrics).clone()
    }
}

impl TelemetrySink for InMemoryTelemetrySink {
    fn emit_log(&self, event: LogEvent) -> Result<(), ObservabilityError> {
        lock(&self.logs).push(event);
        Ok(())
    }

    fn emit_span(&self, span: SpanRecord) -> Result<(), ObservabilityError> {
        lock(&self.spans).push(span);
        Ok(())
    }

    fn emit_business_metric(&self, metric: BusinessMetric) -> Result<(), ObservabilityError> {
        if !metric.value.is_finite() {
            return Err(ObservabilityError::InvalidMetricValue(metric.name));
        }
        lock(&self.business_metrics).push(metric);
        Ok(())
    }

    fn flush(&self) -> Result<(), ObservabilityError> {
        Ok(())
    }
}

fn lock<T>(mutex: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}

#[derive(Debug, Error)]
pub enum ObservabilityError {
    #[error("invalid trace context")]
    InvalidTraceContext,
    #[error("invalid metric name: {0}")]
    InvalidMetricName(String),
    #[error("invalid metric definition: {0}")]
    InvalidMetricDefinition(String),
    #[error("metric is not registered: {0}")]
    MetricNotRegistered(String),
    #[error("metric is already registered with a different definition: {0}")]
    MetricAlreadyRegistered(String),
    #[error("metric type mismatch: {0}")]
    MetricTypeMismatch(String),
    #[error("invalid metric value: {0}")]
    InvalidMetricValue(String),
    #[error("metric label mismatch: expected {expected:?}, got {actual:?}")]
    MetricLabelMismatch {
        expected: BTreeSet<String>,
        actual: BTreeSet<String>,
    },
    #[error("metric cardinality limit exceeded: {0}")]
    MetricCardinalityExceeded(String),
    #[error("invalid SLO target")]
    InvalidSloTarget,
    #[error("invalid SLI measurement")]
    InvalidSliMeasurement,
    #[error("invalid observability configuration: {0}")]
    InvalidConfiguration(String),
    #[error("telemetry exporter unavailable: {0}")]
    ExporterUnavailable(String),
    #[error("telemetry sink failed: {0}")]
    Sink(String),
}

impl From<ObservabilityError> for MmfError {
    fn from(error: ObservabilityError) -> Self {
        let code = match error {
            ObservabilityError::ExporterUnavailable(_) | ObservabilityError::Sink(_) => {
                ErrorCode::DependencyUnavailable
            }
            _ => ErrorCode::InvalidInput,
        };
        MmfError::new(code, error.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        correlation: CorrelationFixture,
        traceparent: TraceparentFixture,
        slo_cases: Vec<SloCase>,
        redaction: RedactionFixture,
    }

    #[derive(Deserialize)]
    struct CorrelationFixture {
        context: CorrelationContext,
        headers: BTreeMap<String, String>,
        log_fields: BTreeMap<String, String>,
    }

    #[derive(Deserialize)]
    struct TraceparentFixture {
        valid: Vec<String>,
        invalid: Vec<String>,
    }

    #[derive(Deserialize)]
    struct SloCase {
        target_percentage: f64,
        compliance_percentage: f64,
        total_budget: f64,
        consumed: f64,
        remaining: f64,
    }

    #[derive(Deserialize)]
    struct RedactionFixture {
        replacement: String,
        sensitive_keys: Vec<String>,
        safe_keys: Vec<String>,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/observability-behavior.json"
        ))
        .expect("valid observability fixture")
    }

    #[test]
    fn language_neutral_correlation_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        assert_eq!(
            fixture.correlation.context.to_headers(),
            fixture.correlation.headers
        );
        assert_eq!(
            fixture.correlation.context.to_log_fields(),
            fixture.correlation.log_fields
        );
    }

    #[test]
    fn language_neutral_traceparent_contract() {
        let fixture = fixture().traceparent;
        for traceparent in fixture.valid {
            let context = TraceContext::parse(&traceparent).expect("valid traceparent");
            assert_eq!(context.traceparent(), traceparent);
        }
        for traceparent in fixture.invalid {
            assert!(TraceContext::parse(&traceparent).is_err(), "{traceparent}");
        }
    }

    #[test]
    fn language_neutral_slo_contract() {
        for case in fixture().slo_cases {
            let budget =
                ErrorBudget::from_compliance(case.target_percentage, case.compliance_percentage)
                    .expect("valid SLO case");
            assert!((budget.total_budget - case.total_budget).abs() < 1e-9);
            assert!((budget.budget_consumed - case.consumed).abs() < 1e-9);
            assert!((budget.budget_remaining - case.remaining).abs() < 1e-9);
        }
    }

    #[test]
    fn redaction_is_recursive_and_fail_closed() {
        let fixture = fixture().redaction;
        let policy = RedactionPolicy::default();
        assert_eq!(policy.replacement, fixture.replacement);
        for key in fixture.sensitive_keys {
            assert!(policy.is_sensitive_key(&key), "{key}");
        }
        for key in fixture.safe_keys {
            assert!(!policy.is_sensitive_key(&key), "{key}");
        }
        let value = serde_json::json!({
            "nested": {"access_token": "secret"},
            "headers": ["Bearer abc"],
            "status": "ok"
        });
        assert_eq!(
            policy.redact(&value),
            serde_json::json!({
                "nested": {"access_token": "[REDACTED]"},
                "headers": ["[REDACTED]"],
                "status": "ok"
            })
        );
    }

    #[test]
    fn prometheus_registry_enforces_type_labels_and_cardinality() {
        let registry = MetricRegistry::default();
        registry
            .register(MetricDefinition {
                name: "requests_total".to_owned(),
                metric_type: MetricType::Counter,
                help: "Requests".to_owned(),
                namespace: "mmf".to_owned(),
                labels: ["route".to_owned()].into_iter().collect(),
                buckets: Vec::new(),
                max_series: 1,
            })
            .expect("register counter");
        registry
            .increment(
                "mmf_requests_total",
                BTreeMap::from([("route".to_owned(), "/health".to_owned())]),
                2.0,
            )
            .expect("increment");
        assert!(
            registry
                .increment(
                    "mmf_requests_total",
                    BTreeMap::from([("route".to_owned(), "/ready".to_owned())]),
                    1.0,
                )
                .is_err()
        );
        let rendered = registry.render_prometheus();
        assert!(rendered.contains("# TYPE mmf_requests_total counter"));
        assert!(rendered.contains("mmf_requests_total{route=\"/health\"} 2"));
    }
}
