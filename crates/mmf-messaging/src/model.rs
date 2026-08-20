use std::collections::BTreeMap;

use mmf_resilience::RetryConfig;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

use crate::MessagingError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BackendType {
    Memory,
    Database,
    Kafka,
    RabbitMq,
    Redis,
    Nats,
    AwsSqs,
    AwsSns,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MessagingPattern {
    PublishSubscribe,
    RequestReply,
    WorkQueue,
    Routing,
    Rpc,
    StreamProcessing,
    PointToPoint,
    Broadcast,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DeliveryGuarantee {
    AtMostOnce,
    AtLeastOnce,
    ExactlyOnce,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MessagePriority {
    Low,
    Normal,
    High,
    Critical,
}

impl MessagePriority {
    #[must_use]
    pub const fn value(self) -> u8 {
        match self {
            Self::Low => 1,
            Self::Normal => 5,
            Self::High => 10,
            Self::Critical => 15,
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MessageStatus {
    Pending,
    Scheduled,
    Processing,
    Processed,
    Failed,
    DeadLetter,
    Retry,
    Skipped,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EventKind {
    Generic,
    Domain,
    Integration,
    System,
    Plugin,
    Workflow,
    Audit,
    Notification,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SerializationFormat {
    Json,
    Cbor,
    MessagePack,
    Avro,
    Protobuf,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct MessageMetadata {
    pub message_id: String,
    pub correlation_id: Option<String>,
    pub causation_id: Option<String>,
    pub tenant_id: Option<String>,
    pub source_service: Option<String>,
    pub target_service: Option<String>,
    pub trace_parent: Option<String>,
    pub created_at_ms: u64,
    pub scheduled_at_ms: Option<u64>,
    pub expires_at_ms: Option<u64>,
    pub schema_version: u32,
    pub content_type: String,
    pub content_encoding: String,
    pub partition_key: Option<String>,
    pub ordering_key: Option<String>,
    pub deduplication_key: Option<String>,
    #[serde(default)]
    pub headers: BTreeMap<String, String>,
}

impl MessageMetadata {
    #[must_use]
    pub fn new(created_at_ms: u64) -> Self {
        Self {
            message_id: Uuid::new_v4().to_string(),
            correlation_id: None,
            causation_id: None,
            tenant_id: None,
            source_service: None,
            target_service: None,
            trace_parent: None,
            created_at_ms,
            scheduled_at_ms: None,
            expires_at_ms: None,
            schema_version: 1,
            content_type: "application/json".into(),
            content_encoding: "utf-8".into(),
            partition_key: None,
            ordering_key: None,
            deduplication_key: None,
            headers: BTreeMap::new(),
        }
    }

    #[must_use]
    pub fn is_expired(&self, now_ms: u64) -> bool {
        self.expires_at_ms.is_some_and(|expiry| now_ms > expiry)
    }

    #[must_use]
    pub fn is_due(&self, now_ms: u64) -> bool {
        self.scheduled_at_ms
            .is_none_or(|scheduled| scheduled <= now_ms)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Message {
    pub metadata: MessageMetadata,
    pub kind: EventKind,
    pub message_type: String,
    pub pattern: MessagingPattern,
    pub delivery_guarantee: DeliveryGuarantee,
    pub priority: MessagePriority,
    pub status: MessageStatus,
    pub topic: String,
    pub routing_key: String,
    pub reply_to: Option<String>,
    pub payload: Value,
    pub retry_count: u32,
    pub max_retries: u32,
}

impl Message {
    pub fn validate(&self, now_ms: u64) -> Result<(), MessagingError> {
        if self.metadata.message_id.trim().is_empty() {
            return Err(MessagingError::InvalidConfiguration(
                "message_id must not be empty".into(),
            ));
        }
        if self.message_type.trim().is_empty() {
            return Err(MessagingError::InvalidConfiguration(
                "message_type must not be empty".into(),
            ));
        }
        if self.metadata.schema_version == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "schema_version must be greater than zero".into(),
            ));
        }
        if self.metadata.is_expired(now_ms) {
            return Err(MessagingError::Expired);
        }
        Ok(())
    }

    #[must_use]
    pub const fn can_retry(&self) -> bool {
        self.retry_count < self.max_retries
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct MessagingConfig {
    pub backend: BackendType,
    pub required: bool,
    pub endpoint: Option<String>,
    pub default_topic: String,
    pub default_delivery_guarantee: DeliveryGuarantee,
    pub max_message_bytes: usize,
    pub max_batch_size: usize,
    pub retry: RetryConfig,
    pub dead_letter_topic: String,
    pub inbox_retention_ms: u64,
    pub outbox_retention_ms: u64,
}

impl Default for MessagingConfig {
    fn default() -> Self {
        Self {
            backend: BackendType::Memory,
            required: true,
            endpoint: None,
            default_topic: "mmf.events".into(),
            default_delivery_guarantee: DeliveryGuarantee::AtLeastOnce,
            max_message_bytes: 1024 * 1024,
            max_batch_size: 100,
            retry: RetryConfig::default(),
            dead_letter_topic: "mmf.dead-letter".into(),
            inbox_retention_ms: 7 * 24 * 60 * 60 * 1_000,
            outbox_retention_ms: 7 * 24 * 60 * 60 * 1_000,
        }
    }
}

impl MessagingConfig {
    pub fn validate(&self) -> Result<(), MessagingError> {
        if self.max_message_bytes == 0 || self.max_batch_size == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "message and batch limits must be greater than zero".into(),
            ));
        }
        if self.backend != BackendType::Memory && self.endpoint.as_deref().is_none_or(str::is_empty)
        {
            return Err(MessagingError::BackendUnavailable(format!(
                "{:?} endpoint is required",
                self.backend
            )));
        }
        self.retry
            .validate()
            .map_err(|error| MessagingError::InvalidConfiguration(error.to_string()))
    }
}

#[must_use]
pub fn recommend_pattern(
    use_case: &str,
    ordering_required: bool,
    response_needed: bool,
    high_throughput: bool,
) -> MessagingPattern {
    if response_needed {
        return MessagingPattern::RequestReply;
    }
    if high_throughput && ordering_required {
        return MessagingPattern::StreamProcessing;
    }
    let normalized = use_case.to_ascii_lowercase();
    if normalized.contains("notification") || normalized.contains("event") {
        MessagingPattern::PublishSubscribe
    } else if normalized.contains("command") || normalized.contains("task") {
        MessagingPattern::PointToPoint
    } else if normalized.contains("broadcast") {
        MessagingPattern::Broadcast
    } else {
        MessagingPattern::PublishSubscribe
    }
}
