use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PushChannel {
    Fcm,
    Apns,
    Sse,
    Webhook,
    Webpush,
    Websocket,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PushPriority {
    Low,
    #[default]
    Normal,
    High,
    Critical,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PushStatus {
    Pending,
    Sending,
    Delivered,
    Failed,
    Expired,
    Rejected,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct PushTarget {
    pub device_tokens: Vec<String>,
    pub connection_ids: Vec<String>,
    pub webhook_urls: Vec<String>,
    pub user_id: Option<String>,
    pub organization_id: Option<String>,
    pub channels: Vec<PushChannel>,
}

impl Default for PushTarget {
    fn default() -> Self {
        Self {
            device_tokens: Vec::new(),
            connection_ids: Vec::new(),
            webhook_urls: Vec::new(),
            user_id: None,
            organization_id: None,
            channels: vec![PushChannel::Fcm],
        }
    }
}

impl PushTarget {
    #[must_use]
    pub fn has_targets(&self) -> bool {
        !self.device_tokens.is_empty()
            || !self.connection_ids.is_empty()
            || !self.webhook_urls.is_empty()
            || self.user_id.is_some()
            || self.organization_id.is_some()
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct PushMessage {
    pub id: String,
    pub target: PushTarget,
    pub title: String,
    pub body: String,
    pub data: BTreeMap<String, Value>,
    pub priority: PushPriority,
    pub ttl_seconds: u64,
    pub collapse_key: Option<String>,
    pub mutable_content: bool,
    pub content_available: bool,
    pub created_at_ms: u64,
    pub correlation_id: Option<String>,
}

impl Default for PushMessage {
    fn default() -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            target: PushTarget::default(),
            title: String::new(),
            body: String::new(),
            data: BTreeMap::new(),
            priority: PushPriority::Normal,
            ttl_seconds: 86_400,
            collapse_key: None,
            mutable_content: false,
            content_available: false,
            created_at_ms: 0,
            correlation_id: None,
        }
    }
}

impl PushMessage {
    #[must_use]
    pub fn is_expired_at(&self, now_ms: u64) -> bool {
        let age_ms = now_ms.saturating_sub(self.created_at_ms);
        age_ms > self.ttl_seconds.saturating_mul(1_000)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct PushResult {
    pub message_id: String,
    pub channel: PushChannel,
    pub status: PushStatus,
    pub success: bool,
    pub attempted_at_ms: u64,
    pub delivered_at_ms: Option<u64>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    pub attempt_number: u32,
    pub should_retry: bool,
    pub retry_after_seconds: Option<u64>,
    #[serde(default)]
    pub failed_tokens: Vec<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}

impl PushResult {
    #[must_use]
    pub fn delivered(message_id: impl Into<String>, channel: PushChannel, now_ms: u64) -> Self {
        Self {
            message_id: message_id.into(),
            channel,
            status: PushStatus::Delivered,
            success: true,
            attempted_at_ms: now_ms,
            delivered_at_ms: Some(now_ms),
            error_code: None,
            error_message: None,
            attempt_number: 1,
            should_retry: false,
            retry_after_seconds: None,
            failed_tokens: Vec::new(),
            metadata: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn failure(
        message_id: impl Into<String>,
        channel: PushChannel,
        status: PushStatus,
        code: impl Into<String>,
        detail: impl Into<String>,
        now_ms: u64,
    ) -> Self {
        Self {
            message_id: message_id.into(),
            channel,
            status,
            success: false,
            attempted_at_ms: now_ms,
            delivered_at_ms: None,
            error_code: Some(code.into()),
            error_message: Some(detail.into()),
            attempt_number: 1,
            should_retry: false,
            retry_after_seconds: None,
            failed_tokens: Vec::new(),
            metadata: BTreeMap::new(),
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PushHealthStatus {
    Healthy,
    Degraded,
    Unavailable,
    Stopped,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct PushAdapterHealth {
    pub channel: PushChannel,
    pub status: PushHealthStatus,
    pub detail: Option<String>,
    pub checked_at_ms: u64,
}
