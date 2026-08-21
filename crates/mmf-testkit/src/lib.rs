//! Deterministic, provider-neutral test tooling for MMF.

#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TestType {
    Unit,
    Integration,
    Contract,
    EndToEnd,
    Performance,
    Security,
    Chaos,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TestStatus {
    Pending,
    Running,
    Passed,
    Failed,
    Skipped,
    Error,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TestSeverity {
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct TestMetrics {
    pub duration_ms: u64,
    pub assertions: u64,
    pub passed_assertions: u64,
    pub failed_assertions: u64,
    #[serde(default)]
    pub custom: BTreeMap<String, f64>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct TestResult {
    pub id: String,
    pub name: String,
    pub test_type: TestType,
    pub status: TestStatus,
    pub severity: TestSeverity,
    pub started_at_ms: u64,
    pub completed_at_ms: Option<u64>,
    pub message: Option<String>,
    #[serde(default)]
    pub details: Value,
    #[serde(default)]
    pub metrics: TestMetrics,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PerformanceTestType {
    Load,
    Stress,
    Spike,
    Endurance,
    Scalability,
    Volume,
    Baseline,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum LoadPattern {
    Constant,
    RampUp,
    RampDown,
    Step,
    Spike,
    Wave,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RequestSpec {
    pub method: String,
    pub url: String,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    #[serde(default)]
    pub query: BTreeMap<String, String>,
    #[serde(default)]
    pub body: Value,
    pub timeout_ms: u64,
    #[serde(default = "default_success_statuses")]
    pub expected_status_codes: BTreeSet<u16>,
}

fn default_success_statuses() -> BTreeSet<u16> {
    BTreeSet::from([200])
}

impl RequestSpec {
    pub fn validate(&self) -> Result<(), TestkitError> {
        if self.method.trim().is_empty()
            || !(self.url.starts_with("http://") || self.url.starts_with("https://"))
            || self.timeout_ms == 0
            || self.expected_status_codes.is_empty()
        {
            return Err(TestkitError::InvalidConfiguration(
                "request requires method, HTTP(S) URL, and timeout".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct LoadConfiguration {
    pub pattern: LoadPattern,
    pub users: u32,
    pub duration_ms: u64,
    pub ramp_up_ms: u64,
    pub requests_per_second: Option<f64>,
    pub think_time_min_ms: u64,
    pub think_time_max_ms: u64,
    pub step_users: u32,
    pub step_interval_ms: u64,
    pub spike_users: u32,
}

impl LoadConfiguration {
    pub fn validate(&self) -> Result<(), TestkitError> {
        if self.users == 0
            || self.duration_ms == 0
            || self.think_time_min_ms > self.think_time_max_ms
            || self
                .requests_per_second
                .is_some_and(|rate| rate <= 0.0 || !rate.is_finite())
        {
            return Err(TestkitError::InvalidConfiguration(
                "load configuration has invalid users, duration, rate, or think time".to_owned(),
            ));
        }
        if matches!(self.pattern, LoadPattern::RampUp | LoadPattern::RampDown)
            && self.ramp_up_ms == 0
            || matches!(self.pattern, LoadPattern::Step)
                && (self.step_users == 0 || self.step_interval_ms == 0)
            || matches!(self.pattern, LoadPattern::Spike) && self.spike_users == 0
        {
            return Err(TestkitError::InvalidConfiguration(
                "selected load pattern requires nonzero pattern parameters".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn users_at(&self, elapsed_ms: u64) -> u32 {
        if elapsed_ms >= self.duration_ms {
            return 0;
        }
        match self.pattern {
            LoadPattern::Constant => self.users,
            LoadPattern::RampUp => {
                let elapsed = elapsed_ms.min(self.ramp_up_ms);
                u32::try_from(
                    u64::from(self.users).saturating_mul(elapsed) / self.ramp_up_ms.max(1),
                )
                .unwrap_or(self.users)
                .max(1)
            }
            LoadPattern::RampDown => {
                let elapsed = elapsed_ms.min(self.ramp_up_ms);
                self.users.saturating_sub(
                    u32::try_from(
                        u64::from(self.users).saturating_mul(elapsed) / self.ramp_up_ms.max(1),
                    )
                    .unwrap_or(self.users),
                )
            }
            LoadPattern::Step => u32::try_from(elapsed_ms / self.step_interval_ms.max(1))
                .unwrap_or(u32::MAX)
                .saturating_add(1)
                .saturating_mul(self.step_users)
                .min(self.users),
            LoadPattern::Spike => {
                if elapsed_ms >= self.duration_ms / 3 && elapsed_ms < self.duration_ms * 2 / 3 {
                    self.spike_users
                } else {
                    self.users
                }
            }
            LoadPattern::Wave => {
                let phase = elapsed_ms.saturating_mul(4) / self.duration_ms.max(1);
                if phase.is_multiple_of(2) {
                    self.users
                } else {
                    self.users.div_ceil(2)
                }
            }
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ResponseMetric {
    pub started_at_ms: u64,
    pub duration_ms: u64,
    pub status_code: Option<u16>,
    pub bytes: u64,
    pub error: Option<String>,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct PerformanceMetrics {
    pub total_requests: u64,
    pub successful_requests: u64,
    pub failed_requests: u64,
    pub requests_per_second: f64,
    pub mean_response_ms: f64,
    pub minimum_response_ms: u64,
    pub maximum_response_ms: u64,
    pub p50_response_ms: f64,
    pub p95_response_ms: f64,
    pub p99_response_ms: f64,
    pub bytes_transferred: u64,
    pub error_rate: f64,
}

#[derive(Clone, Debug, Default)]
pub struct MetricsCollector {
    metrics: Vec<ResponseMetric>,
}

impl MetricsCollector {
    pub fn record(&mut self, metric: ResponseMetric) {
        self.metrics.push(metric);
    }

    #[must_use]
    pub fn aggregate(&self, elapsed_ms: u64) -> PerformanceMetrics {
        if self.metrics.is_empty() {
            return PerformanceMetrics::default();
        }
        let mut durations = self
            .metrics
            .iter()
            .filter(|metric| metric.error.is_none())
            .map(|metric| metric.duration_ms)
            .collect::<Vec<_>>();
        durations.sort_unstable();
        let total = self.metrics.len() as u64;
        let success = durations.len() as u64;
        let failed = total - success;
        let duration_sum = durations.iter().sum::<u64>();
        PerformanceMetrics {
            total_requests: total,
            successful_requests: success,
            failed_requests: failed,
            requests_per_second: metric_float(total) / (metric_float(elapsed_ms.max(1)) / 1_000.0),
            mean_response_ms: if success == 0 {
                0.0
            } else {
                metric_float(duration_sum) / metric_float(success)
            },
            minimum_response_ms: durations.first().copied().unwrap_or_default(),
            maximum_response_ms: durations.last().copied().unwrap_or_default(),
            p50_response_ms: percentile(&durations, 50),
            p95_response_ms: percentile(&durations, 95),
            p99_response_ms: percentile(&durations, 99),
            bytes_transferred: self.metrics.iter().map(|metric| metric.bytes).sum(),
            error_rate: metric_float(failed) / metric_float(total),
        }
    }
}

fn percentile(values: &[u64], percentile: u32) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let span = values.len().saturating_sub(1);
    let scaled = span.saturating_mul(usize::try_from(percentile).unwrap_or(100));
    let lower = scaled / 100;
    let remainder = scaled % 100;
    let upper = (lower + usize::from(remainder > 0)).min(values.len() - 1);
    let fraction = f64::from(u32::try_from(remainder).unwrap_or(100)) / 100.0;
    metric_float(values[lower])
        + (metric_float(values[upper]) - metric_float(values[lower])) * fraction
}

fn metric_float(value: u64) -> f64 {
    f64::from(u32::try_from(value).unwrap_or(u32::MAX))
}

#[async_trait]
pub trait RequestExecutor: Send + Sync {
    async fn execute(&self, request: &RequestSpec, user_id: u32, sequence: u64) -> ResponseMetric;
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ContractType {
    Http,
    Grpc,
    Event,
    MessageQueue,
    Graphql,
    Websocket,
    Database,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum VerificationLevel {
    Lenient,
    Standard,
    Strict,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ContractRequest {
    pub method: String,
    pub path: String,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    #[serde(default)]
    pub body: Value,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ContractResponse {
    pub status_code: u16,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
    #[serde(default)]
    pub body: Value,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ContractInteraction {
    pub description: String,
    pub provider_state: Option<String>,
    pub request: ContractRequest,
    pub response: ContractResponse,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Contract {
    pub consumer: String,
    pub provider: String,
    pub version: String,
    pub contract_type: ContractType,
    pub interactions: Vec<ContractInteraction>,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

impl Contract {
    pub fn validate(&self) -> Result<(), TestkitError> {
        if self.consumer.trim().is_empty()
            || self.provider.trim().is_empty()
            || self.version.trim().is_empty()
            || self.interactions.is_empty()
        {
            return Err(TestkitError::InvalidContract(
                "contract requires parties, version, and interactions".to_owned(),
            ));
        }
        for interaction in &self.interactions {
            if interaction.description.trim().is_empty()
                || interaction.request.method.trim().is_empty()
                || !interaction.request.path.starts_with('/')
                || !(100..=599).contains(&interaction.response.status_code)
            {
                return Err(TestkitError::InvalidContract(
                    "interaction contains invalid description, request, or status".to_owned(),
                ));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ContractMismatch {
    pub path: String,
    pub expected: String,
    pub actual: String,
}

#[must_use]
pub fn verify_response(
    expected: &ContractResponse,
    actual: &ContractResponse,
    level: VerificationLevel,
) -> Vec<ContractMismatch> {
    let mut mismatches = Vec::new();
    if expected.status_code != actual.status_code {
        mismatches.push(mismatch(
            "status",
            &expected.status_code,
            &actual.status_code,
        ));
    }
    for (name, value) in &expected.headers {
        if actual.headers.get(name) != Some(value) {
            mismatches.push(ContractMismatch {
                path: format!("headers.{name}"),
                expected: value.clone(),
                actual: actual
                    .headers
                    .get(name)
                    .cloned()
                    .unwrap_or_else(|| "<missing>".to_owned()),
            });
        }
    }
    compare_value("body", &expected.body, &actual.body, level, &mut mismatches);
    mismatches
}

fn compare_value(
    path: &str,
    expected: &Value,
    actual: &Value,
    level: VerificationLevel,
    mismatches: &mut Vec<ContractMismatch>,
) {
    match (expected, actual) {
        (Value::Object(expected), Value::Object(actual)) => {
            for (key, value) in expected {
                if let Some(actual) = actual.get(key) {
                    compare_value(&format!("{path}.{key}"), value, actual, level, mismatches);
                } else {
                    mismatches.push(ContractMismatch {
                        path: format!("{path}.{key}"),
                        expected: value.to_string(),
                        actual: "<missing>".to_owned(),
                    });
                }
            }
            if level == VerificationLevel::Strict {
                for key in actual.keys().filter(|key| !expected.contains_key(*key)) {
                    mismatches.push(ContractMismatch {
                        path: format!("{path}.{key}"),
                        expected: "<absent>".to_owned(),
                        actual: actual[key].to_string(),
                    });
                }
            }
        }
        _ if expected != actual => mismatches.push(ContractMismatch {
            path: path.to_owned(),
            expected: expected.to_string(),
            actual: actual.to_string(),
        }),
        _ => {}
    }
}

fn mismatch(path: &str, expected: &impl ToString, actual: &impl ToString) -> ContractMismatch {
    ContractMismatch {
        path: path.to_owned(),
        expected: expected.to_string(),
        actual: actual.to_string(),
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ChaosType {
    NetworkDelay,
    NetworkLoss,
    NetworkPartition,
    ServiceKill,
    ResourceExhaustion,
    CpuExhaustion,
    MemoryExhaustion,
    IoExhaustion,
    DiskFailure,
    DnsFailure,
    DependencyFailure,
    ClockSkew,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ChaosScope {
    SingleInstance,
    MultipleInstances,
    EntireService,
    RandomSelection,
    PercentageBased,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ExperimentPhase {
    Created,
    Baseline,
    Injecting,
    Observing,
    Recovering,
    Verifying,
    Completed,
    Failed,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ChaosTarget {
    pub id: String,
    pub service: String,
    pub instance: Option<String>,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ChaosParameters {
    pub duration_ms: u64,
    pub intensity: f64,
    pub latency_ms: Option<u64>,
    pub loss_percent: Option<f64>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl ChaosParameters {
    pub fn validate(&self) -> Result<(), TestkitError> {
        if self.duration_ms == 0
            || !(0.0..=1.0).contains(&self.intensity)
            || self
                .loss_percent
                .is_some_and(|loss| !(0.0..=100.0).contains(&loss))
        {
            return Err(TestkitError::InvalidConfiguration(
                "invalid chaos duration, intensity, or loss".to_owned(),
            ));
        }
        Ok(())
    }
}

#[async_trait]
pub trait ChaosProvider: Send + Sync {
    async fn inject(
        &self,
        chaos_type: ChaosType,
        targets: &[ChaosTarget],
        parameters: &ChaosParameters,
    ) -> Result<String, TestkitError>;
    async fn recover(&self, injection_id: &str) -> Result<(), TestkitError>;
    async fn cleanup(&self, injection_id: &str) -> Result<(), TestkitError>;
}

#[async_trait]
pub trait SteadyStateProbe: Send + Sync {
    fn name(&self) -> &str;
    async fn check(&self) -> Result<bool, TestkitError>;
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ChaosExperiment {
    pub id: String,
    pub name: String,
    pub chaos_type: ChaosType,
    pub scope: ChaosScope,
    pub targets: Vec<ChaosTarget>,
    pub parameters: ChaosParameters,
    pub phase: ExperimentPhase,
    pub injection_id: Option<String>,
}

impl ChaosExperiment {
    pub async fn run(
        &mut self,
        provider: &dyn ChaosProvider,
        probes: &[Arc<dyn SteadyStateProbe>],
    ) -> Result<(), TestkitError> {
        self.parameters.validate()?;
        if self.id.trim().is_empty() || self.targets.is_empty() {
            return Err(TestkitError::InvalidConfiguration(
                "chaos experiment requires ID and targets".to_owned(),
            ));
        }
        self.phase = ExperimentPhase::Baseline;
        for probe in probes {
            if !probe.check().await? {
                self.phase = ExperimentPhase::Failed;
                return Err(TestkitError::SteadyState(probe.name().to_owned()));
            }
        }
        self.phase = ExperimentPhase::Injecting;
        let injection_id = provider
            .inject(self.chaos_type, &self.targets, &self.parameters)
            .await?;
        self.injection_id = Some(injection_id.clone());
        self.phase = ExperimentPhase::Observing;
        let observed = async {
            for probe in probes {
                if !probe.check().await? {
                    return Ok::<bool, TestkitError>(false);
                }
            }
            Ok(true)
        }
        .await;
        self.phase = ExperimentPhase::Recovering;
        let recovery = provider.recover(&injection_id).await;
        let cleanup = provider.cleanup(&injection_id).await;
        recovery?;
        cleanup?;
        if !observed? {
            self.phase = ExperimentPhase::Failed;
            return Err(TestkitError::SteadyState(
                "steady state violated during injection".to_owned(),
            ));
        }
        self.phase = ExperimentPhase::Verifying;
        for probe in probes {
            if !probe.check().await? {
                self.phase = ExperimentPhase::Failed;
                return Err(TestkitError::SteadyState(probe.name().to_owned()));
            }
        }
        self.phase = ExperimentPhase::Completed;
        Ok(())
    }
}

#[derive(Clone, Debug, Default)]
pub struct DeterministicClock {
    now_ms: Arc<Mutex<u64>>,
}
impl DeterministicClock {
    #[must_use]
    pub fn now_ms(&self) -> u64 {
        *self
            .now_ms
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }
    pub fn advance_ms(&self, delta: u64) {
        let mut now = self
            .now_ms
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        *now = now.saturating_add(delta);
    }
}

#[derive(Clone, Debug)]
pub struct DeterministicIds {
    values: Arc<Mutex<VecDeque<String>>>,
}
impl DeterministicIds {
    #[must_use]
    pub fn new(values: impl IntoIterator<Item = String>) -> Self {
        Self {
            values: Arc::new(Mutex::new(values.into_iter().collect())),
        }
    }
    pub fn next(&self) -> Result<String, TestkitError> {
        self.values
            .lock()
            .map_err(|_| TestkitError::State("ID source poisoned".to_owned()))?
            .pop_front()
            .ok_or_else(|| TestkitError::State("deterministic IDs exhausted".to_owned()))
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct FaultRule {
    pub operation: String,
    pub fail_on_calls: BTreeSet<u64>,
    pub error: String,
}
#[derive(Clone, Debug, Default)]
pub struct FaultInjector {
    rules: BTreeMap<String, FaultRule>,
    calls: BTreeMap<String, u64>,
}
impl FaultInjector {
    pub fn add(&mut self, rule: FaultRule) -> Result<(), TestkitError> {
        if rule.operation.trim().is_empty() || rule.error.trim().is_empty() {
            return Err(TestkitError::InvalidConfiguration(
                "fault rule requires operation and error".to_owned(),
            ));
        }
        self.rules.insert(rule.operation.clone(), rule);
        Ok(())
    }
    pub fn check(&mut self, operation: &str) -> Result<(), TestkitError> {
        let call = self.calls.entry(operation.to_owned()).or_default();
        *call = call.saturating_add(1);
        if let Some(rule) = self.rules.get(operation)
            && rule.fail_on_calls.contains(call)
        {
            return Err(TestkitError::Injected(rule.error.clone()));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default)]
pub struct EventCollector {
    events: Vec<Value>,
}
impl EventCollector {
    pub fn record(&mut self, event: Value) {
        self.events.push(event);
    }
    #[must_use]
    pub fn matching(&self, event_type: &str) -> Vec<&Value> {
        self.events
            .iter()
            .filter(|event| event.get("type").and_then(Value::as_str) == Some(event_type))
            .collect()
    }
    pub fn clear(&mut self) {
        self.events.clear();
    }
}

#[async_trait]
pub trait TestDatabaseProvider: Send + Sync {
    async fn create_schema(&self) -> Result<(), TestkitError>;
    async fn reset(&self) -> Result<(), TestkitError>;
    async fn drop_schema(&self) -> Result<(), TestkitError>;
}

#[derive(Debug, Error)]
pub enum TestkitError {
    #[error("invalid test configuration: {0}")]
    InvalidConfiguration(String),
    #[error("invalid contract: {0}")]
    InvalidContract(String),
    #[error("test provider unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("steady state failed: {0}")]
    SteadyState(String),
    #[error("injected fault: {0}")]
    Injected(String),
    #[error("test state error: {0}")]
    State(String),
}
