use std::collections::BTreeMap;
use std::sync::{Arc, RwLock};

use async_trait::async_trait;
use mmf_resilience::{BackoffPolicy, ConfiguredBackoff, RetryConfig, RetryStrategy};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};

use crate::{
    PushAdapter, PushAdapterHealth, PushChannel, PushError, PushHealthStatus, PushMessage,
    PushPriority, PushResult, PushStatus, TokenInvalidationEvent, TokenLifecycleHandler,
    reason_from_fcm_error,
};

pub const FCM_MESSAGING_SCOPE: &str = "https://www.googleapis.com/auth/firebase.messaging";
pub const FCM_ENDPOINT_TEMPLATE: &str =
    "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send";

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FcmCredentialSource {
    ServiceAccountPath(String),
    ServiceAccountJson(Value),
    ApplicationDefault,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct FcmConfig {
    pub project_id: String,
    pub credentials: Option<FcmCredentialSource>,
    pub max_batch_size: usize,
    pub max_attempts: u32,
    pub initial_backoff_ms: u64,
    pub max_backoff_ms: u64,
    pub timeout_ms: u64,
}

impl Default for FcmConfig {
    fn default() -> Self {
        Self {
            project_id: String::new(),
            credentials: None,
            max_batch_size: 500,
            max_attempts: 3,
            initial_backoff_ms: 1_000,
            max_backoff_ms: 30_000,
            timeout_ms: 30_000,
        }
    }
}

impl FcmConfig {
    pub fn validate(&self) -> Result<(), PushError> {
        if self.project_id.trim().is_empty() {
            return Err(PushError::InvalidConfiguration(
                "FCM project_id is required".into(),
            ));
        }
        if self.credentials.is_none() {
            return Err(PushError::InvalidConfiguration(
                "FCM credentials are required".into(),
            ));
        }
        if self.max_batch_size == 0 || self.max_batch_size > 500 {
            return Err(PushError::InvalidConfiguration(
                "FCM max_batch_size must be between 1 and 500".into(),
            ));
        }
        if self.max_attempts == 0 || self.timeout_ms == 0 {
            return Err(PushError::InvalidConfiguration(
                "FCM attempts and timeout must be greater than zero".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct FcmProviderResponse {
    pub status_code: u16,
    pub provider_message_id: Option<String>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    pub retry_after_seconds: Option<u64>,
}

#[async_trait]
pub trait FcmProvider: Send + Sync {
    async fn start(&self, config: &FcmConfig) -> Result<(), PushError>;
    async fn stop(&self) -> Result<(), PushError>;
    async fn send(
        &self,
        config: &FcmConfig,
        message: &Value,
    ) -> Result<FcmProviderResponse, PushError>;
    async fn health(&self) -> Result<(), PushError>;
}

pub struct FcmAdapter {
    config: FcmConfig,
    provider: Arc<dyn FcmProvider>,
    lifecycle: Option<Arc<dyn TokenLifecycleHandler>>,
    running: RwLock<bool>,
    backoff: ConfiguredBackoff,
}

impl FcmAdapter {
    pub fn new(
        config: FcmConfig,
        provider: Arc<dyn FcmProvider>,
        lifecycle: Option<Arc<dyn TokenLifecycleHandler>>,
    ) -> Result<Self, PushError> {
        config.validate()?;
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
            lifecycle,
            running: RwLock::new(false),
            backoff,
        })
    }

    #[must_use]
    pub fn build_message(message: &PushMessage, token: &str) -> Value {
        let urgent = matches!(
            message.priority,
            PushPriority::High | PushPriority::Critical
        );
        let mut data = Map::new();
        data.insert("message_id".into(), Value::String(message.id.clone()));
        for (key, value) in &message.data {
            data.insert(key.clone(), Value::String(serialize_fcm_value(value)));
        }
        let mut android = json!({
            "priority": if urgent { "high" } else { "normal" },
            "ttl": format!("{}s", message.ttl_seconds),
        });
        let mut apns_headers = json!({
            "apns-priority": if urgent { "10" } else { "5" },
            "apns-expiration": message.ttl_seconds.to_string(),
        });
        let mut aps = json!({});
        let mut root = json!({
            "token": token,
            "data": data,
        });
        if !message.title.is_empty() || !message.body.is_empty() {
            root["notification"] = json!({"title": message.title, "body": message.body});
            aps["alert"] = json!({"title": message.title, "body": message.body});
            if urgent {
                aps["sound"] = Value::String("default".into());
            }
        }
        if let Some(collapse_key) = &message.collapse_key {
            android["collapse_key"] = Value::String(collapse_key.clone());
            apns_headers["apns-collapse-id"] = Value::String(collapse_key.clone());
        }
        if message.content_available {
            aps["content-available"] = Value::from(1);
        }
        if message.mutable_content {
            aps["mutable-content"] = Value::from(1);
        }
        root["android"] = android;
        root["apns"] = json!({"headers": apns_headers, "payload": {"aps": aps}});
        root
    }

    #[allow(clippy::too_many_lines)]
    async fn send_one(&self, message: &PushMessage, token: &str, now_ms: u64) -> PushResult {
        let payload = Self::build_message(message, token);
        for attempt in 1..=self.config.max_attempts {
            match self.provider.send(&self.config, &payload).await {
                Ok(response) if response.status_code == 200 => {
                    let mut result = PushResult::delivered(&message.id, PushChannel::Fcm, now_ms);
                    result.attempt_number = attempt;
                    if let Some(id) = response.provider_message_id {
                        result
                            .metadata
                            .insert("fcm_message_id".into(), Value::String(id));
                    }
                    return result;
                }
                Ok(response) if is_invalid_token(&response) => {
                    let provider_code = response.error_code.as_deref().unwrap_or("UNREGISTERED");
                    if let Some(lifecycle) = &self.lifecycle {
                        let event = TokenInvalidationEvent {
                            token: token.into(),
                            channel: PushChannel::Fcm,
                            reason: reason_from_fcm_error(provider_code),
                            reason_detail: response.error_message.clone(),
                            device_id: None,
                            user_id: message.target.user_id.clone(),
                            organization_id: message.target.organization_id.clone(),
                            error_code: response.error_code.clone(),
                            error_message: response.error_message.clone(),
                            occurred_at_ms: now_ms,
                            correlation_id: message.correlation_id.clone(),
                        };
                        if let Err(error) = lifecycle.token_invalidated(&event).await {
                            let mut result = PushResult::failure(
                                &message.id,
                                PushChannel::Fcm,
                                PushStatus::Failed,
                                "TOKEN_LIFECYCLE_FAILED",
                                error.to_string(),
                                now_ms,
                            );
                            result.failed_tokens.push(token.into());
                            return result;
                        }
                    }
                    let mut result = PushResult::failure(
                        &message.id,
                        PushChannel::Fcm,
                        PushStatus::Rejected,
                        "INVALID_TOKEN",
                        "Token is no longer valid",
                        now_ms,
                    );
                    result.attempt_number = attempt;
                    result.failed_tokens.push(token.into());
                    return result;
                }
                Ok(response) => {
                    let retryable = matches!(response.status_code, 429 | 500 | 503);
                    if retryable && attempt < self.config.max_attempts {
                        tokio::time::sleep(self.backoff.delay(attempt)).await;
                        continue;
                    }
                    let mut result = PushResult::failure(
                        &message.id,
                        PushChannel::Fcm,
                        if response.status_code < 500 {
                            PushStatus::Rejected
                        } else {
                            PushStatus::Failed
                        },
                        response
                            .error_code
                            .unwrap_or_else(|| response.status_code.to_string()),
                        response
                            .error_message
                            .unwrap_or_else(|| "FCM delivery failed".into()),
                        now_ms,
                    );
                    result.attempt_number = attempt;
                    result.should_retry = retryable;
                    result.retry_after_seconds = response.retry_after_seconds;
                    return result;
                }
                Err(error) => {
                    if attempt < self.config.max_attempts {
                        tokio::time::sleep(self.backoff.delay(attempt)).await;
                        continue;
                    }
                    let mut result = PushResult::failure(
                        &message.id,
                        PushChannel::Fcm,
                        PushStatus::Failed,
                        "PROVIDER_ERROR",
                        error.to_string(),
                        now_ms,
                    );
                    result.attempt_number = attempt;
                    result.should_retry = true;
                    return result;
                }
            }
        }
        PushResult::failure(
            &message.id,
            PushChannel::Fcm,
            PushStatus::Failed,
            "MAX_RETRIES",
            "Maximum FCM attempts exceeded",
            now_ms,
        )
    }
}

#[async_trait]
impl PushAdapter for FcmAdapter {
    fn channel(&self) -> PushChannel {
        PushChannel::Fcm
    }

    async fn start(&self) -> Result<(), PushError> {
        self.provider.start(&self.config).await?;
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
        if message.target.device_tokens.is_empty() {
            return Ok(PushResult::failure(
                &message.id,
                PushChannel::Fcm,
                PushStatus::Failed,
                "NO_TOKENS",
                "No device tokens provided",
                now_ms,
            ));
        }
        if message.target.device_tokens.len() == 1 {
            return Ok(self
                .send_one(message, &message.target.device_tokens[0], now_ms)
                .await);
        }
        let mut successes = 0_u64;
        let mut failures = Vec::new();
        for batch in message
            .target
            .device_tokens
            .chunks(self.config.max_batch_size)
        {
            for token in batch {
                let result = self.send_one(message, token, now_ms).await;
                if result.success {
                    successes = successes.saturating_add(1);
                } else {
                    failures.push(token.clone());
                }
            }
        }
        let mut aggregate = if failures.is_empty() {
            PushResult::delivered(&message.id, PushChannel::Fcm, now_ms)
        } else {
            PushResult::failure(
                &message.id,
                PushChannel::Fcm,
                PushStatus::Failed,
                "PARTIAL_FAILURE",
                "One or more FCM deliveries failed",
                now_ms,
            )
        };
        aggregate.failed_tokens = failures;
        aggregate.metadata = BTreeMap::from([
            (
                "total_tokens".into(),
                Value::from(message.target.device_tokens.len()),
            ),
            ("success_count".into(), Value::from(successes)),
            (
                "failure_count".into(),
                Value::from(aggregate.failed_tokens.len()),
            ),
        ]);
        Ok(aggregate)
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
            channel: PushChannel::Fcm,
            status,
            detail,
            checked_at_ms: now_ms,
        }
    }
}

fn serialize_fcm_value(value: &Value) -> String {
    match value {
        Value::String(value) => value.clone(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        _ => python_json_string(value),
    }
}

fn python_json_string(value: &Value) -> String {
    match value {
        Value::Null => "null".into(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => serde_json::to_string(value).unwrap_or_else(|_| "\"\"".into()),
        Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(python_json_string)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(values) => format!(
            "{{{}}}",
            values
                .iter()
                .map(|(key, value)| format!(
                    "{}: {}",
                    serde_json::to_string(key).unwrap_or_else(|_| "\"\"".into()),
                    python_json_string(value)
                ))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}

fn is_invalid_token(response: &FcmProviderResponse) -> bool {
    response.status_code == 404
        || response.error_code.as_deref().is_some_and(|code| {
            matches!(
                code,
                "UNREGISTERED" | "messaging/registration-token-not-registered"
            )
        })
        || response
            .error_message
            .as_deref()
            .is_some_and(|detail| detail.contains("UNREGISTERED"))
}
