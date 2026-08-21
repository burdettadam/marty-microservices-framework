use async_trait::async_trait;

use crate::{
    PushAdapterHealth, PushChannel, PushError, PushMessage, PushResult, TokenInvalidationEvent,
    TokenRegistrationEvent,
};

#[async_trait]
pub trait PushAdapter: Send + Sync {
    fn channel(&self) -> PushChannel;
    async fn start(&self) -> Result<(), PushError>;
    async fn stop(&self) -> Result<(), PushError>;
    async fn send(&self, message: &PushMessage, now_ms: u64) -> Result<PushResult, PushError>;
    async fn health(&self, now_ms: u64) -> PushAdapterHealth;

    async fn send_batch(
        &self,
        messages: &[PushMessage],
        now_ms: u64,
    ) -> Vec<Result<PushResult, PushError>> {
        let mut results = Vec::with_capacity(messages.len());
        for message in messages {
            results.push(self.send(message, now_ms).await);
        }
        results
    }
}

#[async_trait]
pub trait DeviceTokenStore: Send + Sync {
    async fn tokens_for_user(&self, user_id: &str) -> Result<Vec<String>, PushError>;
    async fn tokens_for_device(&self, device_id: &str) -> Result<Vec<String>, PushError>;
    async fn store_token(&self, registration: &TokenRegistrationEvent) -> Result<(), PushError>;
    async fn remove_token(&self, token: &str) -> Result<(), PushError>;
    async fn mark_token_invalid(&self, token: &str, reason: Option<&str>) -> Result<(), PushError>;
}

#[async_trait]
pub trait PushEventHandler: Send + Sync {
    async fn delivery_succeeded(
        &self,
        message: &PushMessage,
        result: &PushResult,
    ) -> Result<(), PushError>;
    async fn delivery_failed(
        &self,
        message: &PushMessage,
        result: &PushResult,
    ) -> Result<(), PushError>;
    async fn token_invalid(
        &self,
        token: &str,
        channel: PushChannel,
        reason: Option<&str>,
    ) -> Result<(), PushError>;
}

#[async_trait]
pub trait TokenLifecycleHandler: Send + Sync {
    async fn token_registered(&self, event: &TokenRegistrationEvent) -> Result<(), PushError>;
    async fn token_invalidated(&self, event: &TokenInvalidationEvent) -> Result<(), PushError>;
    async fn token_refreshed(
        &self,
        old_token: &str,
        new_token: &str,
        device_id: &str,
        channel: PushChannel,
    ) -> Result<(), PushError>;
}

#[async_trait]
pub trait PushEventPublisher: Send + Sync {
    async fn publish(&self, event_type: &str, payload: serde_json::Value) -> Result<(), PushError>;
}
