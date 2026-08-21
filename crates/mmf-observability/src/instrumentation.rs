use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

use serde::{Deserialize, Serialize};

use crate::{ObservabilityConfig, ObservabilityError, TelemetrySink};

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InstrumentationTarget {
    HttpServer,
    HttpClient,
    GrpcServer,
    GrpcClient,
    Sql,
    Redis,
    Kafka,
    Messaging,
    Cache,
    Runtime,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct InstrumentationConfig {
    #[serde(default)]
    pub enabled_targets: BTreeSet<InstrumentationTarget>,
    #[serde(default)]
    pub excluded_paths: BTreeSet<String>,
    #[serde(default)]
    pub capture_request_headers: BTreeSet<String>,
    #[serde(default)]
    pub capture_response_headers: BTreeSet<String>,
    #[serde(default)]
    pub static_attributes: BTreeMap<String, String>,
}

impl InstrumentationConfig {
    pub fn validate(&self) -> Result<(), ObservabilityError> {
        if self
            .capture_request_headers
            .iter()
            .chain(&self.capture_response_headers)
            .any(|header| is_sensitive_header(header))
        {
            return Err(ObservabilityError::InvalidConfiguration(
                "sensitive HTTP headers cannot be captured".into(),
            ));
        }
        if self
            .excluded_paths
            .iter()
            .any(|path| !path.starts_with('/'))
        {
            return Err(ObservabilityError::InvalidConfiguration(
                "excluded HTTP paths must be absolute".into(),
            ));
        }
        Ok(())
    }
}

fn is_sensitive_header(header: &str) -> bool {
    matches!(
        header.to_ascii_lowercase().as_str(),
        "authorization" | "proxy-authorization" | "cookie" | "set-cookie" | "x-api-key"
    )
}

pub trait InstrumentationProvider: Send + Sync {
    fn initialize(
        &self,
        observability: &ObservabilityConfig,
        instrumentation: &InstrumentationConfig,
    ) -> Result<Arc<dyn TelemetrySink>, ObservabilityError>;

    fn instrument(&self, target: InstrumentationTarget) -> Result<(), ObservabilityError>;

    fn shutdown(&self) -> Result<(), ObservabilityError>;
}

pub trait SystemMetricsProvider: Send + Sync {
    fn snapshot(&self) -> Result<SystemMetricsSnapshot, ObservabilityError>;
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SystemMetricsSnapshot {
    pub timestamp_ms: u64,
    pub cpu_usage: f64,
    pub memory_usage: f64,
    pub disk_usage: f64,
    pub network_receive_bytes: u64,
    pub network_transmit_bytes: u64,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
}

impl SystemMetricsSnapshot {
    pub fn validate(&self) -> Result<(), ObservabilityError> {
        if [self.cpu_usage, self.memory_usage, self.disk_usage]
            .iter()
            .any(|value| !value.is_finite() || !(0.0..=1.0).contains(value))
        {
            return Err(ObservabilityError::InvalidMetricValue(
                "system utilization".into(),
            ));
        }
        Ok(())
    }
}

pub trait NotificationChannel: Send + Sync {
    fn notify(&self, payload: &NotificationPayload) -> Result<(), ObservabilityError>;
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct NotificationPayload {
    pub title: String,
    pub body: String,
    pub severity: String,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
}
