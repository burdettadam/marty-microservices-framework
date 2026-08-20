use std::collections::BTreeSet;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};

use crate::{DeliveryGuarantee, EventFilter, Message, MessagingError, MessagingPattern};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Subscription {
    pub id: String,
    pub topic: String,
    pub consumer_group: Option<String>,
    pub filter: EventFilter,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct TransportCapabilities {
    pub patterns: Vec<MessagingPattern>,
    pub delivery_guarantees: Vec<DeliveryGuarantee>,
    pub features: BTreeSet<TransportFeature>,
    pub maximum_message_bytes: usize,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TransportFeature {
    Ordering,
    Transactions,
    Replay,
    Scheduling,
    BatchPublish,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct MessagingHealth {
    pub connected: bool,
    pub backend: String,
    pub subscriptions: usize,
    pub pending_messages: usize,
    pub pending_outbox: usize,
    pub dead_letters: usize,
    pub details: Vec<String>,
}

#[async_trait]
pub trait MessageTransport: Send + Sync {
    async fn connect(&self) -> Result<(), MessagingError>;
    async fn disconnect(&self) -> Result<(), MessagingError>;
    async fn publish(&self, message: Message) -> Result<(), MessagingError>;
    async fn publish_batch(&self, messages: Vec<Message>) -> Vec<Result<(), MessagingError>>;
    async fn subscribe(&self, subscription: Subscription) -> Result<(), MessagingError>;
    async fn unsubscribe(&self, subscription_id: &str) -> Result<bool, MessagingError>;
    async fn poll(
        &self,
        subscription_id: &str,
        limit: usize,
        now_ms: u64,
    ) -> Result<Vec<Message>, MessagingError>;
    async fn acknowledge(
        &self,
        subscription_id: &str,
        message_id: &str,
    ) -> Result<(), MessagingError>;
    async fn reject(
        &self,
        subscription_id: &str,
        message: Message,
        requeue: bool,
        reason: &str,
        now_ms: u64,
    ) -> Result<(), MessagingError>;
    fn capabilities(&self) -> TransportCapabilities;
    async fn health(&self) -> Result<MessagingHealth, MessagingError>;
}

#[async_trait]
pub trait MessageSerializer: Send + Sync {
    fn content_type(&self) -> &'static str;
    fn serialize(&self, message: &Message) -> Result<Vec<u8>, MessagingError>;
    fn deserialize(&self, payload: &[u8]) -> Result<Message, MessagingError>;
}

#[derive(Clone, Copy, Debug, Default)]
pub struct JsonMessageSerializer;

#[async_trait]
impl MessageSerializer for JsonMessageSerializer {
    fn content_type(&self) -> &'static str {
        "application/json"
    }

    fn serialize(&self, message: &Message) -> Result<Vec<u8>, MessagingError> {
        serde_json::to_vec(message)
            .map_err(|error| MessagingError::Serialization(error.to_string()))
    }

    fn deserialize(&self, payload: &[u8]) -> Result<Message, MessagingError> {
        serde_json::from_slice(payload)
            .map_err(|error| MessagingError::Serialization(error.to_string()))
    }
}

/// Provider markers make production startup explicit and fail closed when a
/// selected transport has not been installed.
#[async_trait]
pub trait KafkaTransport: MessageTransport {}
#[async_trait]
pub trait DatabaseTransport: MessageTransport {}
#[async_trait]
pub trait NatsTransport: MessageTransport {}
#[async_trait]
pub trait RabbitMqTransport: MessageTransport {}
#[async_trait]
pub trait RedisTransport: MessageTransport {}
#[async_trait]
pub trait AwsSqsTransport: MessageTransport {}
#[async_trait]
pub trait AwsSnsTransport: MessageTransport {}
