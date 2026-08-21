use std::collections::BTreeMap;
use std::sync::{Arc, RwLock};

use serde_json::Value;

use crate::{
    DeviceTokenStore, PushAdapter, PushChannel, PushEventHandler, PushMessage, PushResult,
    PushStatus,
};

pub struct PushManager {
    adapters: RwLock<BTreeMap<PushChannel, Arc<dyn PushAdapter>>>,
    token_store: Option<Arc<dyn DeviceTokenStore>>,
    event_handler: Option<Arc<dyn PushEventHandler>>,
    running: RwLock<bool>,
}

impl PushManager {
    #[must_use]
    pub fn new(
        token_store: Option<Arc<dyn DeviceTokenStore>>,
        event_handler: Option<Arc<dyn PushEventHandler>>,
    ) -> Self {
        Self {
            adapters: RwLock::new(BTreeMap::new()),
            token_store,
            event_handler,
            running: RwLock::new(false),
        }
    }

    pub fn register_adapter(&self, adapter: Arc<dyn PushAdapter>) {
        self.adapters
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert(adapter.channel(), adapter);
    }

    #[must_use]
    pub fn adapter(&self, channel: PushChannel) -> Option<Arc<dyn PushAdapter>> {
        self.adapters
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(&channel)
            .cloned()
    }

    #[must_use]
    pub fn is_running(&self) -> bool {
        *self
            .running
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }

    pub async fn start(&self) -> Vec<PushResult> {
        if self.is_running() {
            return Vec::new();
        }
        let adapters: Vec<_> = self
            .adapters
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .values()
            .cloned()
            .collect();
        let mut failures = Vec::new();
        for adapter in adapters {
            if let Err(error) = adapter.start().await {
                failures.push(PushResult::failure(
                    "manager.start",
                    adapter.channel(),
                    PushStatus::Failed,
                    "ADAPTER_START_FAILED",
                    error.to_string(),
                    0,
                ));
            }
        }
        *self
            .running
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = failures.is_empty();
        failures
    }

    pub async fn stop(&self) -> Vec<PushResult> {
        let adapters: Vec<_> = self
            .adapters
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .values()
            .cloned()
            .collect();
        let mut failures = Vec::new();
        for adapter in adapters {
            if let Err(error) = adapter.stop().await {
                failures.push(PushResult::failure(
                    "manager.stop",
                    adapter.channel(),
                    PushStatus::Failed,
                    "ADAPTER_STOP_FAILED",
                    error.to_string(),
                    0,
                ));
            }
        }
        *self
            .running
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = false;
        failures
    }

    pub async fn send(
        &self,
        message: &PushMessage,
        channels: Option<&[PushChannel]>,
        now_ms: u64,
    ) -> Vec<PushResult> {
        let channels =
            channels.map_or_else(|| message.target.channels.clone(), <[PushChannel]>::to_vec);
        if message.is_expired_at(now_ms) {
            return channels
                .into_iter()
                .map(|channel| {
                    PushResult::failure(
                        &message.id,
                        channel,
                        PushStatus::Expired,
                        "MESSAGE_EXPIRED",
                        "Message TTL exceeded",
                        now_ms,
                    )
                })
                .collect();
        }

        let mut resolved = message.clone();
        if let (Some(store), Some(user_id)) = (&self.token_store, &message.target.user_id) {
            match store.tokens_for_user(user_id).await {
                Ok(tokens) => {
                    for token in tokens {
                        if !resolved.target.device_tokens.contains(&token) {
                            resolved.target.device_tokens.push(token);
                        }
                    }
                }
                Err(error) => {
                    return channels
                        .into_iter()
                        .map(|channel| {
                            PushResult::failure(
                                &message.id,
                                channel,
                                PushStatus::Failed,
                                "TOKEN_LOOKUP_FAILED",
                                error.to_string(),
                                now_ms,
                            )
                        })
                        .collect();
                }
            }
        }

        let mut results = Vec::with_capacity(channels.len());
        for channel in channels {
            let Some(adapter) = self.adapter(channel) else {
                results.push(PushResult::failure(
                    &message.id,
                    channel,
                    PushStatus::Failed,
                    "NO_ADAPTER",
                    format!("No adapter registered for {channel:?}"),
                    now_ms,
                ));
                continue;
            };
            let mut result = match adapter.send(&resolved, now_ms).await {
                Ok(result) => result,
                Err(error) => {
                    let mut failed = PushResult::failure(
                        &message.id,
                        channel,
                        PushStatus::Failed,
                        "ADAPTER_ERROR",
                        error.to_string(),
                        now_ms,
                    );
                    failed.should_retry = true;
                    failed
                }
            };
            self.notify_event_handler(&resolved, &mut result).await;
            results.push(result);
        }
        results
    }

    async fn notify_event_handler(&self, message: &PushMessage, result: &mut PushResult) {
        let Some(handler) = &self.event_handler else {
            return;
        };
        let event_result = if result.success {
            handler.delivery_succeeded(message, result).await
        } else {
            let delivery = handler.delivery_failed(message, result).await;
            if delivery.is_ok()
                && matches!(
                    result.error_code.as_deref(),
                    Some("INVALID_TOKEN" | "UNREGISTERED")
                )
            {
                for token in &result.failed_tokens {
                    if let Err(error) = handler
                        .token_invalid(token, result.channel, result.error_message.as_deref())
                        .await
                    {
                        result.metadata.insert(
                            "event_handler_warning".into(),
                            Value::String(error.to_string()),
                        );
                        return;
                    }
                }
            }
            delivery
        };
        if let Err(error) = event_result {
            result.metadata.insert(
                "event_handler_warning".into(),
                Value::String(error.to_string()),
            );
        }
    }
}

impl Default for PushManager {
    fn default() -> Self {
        Self::new(None, None)
    }
}
