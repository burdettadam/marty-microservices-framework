use std::collections::BTreeMap;
use std::sync::{Arc, Mutex, RwLock};
use std::time::Instant;

use async_trait::async_trait;
use hmac::{Hmac, Mac};
use mmf_resilience::{
    BackoffPolicy, CircuitBreaker, CircuitBreakerConfig, CircuitState, ConfiguredBackoff,
    RetryConfig, RetryStrategy,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::Sha256;

use crate::{
    PushAdapter, PushAdapterHealth, PushChannel, PushError, PushHealthStatus, PushMessage,
    PushResult, PushStatus, lifecycle::encode_hex,
};

type HmacSha256 = Hmac<Sha256>;
const TOKEN_MARKER: &str = "__MARTY_TOKEN__";

/// Tenant-scoped allowlist for callback destinations.
///
/// Registrations use `tenant|URL` entries separated by semicolons. A URL may
/// contain one `__MARTY_TOKEN__` slot matching 16-512 URL-safe characters.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct WebhookDestinationRegistry {
    registrations: BTreeMap<String, Vec<String>>,
}

impl WebhookDestinationRegistry {
    pub fn parse(configuration: &str) -> Result<Self, PushError> {
        let mut registrations = BTreeMap::<String, Vec<String>>::new();
        for raw_entry in configuration.split(';') {
            let entry = raw_entry.trim();
            if entry.is_empty() {
                continue;
            }
            let (tenant, template) = entry.split_once('|').ok_or_else(|| {
                PushError::InvalidConfiguration(
                    "webhook destinations must use tenant|URL entries".into(),
                )
            })?;
            let tenant = tenant.trim();
            let template = template.trim();
            if tenant.is_empty() || template.is_empty() {
                return Err(PushError::InvalidConfiguration(
                    "webhook destination tenant and URL must not be empty".into(),
                ));
            }
            if template.match_indices(TOKEN_MARKER).count() > 1 {
                return Err(PushError::InvalidConfiguration(
                    "webhook destination allows at most one token slot".into(),
                ));
            }
            validate_destination_shape(template)?;
            registrations
                .entry(tenant.to_owned())
                .or_default()
                .push(template.to_owned());
        }
        Ok(Self { registrations })
    }

    pub fn require(&self, tenant: &str, destination: &str) -> Result<(), PushError> {
        validate_destination_shape(destination)?;
        if self.registrations.get(tenant).is_some_and(|templates| {
            templates
                .iter()
                .any(|template| destination_matches(destination, template))
        }) {
            Ok(())
        } else {
            Err(PushError::InvalidOperation(
                "webhook destination is not registered for the tenant".into(),
            ))
        }
    }

