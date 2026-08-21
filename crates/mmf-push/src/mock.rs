use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, RwLock};

use async_trait::async_trait;
use rand::Rng;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    PushAdapter, PushAdapterHealth, PushChannel, PushError, PushHealthStatus, PushMessage,
    PushResult, PushStatus, TokenInvalidationEvent, TokenInvalidationReason, TokenLifecycleHandler,
};

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct MockPushConfig {
    pub channel: PushChannel,
    pub success_rate: f64,
    pub delay_ms: u64,
    pub invalid_tokens: BTreeSet<String>,
    pub simulate_error: Option<String>,
    pub simulate_error_code: Option<String>,
    pub deterministic_outcomes: VecDeque<bool>,
}

impl Default for MockPushConfig {
    fn default() -> Self {
        Self {
            channel: PushChannel::Fcm,
            success_rate: 1.0,
            delay_ms: 0,
            invalid_tokens: BTreeSet::new(),
            simulate_error: None,
            simulate_error_code: None,
            deterministic_outcomes: VecDeque::new(),
        }
    }
}

impl MockPushConfig {
    pub fn validate(&self) -> Result<(), PushError> {
        if !self.success_rate.is_finite() || !(0.0..=1.0).contains(&self.success_rate) {
            return Err(PushError::InvalidConfiguration(
                "mock success_rate must be between 0.0 and 1.0".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CapturedMessage {
    pub message: PushMessage,
    pub result: PushResult,
    pub captured_at_ms: u64,
}

pub struct MockPushAdapter {
    config: Mutex<MockPushConfig>,
    lifecycle: Option<Arc<dyn TokenLifecycleHandler>>,
    messages: Mutex<Vec<CapturedMessage>>,
    running: AtomicBool,
    custom_handler: RwLock<Option<Arc<dyn MockPushHandler>>>,
}

#[async_trait]
pub trait MockPushHandler: Send + Sync {
    async fn send(&self, message: &PushMessage, now_ms: u64) -> Result<PushResult, PushError>;
}

impl MockPushAdapter {
    pub fn new(
        config: MockPushConfig,
        lifecycle: Option<Arc<dyn TokenLifecycleHandler>>,
    ) -> Result<Self, PushError> {
        config.validate()?;
        Ok(Self {
            config: Mutex::new(config),
            lifecycle,
            messages: Mutex::new(Vec::new()),
            running: AtomicBool::new(false),
            custom_handler: RwLock::new(None),
        })
    }

    #[must_use]
    pub fn sent_count(&self) -> usize {
        self.messages
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .len()
    }

    #[must_use]
    pub fn messages(&self) -> Vec<CapturedMessage> {
        self.messages
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone()
    }

    #[must_use]
    pub fn last_message(&self) -> Option<CapturedMessage> {
        self.messages
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .last()
            .cloned()
    }

    #[must_use]
    pub fn successful_messages(&self) -> Vec<CapturedMessage> {
        self.messages()
            .into_iter()
            .filter(|captured| captured.result.success)
            .collect()
    }

    #[must_use]
    pub fn failed_messages(&self) -> Vec<CapturedMessage> {
        self.messages()
            .into_iter()
            .filter(|captured| !captured.result.success)
            .collect()
    }

    pub fn clear(&self) {
        self.messages
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clear();
    }

    pub fn reset(&self) {
        self.clear();
        let channel = self
            .config
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .channel;
        *self
            .config
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = MockPushConfig {
            channel,
            ..MockPushConfig::default()
        };
        *self
            .custom_handler
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = None;
    }

    pub fn update_config(&self, update: impl FnOnce(&mut MockPushConfig)) -> Result<(), PushError> {
        let mut config = self
            .config
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        update(&mut config);
        config.validate()
    }

    pub fn set_custom_handler(&self, handler: Arc<dyn MockPushHandler>) {
        *self
            .custom_handler
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = Some(handler);
    }

    pub fn clear_custom_handler(&self) {
        *self
            .custom_handler
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = None;
    }

    #[must_use]
    pub fn find_messages(
        &self,
        user_id: Option<&str>,
        device_token: Option<&str>,
        data_contains: &BTreeMap<String, Value>,
    ) -> Vec<CapturedMessage> {
        self.messages()
            .into_iter()
            .filter(|captured| {
                user_id
                    .is_none_or(|value| captured.message.target.user_id.as_deref() == Some(value))
                    && device_token.is_none_or(|value| {
                        captured
                            .message
                            .target
                            .device_tokens
                            .iter()
                            .any(|token| token == value)
                    })
                    && data_contains
                        .iter()
                        .all(|(key, value)| captured.message.data.get(key) == Some(value))
            })
            .collect()
    }

    pub fn assert_sent(
        &self,
        count: Option<usize>,
        minimum: Option<usize>,
        maximum: Option<usize>,
    ) -> Result<(), PushError> {
        let actual = self.sent_count();
        if count.is_some_and(|expected| actual != expected)
            || minimum.is_some_and(|expected| actual < expected)
            || maximum.is_some_and(|expected| actual > expected)
        {
            return Err(PushError::InvalidOperation(format!(
                "captured message count {actual} did not satisfy count={count:?}, minimum={minimum:?}, maximum={maximum:?}"
            )));
        }
        Ok(())
    }

    pub fn assert_message_sent_to(
        &self,
        user_id: Option<&str>,
        device_token: Option<&str>,
    ) -> Result<CapturedMessage, PushError> {
        self.find_messages(user_id, device_token, &BTreeMap::new())
            .into_iter()
            .next()
            .ok_or_else(|| {
                PushError::InvalidOperation(format!(
                    "no captured message matched user_id={user_id:?}, device_token={device_token:?}"
                ))
            })
    }

    fn capture(&self, message: &PushMessage, result: PushResult, now_ms: u64) -> PushResult {
        self.messages
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(CapturedMessage {
                message: message.clone(),
                result: result.clone(),
                captured_at_ms: now_ms,
            });
        result
    }
}

#[async_trait]
impl PushAdapter for MockPushAdapter {
    fn channel(&self) -> PushChannel {
        self.config
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .channel
    }

    async fn start(&self) -> Result<(), PushError> {
        self.running.store(true, Ordering::Release);
        Ok(())
    }

    async fn stop(&self) -> Result<(), PushError> {
        self.running.store(false, Ordering::Release);
        Ok(())
    }

    async fn send(&self, message: &PushMessage, now_ms: u64) -> Result<PushResult, PushError> {
        let (config, success) = {
            let mut config = self
                .config
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            let success = config
                .deterministic_outcomes
                .pop_front()
                .unwrap_or_else(|| rand::rng().random::<f64>() <= config.success_rate);
            (config.clone(), success)
        };
        if config.delay_ms > 0 {
            tokio::time::sleep(std::time::Duration::from_millis(config.delay_ms)).await;
        }
        let custom_handler = self
            .custom_handler
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone();
        if let Some(handler) = custom_handler {
            let result = handler.send(message, now_ms).await?;
            return Ok(self.capture(message, result, now_ms));
        }
        if let Some(detail) = config.simulate_error {
            return Ok(self.capture(
                message,
                PushResult::failure(
                    &message.id,
                    config.channel,
                    PushStatus::Failed,
                    config
                        .simulate_error_code
                        .unwrap_or_else(|| "SIMULATED_ERROR".into()),
                    detail,
                    now_ms,
                ),
                now_ms,
            ));
        }
        let invalid: Vec<_> = message
            .target
            .device_tokens
            .iter()
            .filter(|token| config.invalid_tokens.contains(*token))
            .cloned()
            .collect();
        if !invalid.is_empty() {
            if let Some(lifecycle) = &self.lifecycle {
                for token in &invalid {
                    lifecycle
                        .token_invalidated(&TokenInvalidationEvent {
                            token: token.clone(),
                            channel: config.channel,
                            reason: TokenInvalidationReason::Unregistered,
                            reason_detail: Some("Mock: Token marked as invalid".into()),
                            device_id: None,
                            user_id: message.target.user_id.clone(),
                            organization_id: message.target.organization_id.clone(),
                            error_code: Some("INVALID_TOKEN".into()),
                            error_message: None,
                            occurred_at_ms: now_ms,
                            correlation_id: message.correlation_id.clone(),
                        })
                        .await?;
                }
            }
            let mut result = PushResult::failure(
                &message.id,
                config.channel,
                PushStatus::Rejected,
                "INVALID_TOKEN",
                "One or more tokens are invalid",
                now_ms,
            );
            result.failed_tokens = invalid;
            return Ok(self.capture(message, result, now_ms));
        }
        if !success {
            let mut result = PushResult::failure(
                &message.id,
                config.channel,
                PushStatus::Failed,
                "RANDOM_FAILURE",
                "Simulated random failure based on success_rate",
                now_ms,
            );
            result.should_retry = true;
            return Ok(self.capture(message, result, now_ms));
        }
        let mut result = PushResult::delivered(&message.id, config.channel, now_ms);
        result.metadata.insert("mock".into(), Value::Bool(true));
        result.metadata.insert(
            "tokens_count".into(),
            Value::from(message.target.device_tokens.len()),
        );
        Ok(self.capture(message, result, now_ms))
    }

    async fn health(&self, now_ms: u64) -> PushAdapterHealth {
        PushAdapterHealth {
            channel: self.channel(),
            status: if self.running.load(Ordering::Acquire) {
                PushHealthStatus::Healthy
            } else {
                PushHealthStatus::Stopped
            },
            detail: None,
            checked_at_ms: now_ms,
        }
    }
}
