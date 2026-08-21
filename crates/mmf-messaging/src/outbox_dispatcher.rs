use std::{sync::Arc, time::Duration};

use async_trait::async_trait;
use tokio::sync::watch;

use crate::{MessageStatus, MessageTransport, MessagingError, OutboxEntry};

#[cfg(feature = "postgres")]
use crate::PostgresOutboxStore;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct OutboxDispatcherConfig {
    pub batch_size: usize,
    pub lease_duration_ms: u64,
    pub poll_interval_ms: u64,
    pub retry_base_ms: u64,
    pub retry_max_ms: u64,
    pub partition: Option<u32>,
}

impl Default for OutboxDispatcherConfig {
    fn default() -> Self {
        Self {
            batch_size: 100,
            lease_duration_ms: 30_000,
            poll_interval_ms: 250,
            retry_base_ms: 1_000,
            retry_max_ms: 60_000,
            partition: None,
        }
    }
}

impl OutboxDispatcherConfig {
    pub fn validate(&self) -> Result<(), MessagingError> {
        if self.batch_size == 0
            || self.lease_duration_ms == 0
            || self.poll_interval_ms == 0
            || self.retry_base_ms == 0
            || self.retry_max_ms < self.retry_base_ms
        {
            return Err(MessagingError::InvalidConfiguration(
                "outbox dispatcher requires a positive batch, lease, poll interval, and valid retry range"
                    .into(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn retry_delay_ms(&self, attempt_count: u32) -> u64 {
        let exponent = attempt_count.saturating_sub(1).min(63);
        self.retry_base_ms
            .saturating_mul(1_u64 << exponent)
            .min(self.retry_max_ms)
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct OutboxDispatchReport {
    pub claimed: usize,
    pub delivered: usize,
    pub retrying: usize,
    pub dead_lettered: usize,
}

#[async_trait]
pub trait OutboxLeaseStore: Send + Sync {
    async fn claim_due(
        &self,
        now_ms: u64,
        lease_duration_ms: u64,
        limit: usize,
        partition: Option<u32>,
    ) -> Result<Vec<OutboxEntry>, MessagingError>;

    async fn mark_processed_by_lease(
        &self,
        message_id: &str,
        lease_token: &str,
        now_ms: u64,
    ) -> Result<(), MessagingError>;

    async fn mark_failed_by_lease(
        &self,
        message_id: &str,
        lease_token: &str,
        reason: &str,
        next_attempt_at_ms: Option<u64>,
        now_ms: u64,
    ) -> Result<MessageStatus, MessagingError>;
}

#[cfg(feature = "postgres")]
#[async_trait]
impl OutboxLeaseStore for PostgresOutboxStore {
    async fn claim_due(
        &self,
        now_ms: u64,
        lease_duration_ms: u64,
        limit: usize,
        partition: Option<u32>,
    ) -> Result<Vec<OutboxEntry>, MessagingError> {
        self.claim_due(now_ms, lease_duration_ms, limit, partition)
            .await
    }

    async fn mark_processed_by_lease(
        &self,
        message_id: &str,
        lease_token: &str,
        now_ms: u64,
    ) -> Result<(), MessagingError> {
        self.mark_processed_by_lease(message_id, lease_token, now_ms)
            .await
    }

    async fn mark_failed_by_lease(
        &self,
        message_id: &str,
        lease_token: &str,
        reason: &str,
        next_attempt_at_ms: Option<u64>,
        now_ms: u64,
    ) -> Result<MessageStatus, MessagingError> {
        self.mark_failed_by_lease(message_id, lease_token, reason, next_attempt_at_ms, now_ms)
            .await
    }
}

pub async fn dispatch_outbox_once<S, T>(
    store: &S,
    transport: &T,
    config: &OutboxDispatcherConfig,
    now_ms: u64,
) -> Result<OutboxDispatchReport, MessagingError>
where
    S: OutboxLeaseStore + ?Sized,
    T: MessageTransport + ?Sized,
{
    config.validate()?;
    let entries = store
        .claim_due(
            now_ms,
            config.lease_duration_ms,
            config.batch_size,
            config.partition,
        )
        .await?;
    let mut report = OutboxDispatchReport {
        claimed: entries.len(),
        ..OutboxDispatchReport::default()
    };

    for entry in entries {
        let message_id = entry.message.metadata.message_id.clone();
        let lease_token = entry.lease_token.as_deref().ok_or_else(|| {
            MessagingError::Storage(format!(
                "claimed outbox message {message_id} has no lease token"
            ))
        })?;
        match transport.publish(entry.message.clone()).await {
            Ok(()) => {
                store
                    .mark_processed_by_lease(&message_id, lease_token, now_ms)
                    .await?;
                report.delivered += 1;
            }
            Err(error) => {
                let retry_at = now_ms.saturating_add(config.retry_delay_ms(entry.attempt_count));
                let status = store
                    .mark_failed_by_lease(
                        &message_id,
                        lease_token,
                        &error.to_string(),
                        Some(retry_at),
                        now_ms,
                    )
                    .await?;
                if status == MessageStatus::DeadLetter {
                    report.dead_lettered += 1;
                } else {
                    report.retrying += 1;
                }
            }
        }
    }
    Ok(report)
}

pub async fn run_outbox_dispatcher<S>(
    store: Arc<S>,
    transport: Arc<dyn MessageTransport>,
    config: OutboxDispatcherConfig,
    mut shutdown: watch::Receiver<bool>,
) -> Result<(), MessagingError>
where
    S: OutboxLeaseStore + 'static,
{
    config.validate()?;
    let result = async {
        loop {
            if *shutdown.borrow() {
                break;
            }
            if transport.connect().await.is_err() {
                wait_for_poll_or_shutdown(config.poll_interval_ms, &mut shutdown).await;
                continue;
            }
            dispatch_outbox_once(store.as_ref(), transport.as_ref(), &config, unix_time_ms())
                .await?;
            wait_for_poll_or_shutdown(config.poll_interval_ms, &mut shutdown).await;
        }
        Ok(())
    }
    .await;
    let disconnect = transport.disconnect().await;
    result.and(disconnect)
}

async fn wait_for_poll_or_shutdown(interval_ms: u64, shutdown: &mut watch::Receiver<bool>) {
    tokio::select! {
        () = tokio::time::sleep(Duration::from_millis(interval_ms)) => {}
        _ = shutdown.changed() => {}
    }
}

fn unix_time_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |duration| {
            u64::try_from(duration.as_millis()).unwrap_or(u64::MAX)
        })
}

#[cfg(test)]
mod tests {
    use std::sync::Mutex;

    use serde_json::json;

    use super::*;
    use crate::{
        BackendType, DeliveryGuarantee, EventFilter, EventKind, MemoryTransport, Message,
        MessageMetadata, MessagePriority, MessagingConfig, MessagingPattern, Subscription,
    };

    struct LeaseStore {
        entries: Mutex<Vec<OutboxEntry>>,
        processed: Mutex<Vec<String>>,
        failed: Mutex<Vec<(String, u64)>>,
        failure_status: MessageStatus,
    }

    #[async_trait]
    impl OutboxLeaseStore for LeaseStore {
        async fn claim_due(
            &self,
            _now_ms: u64,
            _lease_duration_ms: u64,
            _limit: usize,
            _partition: Option<u32>,
        ) -> Result<Vec<OutboxEntry>, MessagingError> {
            Ok(std::mem::take(&mut *self.entries.lock().expect("entries")))
        }

        async fn mark_processed_by_lease(
            &self,
            message_id: &str,
            _lease_token: &str,
            _now_ms: u64,
        ) -> Result<(), MessagingError> {
            self.processed
                .lock()
                .expect("processed")
                .push(message_id.into());
            Ok(())
        }

        async fn mark_failed_by_lease(
            &self,
            message_id: &str,
            _lease_token: &str,
            _reason: &str,
            next_attempt_at_ms: Option<u64>,
            _now_ms: u64,
        ) -> Result<MessageStatus, MessagingError> {
            self.failed
                .lock()
                .expect("failed")
                .push((message_id.into(), next_attempt_at_ms.expect("retry time")));
            Ok(self.failure_status)
        }
    }

    fn entry(message_id: &str) -> OutboxEntry {
        let mut metadata = MessageMetadata::new(1_000);
        metadata.message_id = message_id.into();
        OutboxEntry {
            message: Message {
                metadata,
                kind: EventKind::Domain,
                message_type: "organization.created.event".into(),
                pattern: MessagingPattern::PublishSubscribe,
                delivery_guarantee: DeliveryGuarantee::AtLeastOnce,
                priority: MessagePriority::Normal,
                status: MessageStatus::Processing,
                topic: "marty.organization.events".into(),
                routing_key: "organization.created.event".into(),
                reply_to: None,
                payload: json!({"organization_id":"org-1"}),
                retry_count: 0,
                max_retries: 3,
            },
            partition: 0,
            status: MessageStatus::Processing,
            attempt_count: 2,
            max_attempts: 4,
            next_attempt_at_ms: None,
            last_error: None,
            processed_at_ms: None,
            lease_token: Some("lease-1".into()),
            lease_expires_at_ms: Some(31_000),
        }
    }

    fn lease_store(entry: OutboxEntry, failure_status: MessageStatus) -> LeaseStore {
        LeaseStore {
            entries: Mutex::new(vec![entry]),
            processed: Mutex::new(Vec::new()),
            failed: Mutex::new(Vec::new()),
            failure_status,
        }
    }

    #[test]
    fn retry_backoff_is_bounded_and_configuration_fails_closed() {
        let config = OutboxDispatcherConfig {
            retry_base_ms: 100,
            retry_max_ms: 1_000,
            ..OutboxDispatcherConfig::default()
        };
        assert_eq!(config.retry_delay_ms(1), 100);
        assert_eq!(config.retry_delay_ms(2), 200);
        assert_eq!(config.retry_delay_ms(5), 1_000);
        assert_eq!(config.retry_delay_ms(u32::MAX), 1_000);

        let invalid = OutboxDispatcherConfig {
            batch_size: 0,
            ..config
        };
        assert!(matches!(
            invalid.validate(),
            Err(MessagingError::InvalidConfiguration(_))
        ));
    }

    #[tokio::test]
    async fn claimed_messages_are_acknowledged_only_after_transport_delivery() {
        let store = lease_store(entry("message-1"), MessageStatus::Retry);
        let transport = MemoryTransport::new(MessagingConfig {
            backend: BackendType::Memory,
            ..MessagingConfig::default()
        })
        .expect("transport");
        transport.connect().await.expect("connect");
        transport
            .subscribe(Subscription {
                id: "consumer".into(),
                topic: "marty.organization.events".into(),
                consumer_group: None,
                filter: EventFilter::default(),
            })
            .await
            .expect("subscribe");

        let report = dispatch_outbox_once(
            &store,
            &transport,
            &OutboxDispatcherConfig::default(),
            10_000,
        )
        .await
        .expect("dispatch");

        assert_eq!(
            report,
            OutboxDispatchReport {
                claimed: 1,
                delivered: 1,
                retrying: 0,
                dead_lettered: 0,
            }
        );
        assert_eq!(*store.processed.lock().expect("processed"), ["message-1"]);
        assert!(store.failed.lock().expect("failed").is_empty());
    }

    #[tokio::test]
    async fn failed_delivery_is_retried_without_false_acknowledgement() {
        let store = lease_store(entry("message-2"), MessageStatus::Retry);
        let transport = MemoryTransport::new(MessagingConfig::default()).expect("transport");
        transport.connect().await.expect("connect");
        let config = OutboxDispatcherConfig {
            retry_base_ms: 100,
            retry_max_ms: 1_000,
            ..OutboxDispatcherConfig::default()
        };

        let report = dispatch_outbox_once(&store, &transport, &config, 10_000)
            .await
            .expect("dispatch");

        assert_eq!(report.claimed, 1);
        assert_eq!(report.retrying, 1);
        assert_eq!(report.delivered, 0);
        assert!(store.processed.lock().expect("processed").is_empty());
        assert_eq!(
            *store.failed.lock().expect("failed"),
            [("message-2".into(), 10_200)]
        );
    }
}
