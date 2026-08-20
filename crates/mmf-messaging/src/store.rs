use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

use crate::{Message, MessageStatus, MessagingError};

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct OutboxEntry {
    pub message: Message,
    pub partition: u32,
    pub status: MessageStatus,
    pub attempt_count: u32,
    pub max_attempts: u32,
    pub next_attempt_at_ms: Option<u64>,
    pub last_error: Option<String>,
    pub processed_at_ms: Option<u64>,
}

impl OutboxEntry {
    #[must_use]
    pub fn is_pending(&self, now_ms: u64) -> bool {
        matches!(self.status, MessageStatus::Pending | MessageStatus::Retry)
            && self.message.metadata.is_due(now_ms)
            && !self.message.metadata.is_expired(now_ms)
            && self.next_attempt_at_ms.is_none_or(|retry| retry <= now_ms)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DeadLetter {
    pub message_id: String,
    pub message_type: String,
    pub topic: String,
    pub reason: String,
    pub failed_at_ms: u64,
    pub attempt_count: u32,
}

#[derive(Default)]
pub struct InMemoryDeliveryStore {
    outbox: BTreeMap<String, OutboxEntry>,
    inbox: BTreeMap<String, u64>,
    dead_letters: BTreeMap<String, DeadLetter>,
}

impl InMemoryDeliveryStore {
    pub fn enqueue(&mut self, message: Message, partitions: u32) -> Result<u32, MessagingError> {
        if partitions == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "partition count must be greater than zero".into(),
            ));
        }
        let message_id = message.metadata.message_id.clone();
        if self.outbox.contains_key(&message_id) {
            return Err(MessagingError::Duplicate(message_id));
        }
        let partition_key = message
            .metadata
            .partition_key
            .as_deref()
            .or(message.metadata.ordering_key.as_deref())
            .unwrap_or(&message_id);
        let partition = stable_partition(partition_key, partitions);
        let max_attempts = message.max_retries.saturating_add(1);
        self.outbox.insert(
            message_id,
            OutboxEntry {
                message,
                partition,
                status: MessageStatus::Pending,
                attempt_count: 0,
                max_attempts,
                next_attempt_at_ms: None,
                last_error: None,
                processed_at_ms: None,
            },
        );
        Ok(partition)
    }

    #[must_use]
    pub fn pending(&self, now_ms: u64, limit: usize, partition: Option<u32>) -> Vec<OutboxEntry> {
        let mut entries: Vec<_> = self
            .outbox
            .values()
            .filter(|entry| {
                entry.is_pending(now_ms) && partition.is_none_or(|p| entry.partition == p)
            })
            .cloned()
            .collect();
        entries.sort_by(|left, right| {
            right
                .message
                .priority
                .cmp(&left.message.priority)
                .then(
                    left.message
                        .metadata
                        .created_at_ms
                        .cmp(&right.message.metadata.created_at_ms),
                )
                .then(
                    left.message
                        .metadata
                        .message_id
                        .cmp(&right.message.metadata.message_id),
                )
        });
        entries.truncate(limit);
        entries
    }

    pub fn mark_processing(&mut self, message_id: &str) -> Result<(), MessagingError> {
        let entry = self.outbox.get_mut(message_id).ok_or_else(|| {
            MessagingError::Storage(format!("outbox message {message_id} not found"))
        })?;
        entry.attempt_count = entry.attempt_count.saturating_add(1);
        entry.status = MessageStatus::Processing;
        Ok(())
    }

    pub fn mark_processed(&mut self, message_id: &str, now_ms: u64) -> Result<(), MessagingError> {
        let entry = self.outbox.get_mut(message_id).ok_or_else(|| {
            MessagingError::Storage(format!("outbox message {message_id} not found"))
        })?;
        entry.status = MessageStatus::Processed;
        entry.processed_at_ms = Some(now_ms);
        entry.last_error = None;
        Ok(())
    }

    pub fn mark_failed(
        &mut self,
        message_id: &str,
        reason: impl Into<String>,
        next_attempt_at_ms: Option<u64>,
        now_ms: u64,
    ) -> Result<MessageStatus, MessagingError> {
        let reason = reason.into();
        let entry = self.outbox.get_mut(message_id).ok_or_else(|| {
            MessagingError::Storage(format!("outbox message {message_id} not found"))
        })?;
        entry.last_error = Some(reason.clone());
        if entry.attempt_count >= entry.max_attempts {
            entry.status = MessageStatus::DeadLetter;
            self.dead_letters.insert(
                message_id.to_owned(),
                DeadLetter {
                    message_id: message_id.to_owned(),
                    message_type: entry.message.message_type.clone(),
                    topic: entry.message.topic.clone(),
                    reason,
                    failed_at_ms: now_ms,
                    attempt_count: entry.attempt_count,
                },
            );
        } else {
            entry.status = MessageStatus::Retry;
            entry.next_attempt_at_ms = next_attempt_at_ms;
        }
        Ok(entry.status)
    }

    pub fn requeue_dead_letter(&mut self, message_id: &str) -> Result<bool, MessagingError> {
        if self.dead_letters.remove(message_id).is_none() {
            return Ok(false);
        }
        let entry = self.outbox.get_mut(message_id).ok_or_else(|| {
            MessagingError::Storage(format!("outbox message {message_id} not found"))
        })?;
        entry.status = MessageStatus::Pending;
        entry.attempt_count = 0;
        entry.next_attempt_at_ms = None;
        entry.last_error = None;
        Ok(true)
    }

    pub fn begin_inbox(&mut self, message_id: &str, now_ms: u64) -> Result<(), MessagingError> {
        if self.inbox.contains_key(message_id) {
            return Err(MessagingError::Duplicate(message_id.to_owned()));
        }
        self.inbox.insert(message_id.to_owned(), now_ms);
        Ok(())
    }

    pub fn cleanup(&mut self, before_ms: u64) -> (usize, usize) {
        let outbox_before = self.outbox.len();
        self.outbox.retain(|_, entry| {
            entry
                .processed_at_ms
                .is_none_or(|processed| processed >= before_ms)
        });
        let inbox_before = self.inbox.len();
        self.inbox.retain(|_, processed| *processed >= before_ms);
        (
            outbox_before - self.outbox.len(),
            inbox_before - self.inbox.len(),
        )
    }

    #[must_use]
    pub fn dead_letters(&self) -> Vec<DeadLetter> {
        self.dead_letters.values().cloned().collect()
    }

    #[must_use]
    pub fn replay_ids(&self, message_type: Option<&str>) -> BTreeSet<String> {
        self.outbox
            .values()
            .filter(|entry| message_type.is_none_or(|kind| entry.message.message_type == kind))
            .map(|entry| entry.message.metadata.message_id.clone())
            .collect()
    }

    #[must_use]
    pub fn pending_count(&self, now_ms: u64) -> usize {
        self.outbox
            .values()
            .filter(|entry| entry.is_pending(now_ms))
            .count()
    }
}

#[must_use]
pub fn stable_partition(key: &str, partition_count: u32) -> u32 {
    let hash = key.as_bytes().iter().fold(2_166_136_261_u32, |hash, byte| {
        (hash ^ u32::from(*byte)).wrapping_mul(16_777_619)
    });
    hash % partition_count.max(1)
}
