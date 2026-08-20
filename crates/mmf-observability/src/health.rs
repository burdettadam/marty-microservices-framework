use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::ObservabilityError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Unhealthy,
    Unknown,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct HealthCheckResult {
    pub name: String,
    pub status: HealthStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
    #[serde(default)]
    pub details: BTreeMap<String, Value>,
    pub timestamp_ms: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub duration_ms: Option<f64>,
}

impl HealthCheckResult {
    pub fn validate(&self) -> Result<(), ObservabilityError> {
        if self.name.trim().is_empty()
            || self
                .duration_ms
                .is_some_and(|duration| !duration.is_finite() || duration < 0.0)
        {
            return Err(ObservabilityError::HealthProbe(
                "health result requires a name and non-negative duration".into(),
            ));
        }
        Ok(())
    }
}

#[async_trait]
pub trait HealthProbe: Send + Sync {
    async fn check(&self, now_ms: u64) -> Result<HealthCheckResult, ObservabilityError>;
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ServiceMetrics {
    pub request_count: u64,
    pub error_count: u64,
    pub request_duration_ms_sum: f64,
    pub active_connections: u64,
    pub last_update_ms: u64,
}

impl ServiceMetrics {
    pub fn record_request(
        &mut self,
        duration_ms: f64,
        failed: bool,
        now_ms: u64,
    ) -> Result<(), ObservabilityError> {
        if !duration_ms.is_finite() || duration_ms < 0.0 {
            return Err(ObservabilityError::InvalidMetricValue(
                "request_duration_ms".into(),
            ));
        }
        self.request_count = self.request_count.saturating_add(1);
        self.error_count = self.error_count.saturating_add(u64::from(failed));
        self.request_duration_ms_sum += duration_ms;
        self.last_update_ms = now_ms;
        Ok(())
    }

    pub fn set_active_connections(&mut self, count: u64, now_ms: u64) {
        self.active_connections = count;
        self.last_update_ms = now_ms;
    }

    #[must_use]
    pub fn average_request_duration_ms(&self) -> f64 {
        if self.request_count == 0 {
            0.0
        } else {
            #[allow(clippy::cast_precision_loss)]
            let count = self.request_count as f64;
            self.request_duration_ms_sum / count
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ServiceHealthReport {
    pub service: String,
    pub status: HealthStatus,
    pub timestamp_ms: u64,
    pub checks: BTreeMap<String, HealthCheckResult>,
    pub metrics: ServiceMetrics,
}

impl ServiceHealthReport {
    #[must_use]
    pub fn aggregate(
        service: impl Into<String>,
        timestamp_ms: u64,
        checks: BTreeMap<String, HealthCheckResult>,
        metrics: ServiceMetrics,
    ) -> Self {
        let status = if checks
            .values()
            .any(|result| result.status == HealthStatus::Unhealthy)
        {
            HealthStatus::Unhealthy
        } else if checks
            .values()
            .any(|result| result.status == HealthStatus::Degraded)
        {
            HealthStatus::Degraded
        } else if checks
            .values()
            .any(|result| result.status == HealthStatus::Unknown)
        {
            HealthStatus::Unknown
        } else {
            HealthStatus::Healthy
        };
        Self {
            service: service.into(),
            status,
            timestamp_ms,
            checks,
            metrics,
        }
    }
}

#[derive(Default)]
pub struct MonitoringManager {
    service_name: String,
    probes: BTreeMap<String, Arc<dyn HealthProbe>>,
    metrics: Mutex<ServiceMetrics>,
}

impl MonitoringManager {
    #[must_use]
    pub fn new(service_name: impl Into<String>) -> Self {
        Self {
            service_name: service_name.into(),
            ..Self::default()
        }
    }

    pub fn add_probe(
        &mut self,
        name: impl Into<String>,
        probe: Arc<dyn HealthProbe>,
    ) -> Result<(), ObservabilityError> {
        let name = name.into();
        if name.trim().is_empty() {
            return Err(ObservabilityError::HealthProbe(
                "health probe name is required".into(),
            ));
        }
        self.probes.insert(name, probe);
        Ok(())
    }

    pub fn record_request(
        &self,
        duration_ms: f64,
        failed: bool,
        now_ms: u64,
    ) -> Result<(), ObservabilityError> {
        lock(&self.metrics).record_request(duration_ms, failed, now_ms)
    }

    pub async fn health(&self, now_ms: u64) -> ServiceHealthReport {
        let mut checks = BTreeMap::new();
        for (name, probe) in &self.probes {
            let result = match probe.check(now_ms).await {
                Ok(result) if result.validate().is_ok() => result,
                Ok(_) => failed_result(name, "health probe returned an invalid result", now_ms),
                Err(error) => failed_result(name, &error.to_string(), now_ms),
            };
            checks.insert(name.clone(), result);
        }
        ServiceHealthReport::aggregate(
            self.service_name.clone(),
            now_ms,
            checks,
            lock(&self.metrics).clone(),
        )
    }
}

fn failed_result(name: &str, message: &str, timestamp_ms: u64) -> HealthCheckResult {
    HealthCheckResult {
        name: name.into(),
        status: HealthStatus::Unhealthy,
        message: Some(format!("Health check failed: {message}")),
        details: BTreeMap::from([("error".into(), Value::String(message.into()))]),
        timestamp_ms,
        duration_ms: None,
    }
}

fn lock<T>(mutex: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}
