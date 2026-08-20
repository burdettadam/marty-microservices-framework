use std::fmt::Write as _;
use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

use crate::{PushChannel, PushError, PushEventPublisher, TokenLifecycleHandler};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TokenInvalidationReason {
    Unregistered,
    InvalidFormat,
    Expired,
    SenderIdMismatch,
    UserLogout,
    DeviceUnregistered,
    UserRequest,
    RepeatedFailures,
    Stale,
    Unknown,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct TokenInvalidationEvent {
    #[serde(skip_serializing)]
    pub token: String,
    pub channel: PushChannel,
    pub reason: TokenInvalidationReason,
    pub reason_detail: Option<String>,
    pub device_id: Option<String>,
    pub user_id: Option<String>,
    pub organization_id: Option<String>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    pub occurred_at_ms: u64,
    pub correlation_id: Option<String>,
}

impl TokenInvalidationEvent {
    pub const EVENT_TYPE: &'static str = "push.token.invalidated";

    #[must_use]
    pub fn redacted_payload(&self) -> Value {
        let mut payload = serde_json::to_value(self).unwrap_or_else(|_| json!({}));
        payload["event_type"] = Value::String(Self::EVENT_TYPE.into());
        payload["token_preview"] = Value::String(token_preview(&self.token));
        payload["token_fingerprint"] = Value::String(token_fingerprint(&self.token));
        payload
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct TokenRegistrationEvent {
    #[serde(skip_serializing)]
    pub token: String,
    pub channel: PushChannel,
    pub device_id: String,
    pub user_id: Option<String>,
    pub organization_id: Option<String>,
    pub platform: Option<String>,
    pub app_version: Option<String>,
    pub device_model: Option<String>,
    pub registered_at_ms: u64,
    pub correlation_id: Option<String>,
}

impl TokenRegistrationEvent {
    pub const EVENT_TYPE: &'static str = "push.token.registered";

    #[must_use]
    pub fn redacted_payload(&self) -> Value {
        let mut payload = serde_json::to_value(self).unwrap_or_else(|_| json!({}));
        payload["event_type"] = Value::String(Self::EVENT_TYPE.into());
        payload["token_fingerprint"] = Value::String(token_fingerprint(&self.token));
        payload
    }
}

#[must_use]
pub fn token_preview(token: &str) -> String {
    let preview: String = token.chars().take(20).collect();
    if token.chars().count() > 20 {
        format!("{preview}...")
    } else {
        preview
    }
}

#[must_use]
pub fn token_fingerprint(token: &str) -> String {
    let digest = Sha256::digest(token.as_bytes());
    encode_hex(&digest)
}

pub(crate) fn encode_hex(bytes: &[u8]) -> String {
    bytes.iter().fold(
        String::with_capacity(bytes.len().saturating_mul(2)),
        |mut encoded, byte| {
            let _ = write!(encoded, "{byte:02x}");
            encoded
        },
    )
}

#[must_use]
pub fn reason_from_fcm_error(error_code: &str) -> TokenInvalidationReason {
    match error_code {
        "UNREGISTERED" | "messaging/registration-token-not-registered" => {
            TokenInvalidationReason::Unregistered
        }
        "INVALID_ARGUMENT" | "messaging/invalid-registration-token" => {
            TokenInvalidationReason::InvalidFormat
        }
        "SENDER_ID_MISMATCH" | "messaging/mismatched-credential" => {
            TokenInvalidationReason::SenderIdMismatch
        }
        _ => TokenInvalidationReason::Unknown,
    }
}

#[must_use]
pub fn reason_from_apns_error(error_code: &str) -> TokenInvalidationReason {
    match error_code {
        "BadDeviceToken" => TokenInvalidationReason::InvalidFormat,
        "Unregistered" => TokenInvalidationReason::Unregistered,
        "ExpiredToken" => TokenInvalidationReason::Expired,
        "DeviceTokenNotForTopic" => TokenInvalidationReason::SenderIdMismatch,
        _ => TokenInvalidationReason::Unknown,
    }
}

pub struct PublishingTokenLifecycleHandler {
    delegate: Option<Arc<dyn TokenLifecycleHandler>>,
    publisher: Option<Arc<dyn PushEventPublisher>>,
}

impl PublishingTokenLifecycleHandler {
    #[must_use]
    pub fn new(
        delegate: Option<Arc<dyn TokenLifecycleHandler>>,
        publisher: Option<Arc<dyn PushEventPublisher>>,
    ) -> Self {
        Self {
            delegate,
            publisher,
        }
    }
}

#[async_trait::async_trait]
impl TokenLifecycleHandler for PublishingTokenLifecycleHandler {
    async fn token_registered(&self, event: &TokenRegistrationEvent) -> Result<(), PushError> {
        if let Some(delegate) = &self.delegate {
            delegate.token_registered(event).await?;
        }
        if let Some(publisher) = &self.publisher {
            publisher
                .publish(TokenRegistrationEvent::EVENT_TYPE, event.redacted_payload())
                .await?;
        }
        Ok(())
    }

    async fn token_invalidated(&self, event: &TokenInvalidationEvent) -> Result<(), PushError> {
        if let Some(delegate) = &self.delegate {
            delegate.token_invalidated(event).await?;
        }
        if let Some(publisher) = &self.publisher {
            publisher
                .publish(TokenInvalidationEvent::EVENT_TYPE, event.redacted_payload())
                .await?;
        }
        Ok(())
    }

    async fn token_refreshed(
        &self,
        old_token: &str,
        new_token: &str,
        device_id: &str,
        channel: PushChannel,
    ) -> Result<(), PushError> {
        if let Some(delegate) = &self.delegate {
            delegate
                .token_refreshed(old_token, new_token, device_id, channel)
                .await?;
        }
        if let Some(publisher) = &self.publisher {
            publisher
                .publish(
                    "push.token.refreshed",
                    json!({
                        "old_token_fingerprint": token_fingerprint(old_token),
                        "new_token_fingerprint": token_fingerprint(new_token),
                        "device_id": device_id,
                        "channel": channel,
                    }),
                )
                .await?;
        }
        Ok(())
    }
}
