use std::collections::{BTreeMap, VecDeque};
use std::sync::Mutex;

use async_trait::async_trait;

use crate::{
    BackendType, DeliveryGuarantee, JsonMessageSerializer, Message, MessageSerializer,
    MessageStatus, MessageTransport, MessagingConfig, MessagingError, MessagingHealth,
    MessagingPattern, Subscription, TransportCapabilities, TransportFeature,
};

#[derive(Default)]
struct QueueState {
    subscription: Option<Subscription>,
    pending: VecDeque<Message>,
    inflight: BTreeMap<String, Message>,
}

#[derive(Default)]
struct MemoryState {
    connected: bool,
    queues: BTreeMap<String, QueueState>,
    dead_letters: Vec<Message>,
}

pub struct MemoryTransport {
    config: MessagingConfig,
    state: Mutex<MemoryState>,
}

impl MemoryTransport {
    pub fn new(config: MessagingConfig) -> Result<Self, MessagingError> {
        if config.backend != BackendType::Memory {
            return Err(MessagingError::InvalidConfiguration(
                "MemoryTransport requires the memory backend".into(),
            ));
        }
        config.validate()?;
        Ok(Self {
            config,
            state: Mutex::new(MemoryState::default()),
        })
    }

    fn lock(&self) -> Result<std::sync::MutexGuard<'_, MemoryState>, MessagingError> {
        self.state
            .lock()
            .map_err(|error| MessagingError::Storage(error.to_string()))
    }

    fn ensure_connected(state: &MemoryState) -> Result<(), MessagingError> {
        if state.connected {
            Ok(())
        } else {
            Err(MessagingError::BackendUnavailable(
                "memory transport is disconnected".into(),
            ))
        }
    }

    #[must_use]
    pub fn dead_letters(&self) -> Vec<Message> {
        self.lock()
            .map_or_else(|_| Vec::new(), |state| state.dead_letters.clone())
    }
}

#[async_trait]
impl MessageTransport for MemoryTransport {
    async fn connect(&self) -> Result<(), MessagingError> {
        self.lock()?.connected = true;
        Ok(())
    }

    async fn disconnect(&self) -> Result<(), MessagingError> {
        let mut state = self.lock()?;
        state.connected = false;
        state.queues.clear();
        Ok(())
    }

    async fn publish(&self, mut message: Message) -> Result<(), MessagingError> {
        let payload_size = JsonMessageSerializer.serialize(&message)?.len();
        if payload_size > self.config.max_message_bytes {
            return Err(MessagingError::InvalidConfiguration(format!(
                "message size {payload_size} exceeds limit {}",
                self.config.max_message_bytes
            )));
        }
        let mut state = self.lock()?;
        Self::ensure_connected(&state)?;
        if message.topic.is_empty() {
            message.topic.clone_from(&self.config.default_topic);
        }
        message.status = MessageStatus::Pending;
        let mut delivered = 0;
        for queue in state.queues.values_mut() {
            if let Some(subscription) = &queue.subscription
                && subscription.topic == message.topic
                && subscription.filter.matches(&message)
            {
                queue.pending.push_back(message.clone());
                delivered += 1;
            }
        }
        if delivered == 0 {
            return Err(MessagingError::Unroutable(message.metadata.message_id));
        }
        Ok(())
    }

    async fn publish_batch(&self, messages: Vec<Message>) -> Vec<Result<(), MessagingError>> {
        if messages.len() > self.config.max_batch_size {
            return vec![Err(MessagingError::InvalidConfiguration(format!(
                "batch size exceeds limit {}",
                self.config.max_batch_size
            )))];
        }
        let mut results = Vec::with_capacity(messages.len());
        for message in messages {
            results.push(self.publish(message).await);
        }
        results
    }

    async fn subscribe(&self, subscription: Subscription) -> Result<(), MessagingError> {
        if subscription.id.trim().is_empty() || subscription.topic.trim().is_empty() {
            return Err(MessagingError::InvalidConfiguration(
                "subscription id and topic are required".into(),
            ));
        }
        let mut state = self.lock()?;
        Self::ensure_connected(&state)?;
        if state.queues.contains_key(&subscription.id) {
            return Err(MessagingError::Duplicate(subscription.id));
        }
        state.queues.insert(
            subscription.id.clone(),
            QueueState {
                subscription: Some(subscription),
                ..QueueState::default()
            },
        );
        Ok(())
    }