    #[must_use]
    pub fn templates(&self, tenant: &str) -> &[String] {
        self.registrations.get(tenant).map_or(&[], Vec::as_slice)
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct WebhookEndpointConfig {
    pub url: String,
    #[serde(default, skip_serializing)]
    pub secret: String,
    #[serde(default)]
    pub event_types: Vec<String>,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub custom_headers: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct WebhookConfig {
    pub connect_timeout_ms: u64,
    pub read_timeout_ms: u64,
    pub max_attempts: u32,
    pub initial_backoff_ms: u64,
    pub max_backoff_ms: u64,
    pub failure_threshold: u32,
    pub recovery_timeout_ms: u64,
    pub signature_header: String,
    pub event_header: String,
    pub delivery_id_header: String,
    pub timestamp_header: String,
}

impl Default for WebhookConfig {
    fn default() -> Self {
        Self {
            connect_timeout_ms: 5_000,
            read_timeout_ms: 30_000,
            max_attempts: 3,
            initial_backoff_ms: 1_000,
            max_backoff_ms: 60_000,
            failure_threshold: 5,
            recovery_timeout_ms: 300_000,
            signature_header: "X-MMF-Signature".into(),
            event_header: "X-MMF-Event".into(),
            delivery_id_header: "X-MMF-Delivery-Id".into(),
            timestamp_header: "X-MMF-Timestamp".into(),
        }
    }
}

impl WebhookConfig {
    pub fn validate(&self) -> Result<(), PushError> {
        if self.connect_timeout_ms == 0
            || self.read_timeout_ms == 0
            || self.max_attempts == 0
            || self.failure_threshold == 0
            || self.recovery_timeout_ms == 0
        {
            return Err(PushError::InvalidConfiguration(
                "webhook timeouts, attempts, and thresholds must be greater than zero".into(),
            ));
        }
        if [
            &self.signature_header,
            &self.event_header,
            &self.delivery_id_header,
            &self.timestamp_header,
        ]
        .iter()
        .any(|header| header.trim().is_empty())
        {
            return Err(PushError::InvalidConfiguration(
                "webhook header names must not be empty".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct WebhookRequest {
    pub url: String,
    pub headers: BTreeMap<String, String>,
    pub body: Vec<u8>,
    pub connect_timeout_ms: u64,
    pub read_timeout_ms: u64,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct WebhookResponse {
    pub status_code: u16,
    pub body: String,
    pub retry_after_seconds: Option<u64>,
}

#[async_trait]
pub trait WebhookProvider: Send + Sync {
    async fn start(&self) -> Result<(), PushError>;
    async fn stop(&self) -> Result<(), PushError>;
    async fn post(&self, request: &WebhookRequest) -> Result<WebhookResponse, PushError>;
    async fn health(&self) -> Result<(), PushError>;
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct WebhookCircuitStats {
    pub state: String,
}

pub struct WebhookAdapter {
    config: WebhookConfig,
    provider: Arc<dyn WebhookProvider>,
    configured_endpoints: Vec<WebhookEndpointConfig>,
    circuits: Mutex<BTreeMap<String, CircuitBreaker>>,
    backoff: ConfiguredBackoff,
    running: RwLock<bool>,
}

impl WebhookAdapter {
    pub fn new(
        config: WebhookConfig,
        provider: Arc<dyn WebhookProvider>,
        configured_endpoints: Vec<WebhookEndpointConfig>,
    ) -> Result<Self, PushError> {
        config.validate()?;
        for endpoint in &configured_endpoints {
            validate_endpoint(endpoint)?;
        }
        let backoff = ConfiguredBackoff::new(RetryConfig {
            max_attempts: config.max_attempts,
            base_delay_ms: config.initial_backoff_ms,
            max_delay_ms: config.max_backoff_ms,
            strategy: RetryStrategy::Exponential,
            backoff_multiplier: 2.0,
            jitter: false,
            jitter_factor: 0.0,
        })
        .map_err(|error| PushError::InvalidConfiguration(error.to_string()))?;
        Ok(Self {
            config,
            provider,
            configured_endpoints,
            circuits: Mutex::new(BTreeMap::new()),
            backoff,
            running: RwLock::new(false),
        })
    }

    #[must_use]
    pub fn sign_payload(body: &[u8], secret: &str) -> String {
        if secret.is_empty() {
            return String::new();
        }
        let Ok(mut mac) = HmacSha256::new_from_slice(secret.as_bytes()) else {
            return String::new();
        };
        mac.update(body);
        let digest = mac.finalize().into_bytes();
        let encoded = encode_hex(&digest);
        format!("sha256={encoded}")
    }

    #[must_use]
    pub fn verify_signature(body: &[u8], secret: &str, signature: &str) -> bool {
        let Some(encoded) = signature.strip_prefix("sha256=") else {
            return false;
        };
        let Some(bytes) = decode_hex(encoded) else {
            return false;
        };
        let Ok(mut mac) = HmacSha256::new_from_slice(secret.as_bytes()) else {
            return false;
        };
        mac.update(body);
        mac.verify_slice(&bytes).is_ok()
    }

    pub async fn send_to_endpoints(
        &self,
        message: &PushMessage,
        endpoints: &[WebhookEndpointConfig],
        now_ms: u64,
    ) -> Result<PushResult, PushError> {
        let event_type = message
            .data
            .get("event_type")
            .and_then(Value::as_str)
            .unwrap_or("");
        let filtered: Vec<_> = endpoints
            .iter()
            .filter(|endpoint| {
                endpoint.enabled
                    && (endpoint.event_types.is_empty()
                        || endpoint.event_types.iter().any(|item| item == event_type))
            })
            .collect();
        if filtered.is_empty() {
            let mut result = PushResult::delivered(&message.id, PushChannel::Webhook, now_ms);
            result.metadata.insert(
                "skipped".into(),
                Value::String("No matching endpoints for event type".into()),
            );
            return Ok(result);
        }
        let mut successes = 0_usize;
        let mut failures = Vec::new();
        for endpoint in &filtered {
            match self.deliver_to_endpoint(message, endpoint, now_ms).await {
                Ok(result) if result.success => successes = successes.saturating_add(1),
                Ok(result) => failures.push(result),
                Err(error) => failures.push(PushResult::failure(
                    &message.id,
                    PushChannel::Webhook,
                    PushStatus::Failed,
                    "PROVIDER_ERROR",
                    error.to_string(),
                    now_ms,
                )),
            }
        }
        let mut aggregate = if successes > 0 {
            PushResult::delivered(&message.id, PushChannel::Webhook, now_ms)
        } else {
            PushResult::failure(
                &message.id,
                PushChannel::Webhook,
                PushStatus::Failed,
                "ALL_ENDPOINTS_FAILED",
                "No webhook endpoint accepted the delivery",
                now_ms,
            )
        };
        aggregate
            .metadata
            .insert("total_endpoints".into(), Value::from(filtered.len()));
        aggregate
            .metadata
            .insert("success_count".into(), Value::from(successes));
        aggregate
            .metadata
            .insert("failure_count".into(), Value::from(failures.len()));
        Ok(aggregate)
    }

    #[must_use]
    pub fn circuit_stats(&self) -> BTreeMap<String, WebhookCircuitStats> {
        self.circuits
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .iter()
            .map(|(url, circuit)| {
                (
                    url.clone(),
                    WebhookCircuitStats {
                        state: match circuit.state() {
                            CircuitState::Closed => "closed",
                            CircuitState::Open => "open",
                            CircuitState::HalfOpen => "half_open",
                        }
                        .into(),
                    },
                )
            })
            .collect()
    }

    fn circuit(&self, url: &str) -> Result<CircuitBreaker, PushError> {
        let mut circuits = self
            .circuits
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if let Some(circuit) = circuits.get(url) {
            return Ok(circuit.clone());
        }
        let circuit = CircuitBreaker::new(
            format!("webhook:{url}"),
            CircuitBreakerConfig {
                failure_threshold: self.config.failure_threshold,
                success_threshold: 1,
                open_timeout_ms: self.config.recovery_timeout_ms,
                ..CircuitBreakerConfig::default()
            },
        )
        .map_err(|error| PushError::InvalidConfiguration(error.to_string()))?;
        circuits.insert(url.into(), circuit.clone());
        Ok(circuit)
    }

    #[allow(clippy::too_many_lines)]
    pub async fn deliver_to_endpoint(
        &self,
        message: &PushMessage,
        endpoint: &WebhookEndpointConfig,
        now_ms: u64,
    ) -> Result<PushResult, PushError> {
        validate_endpoint(endpoint)?;
        let circuit = self.circuit(&endpoint.url)?;
        if circuit.allow_call_at(Instant::now()).is_err() {
            return Ok(PushResult::failure(
                &message.id,
                PushChannel::Webhook,
                PushStatus::Failed,
                "CIRCUIT_OPEN",
                "Circuit breaker is open for this endpoint",
                now_ms,
            ));
        }
        let body = serde_json::to_vec(message)
            .map_err(|error| PushError::Serialization(error.to_string()))?;
        let mut headers = BTreeMap::from([
            ("Content-Type".into(), "application/json".into()),
            (
                self.config.event_header.clone(),
                message
                    .data
                    .get("event_type")
                    .and_then(Value::as_str)
                    .unwrap_or("push")
                    .into(),
            ),
            (self.config.delivery_id_header.clone(), message.id.clone()),
            (self.config.timestamp_header.clone(), now_ms.to_string()),
        ]);
        headers.extend(endpoint.custom_headers.clone());
        let signature = Self::sign_payload(&body, &endpoint.secret);
        if !signature.is_empty() {
            headers.insert(self.config.signature_header.clone(), signature);
        }
        if let Some(correlation_id) = &message.correlation_id {
            headers.insert("X-MMF-Correlation-Id".into(), correlation_id.clone());
        }
        let request = WebhookRequest {
            url: endpoint.url.clone(),
            headers,
            body,
            connect_timeout_ms: self.config.connect_timeout_ms,
            read_timeout_ms: self.config.read_timeout_ms,
        };
        for attempt in 1..=self.config.max_attempts {
            match self.provider.post(&request).await {
                Ok(response) if response.status_code < 400 => {
                    circuit.record_success_at(Instant::now());
                    let mut result =
                        PushResult::delivered(&message.id, PushChannel::Webhook, now_ms);
                    result.attempt_number = attempt;
                    result
                        .metadata
                        .insert("status_code".into(), Value::from(response.status_code));
                    result
                        .metadata
                        .insert("endpoint".into(), Value::String(endpoint.url.clone()));
                    return Ok(result);
                }
                Ok(response) if response.status_code >= 500 => {
                    circuit.record_failure_at(Instant::now());
                    if attempt < self.config.max_attempts {
                        tokio::time::sleep(self.backoff.delay(attempt)).await;
                        continue;
                    }
                    let mut result = PushResult::failure(
                        &message.id,
                        PushChannel::Webhook,
                        PushStatus::Failed,
                        response.status_code.to_string(),
                        response.body,
                        now_ms,
                    );
                    result.attempt_number = attempt;
                    result.should_retry = true;
                    result.retry_after_seconds = response.retry_after_seconds;
                    return Ok(result);
                }
                Ok(response) => {
                    let mut result = PushResult::failure(
                        &message.id,
                        PushChannel::Webhook,
                        PushStatus::Rejected,
                        response.status_code.to_string(),
                        response.body.chars().take(200).collect::<String>(),
                        now_ms,
                    );
                    result.attempt_number = attempt;
                    return Ok(result);
                }
                Err(error) => {
                    circuit.record_failure_at(Instant::now());
                    if attempt < self.config.max_attempts {
                        tokio::time::sleep(self.backoff.delay(attempt)).await;
                        continue;
                    }
                    let mut result = PushResult::failure(
                        &message.id,
                        PushChannel::Webhook,
                        PushStatus::Failed,
                        "PROVIDER_ERROR",
                        error.to_string(),
                        now_ms,
                    );
                    result.attempt_number = attempt;
                    result.should_retry = true;
                    return Ok(result);
                }
            }
        }
        Err(PushError::Delivery("webhook attempts exhausted".into()))
    }
}

#[async_trait]
impl PushAdapter for WebhookAdapter {
    fn channel(&self) -> PushChannel {
        PushChannel::Webhook
    }

    async fn start(&self) -> Result<(), PushError> {
        self.provider.start().await?;
        *self
            .running
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = true;
        Ok(())
    }

    async fn stop(&self) -> Result<(), PushError> {
        self.provider.stop().await?;
        *self
            .running
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = false;
        Ok(())
    }

    async fn send(&self, message: &PushMessage, now_ms: u64) -> Result<PushResult, PushError> {
        let endpoints = if message.target.webhook_urls.is_empty() {
            self.configured_endpoints.clone()
        } else {
            message
                .target
                .webhook_urls
                .iter()
                .map(|url| WebhookEndpointConfig {
                    url: url.clone(),
                    enabled: true,
                    ..WebhookEndpointConfig::default()
                })
                .collect()
        };
        if endpoints.is_empty() {
            return Ok(PushResult::failure(
                &message.id,
                PushChannel::Webhook,
                PushStatus::Failed,
                "NO_ENDPOINTS",
                "No webhook URLs provided",
                now_ms,
            ));
        }
        self.send_to_endpoints(message, &endpoints, now_ms).await
    }

    async fn health(&self, now_ms: u64) -> PushAdapterHealth {
        let running = *self
            .running
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let (status, detail) = if running {
            match self.provider.health().await {
                Ok(()) => (PushHealthStatus::Healthy, None),
                Err(error) => (PushHealthStatus::Unavailable, Some(error.to_string())),
            }
        } else {
            (PushHealthStatus::Stopped, None)
        };
        PushAdapterHealth {
            channel: PushChannel::Webhook,
            status,
            detail,
            checked_at_ms: now_ms,
        }
    }
}

fn validate_endpoint(endpoint: &WebhookEndpointConfig) -> Result<(), PushError> {
    validate_destination_shape(&endpoint.url)
}

fn validate_destination_shape(value: &str) -> Result<(), PushError> {
    let parse_value = value.replace(TOKEN_MARKER, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");
    let parsed = url::Url::parse(&parse_value).map_err(|_| {
        PushError::InvalidConfiguration("webhook endpoint must be an absolute URL".into())
    })?;
    if !matches!(parsed.scheme(), "http" | "https")
        || parsed.host_str().is_none()
        || !parsed.username().is_empty()
        || parsed.password().is_some()
        || parsed.fragment().is_some()
    {
        return Err(PushError::InvalidConfiguration(
            "webhook endpoint must be HTTP(S) without userinfo or fragments".into(),
        ));
    }
    Ok(())
}

fn destination_matches(destination: &str, template: &str) -> bool {
    let Some((prefix, suffix)) = template.split_once(TOKEN_MARKER) else {
        return destination == template;
    };
    let Some(token_with_suffix) = destination.strip_prefix(prefix) else {
        return false;
    };
    let Some(token) = token_with_suffix.strip_suffix(suffix) else {
        return false;
    };
    (16..=512).contains(&token.len())
        && token
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-'))
}

fn decode_hex(value: &str) -> Option<Vec<u8>> {
    if !value.len().is_multiple_of(2) {
        return None;
    }
    (0..value.len())
        .step_by(2)
        .map(|index| u8::from_str_radix(&value[index..index + 2], 16).ok())
        .collect()
}

const fn default_true() -> bool {
    true
}