    async fn unsubscribe(&self, subscription_id: &str) -> Result<bool, MessagingError> {
        let mut state = self.lock()?;
        Self::ensure_connected(&state)?;
        Ok(state.queues.remove(subscription_id).is_some())
    }

    async fn poll(
        &self,
        subscription_id: &str,
        limit: usize,
        now_ms: u64,
    ) -> Result<Vec<Message>, MessagingError> {
        let mut state = self.lock()?;
        Self::ensure_connected(&state)?;
        let queue = state.queues.get_mut(subscription_id).ok_or_else(|| {
            MessagingError::InvalidConfiguration(format!("unknown subscription {subscription_id}"))
        })?;
        let mut candidates: Vec<_> = queue.pending.drain(..).collect();
        candidates.sort_by(|left, right| {
            right.priority.cmp(&left.priority).then(
                left.metadata
                    .created_at_ms
                    .cmp(&right.metadata.created_at_ms),
            )
        });
        let mut ready = Vec::new();
        for mut message in candidates {
            if ready.len() >= limit || !message.metadata.is_due(now_ms) {
                queue.pending.push_back(message);
            } else if !message.metadata.is_expired(now_ms) {
                message.status = MessageStatus::Processing;
                queue
                    .inflight
                    .insert(message.metadata.message_id.clone(), message.clone());
                ready.push(message);
            }
        }
        Ok(ready)
    }

    async fn acknowledge(
        &self,
        subscription_id: &str,
        message_id: &str,
    ) -> Result<(), MessagingError> {
        let mut state = self.lock()?;
        Self::ensure_connected(&state)?;
        let queue = state.queues.get_mut(subscription_id).ok_or_else(|| {
            MessagingError::InvalidConfiguration(format!("unknown subscription {subscription_id}"))
        })?;
        queue.inflight.remove(message_id).ok_or_else(|| {
            MessagingError::InvalidConfiguration(format!("message {message_id} is not in flight"))
        })?;
        Ok(())
    }

    async fn reject(
        &self,
        subscription_id: &str,
        mut message: Message,
        requeue: bool,
        reason: &str,
        now_ms: u64,
    ) -> Result<(), MessagingError> {
        let mut state = self.lock()?;
        Self::ensure_connected(&state)?;
        let queue = state.queues.get_mut(subscription_id).ok_or_else(|| {
            MessagingError::InvalidConfiguration(format!("unknown subscription {subscription_id}"))
        })?;
        queue.inflight.remove(&message.metadata.message_id);
        message
            .metadata
            .headers
            .insert("mmf-failure-reason".into(), reason.into());
        message
            .metadata
            .headers
            .insert("mmf-failed-at-ms".into(), now_ms.to_string());
        if requeue && message.can_retry() {
            message.retry_count = message.retry_count.saturating_add(1);
            message.status = MessageStatus::Retry;
            queue.pending.push_back(message);
        } else {
            message.status = MessageStatus::DeadLetter;
            state.dead_letters.push(message);
        }
        Ok(())
    }

    fn capabilities(&self) -> TransportCapabilities {
        TransportCapabilities {
            patterns: vec![
                MessagingPattern::PublishSubscribe,
                MessagingPattern::WorkQueue,
                MessagingPattern::Routing,
                MessagingPattern::PointToPoint,
                MessagingPattern::Broadcast,
            ],
            delivery_guarantees: vec![
                DeliveryGuarantee::AtMostOnce,
                DeliveryGuarantee::AtLeastOnce,
            ],
            features: [
                TransportFeature::Ordering,
                TransportFeature::Scheduling,
                TransportFeature::BatchPublish,
            ]
            .into(),
            maximum_message_bytes: self.config.max_message_bytes,
        }
    }

    async fn health(&self) -> Result<MessagingHealth, MessagingError> {
        let state = self.lock()?;
        let pending_messages = state.queues.values().map(|queue| queue.pending.len()).sum();
        Ok(MessagingHealth {
            connected: state.connected,
            backend: "memory".into(),
            subscriptions: state.queues.len(),
            pending_messages,
            pending_outbox: 0,
            dead_letters: state.dead_letters.len(),
            details: Vec::new(),
        })
    }
}
