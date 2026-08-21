use std::collections::BTreeMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use tokio::sync::mpsc;

use crate::{
    PushAdapter, PushAdapterHealth, PushChannel, PushError, PushHealthStatus, PushMessage,
    PushResult, PushStatus,
};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct SseConfig {
    pub heartbeat_interval_seconds: u64,
    pub max_connections_per_user: usize,
    pub stale_timeout_seconds: u64,
    pub event_id_format: String,
    pub queue_capacity: usize,
    pub send_timeout_ms: u64,
}

impl Default for SseConfig {
    fn default() -> Self {
        Self {
            heartbeat_interval_seconds: 30,
            max_connections_per_user: 5,
            stale_timeout_seconds: 300,
            event_id_format: "{message_id}".into(),
            queue_capacity: 128,
            send_timeout_ms: 1_000,
        }
    }
}

impl SseConfig {
    pub fn validate(&self) -> Result<(), PushError> {
        if self.heartbeat_interval_seconds == 0
            || self.max_connections_per_user == 0
            || self.stale_timeout_seconds == 0
            || self.queue_capacity == 0
            || self.send_timeout_ms == 0
        {
            return Err(PushError::InvalidConfiguration(
                "SSE intervals, limits, and queue capacity must be greater than zero".into(),
            ));
        }
        if !self.event_id_format.contains("{message_id}") {
            return Err(PushError::InvalidConfiguration(
                "SSE event_id_format must contain {message_id}".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SseConnection {
    pub id: String,
    pub user_id: Option<String>,
    pub organization_id: Option<String>,
    pub device_id: Option<String>,
    pub connected_at_ms: u64,
    pub last_activity_ms: u64,
    pub last_event_id: Option<String>,
}

struct ConnectionEntry {
    connection: SseConnection,
    sender: mpsc::Sender<String>,
}

pub struct SseSubscription {
    pub connection: SseConnection,
    receiver: mpsc::Receiver<String>,
    heartbeat_interval: Duration,
}

impl SseSubscription {
    pub async fn next(&mut self) -> Option<String> {
        self.receiver.recv().await
    }

    pub fn try_next(&mut self) -> Result<String, tokio::sync::mpsc::error::TryRecvError> {
        self.receiver.try_recv()
    }

    pub async fn next_event(&mut self) -> Option<String> {
        match tokio::time::timeout(self.heartbeat_interval, self.receiver.recv()).await {
            Ok(event) => event,
            Err(_) => Some(SseAdapter::heartbeat_event().into()),
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct SseConnectionStats {
    pub total_connections: usize,
    pub by_organization: BTreeMap<String, usize>,
    pub by_user: BTreeMap<String, usize>,
    pub heartbeat_interval_seconds: u64,
}

pub struct SseAdapter {
    config: SseConfig,
    connections: Arc<Mutex<BTreeMap<String, ConnectionEntry>>>,
    running: Arc<AtomicBool>,
    heartbeat_task: Mutex<Option<tokio::task::JoinHandle<()>>>,
    last_error: RwLock<Option<String>>,
}

impl SseAdapter {
    pub fn new(config: SseConfig) -> Result<Self, PushError> {
        config.validate()?;
        Ok(Self {
            config,
            connections: Arc::new(Mutex::new(BTreeMap::new())),
            running: Arc::new(AtomicBool::new(false)),
            heartbeat_task: Mutex::new(None),
            last_error: RwLock::new(None),
        })
    }

    pub fn add_connection(
        &self,
        connection_id: impl Into<String>,
        user_id: Option<String>,
        organization_id: Option<String>,
        device_id: Option<String>,
        now_ms: u64,
    ) -> SseSubscription {
        let id = connection_id.into();
        let mut connections = self
            .connections
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if let Some(user_id) = &user_id {
            let mut matching: Vec<_> = connections
                .iter()
                .filter(|(_, entry)| entry.connection.user_id.as_ref() == Some(user_id))
                .map(|(id, entry)| (id.clone(), entry.connection.connected_at_ms))
                .collect();
            matching.sort_by_key(|(_, connected_at)| *connected_at);
            let remove_count = matching
                .len()
                .saturating_add(1)
                .saturating_sub(self.config.max_connections_per_user);
            for (oldest, _) in matching.into_iter().take(remove_count) {
                connections.remove(&oldest);
            }
        }
        let connection = SseConnection {
            id: id.clone(),
            user_id,
            organization_id,
            device_id,
            connected_at_ms: now_ms,
            last_activity_ms: now_ms,
            last_event_id: None,
        };
        let (sender, receiver) = mpsc::channel(self.config.queue_capacity);
        connections.insert(
            id,
            ConnectionEntry {
                connection: connection.clone(),
                sender,
            },
        );
        SseSubscription {
            connection,
            receiver,
            heartbeat_interval: Duration::from_secs(self.config.heartbeat_interval_seconds),
        }
    }

    pub fn remove_connection(&self, connection_id: &str) -> bool {
        self.connections
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .remove(connection_id)
            .is_some()
    }

    pub fn cleanup_stale(&self, now_ms: u64) -> Vec<String> {
        let stale_after = self.config.stale_timeout_seconds.saturating_mul(1_000);
        let mut connections = self
            .connections
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let stale: Vec<_> = connections
            .iter()
            .filter(|(_, entry)| {
                now_ms.saturating_sub(entry.connection.last_activity_ms) > stale_after
            })
            .map(|(id, _)| id.clone())
            .collect();
        for id in &stale {
            connections.remove(id);
        }
        stale
    }

    #[must_use]
    pub fn heartbeat_event() -> &'static str {
        ": heartbeat\n\n"
    }

    #[must_use]
    pub fn build_event(&self, message: &PushMessage) -> String {
        let event_id = self
            .config
            .event_id_format
            .replace("{message_id}", &message.id);
        let event_type = message
            .data
            .get("event_type")
            .and_then(Value::as_str)
            .unwrap_or("message");
        let payload = json!({
            "id": message.id,
            "title": message.title,
            "body": message.body,
            "data": message.data,
            "priority": message.priority,
            "timestamp_ms": message.created_at_ms,
            "correlation_id": message.correlation_id,
        });
        format!("id: {event_id}\nevent: {event_type}\ndata: {payload}\n")
    }

    #[must_use]
    pub fn connection(&self, connection_id: &str) -> Option<SseConnection> {
        self.connections
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(connection_id)
            .map(|entry| entry.connection.clone())
    }

    #[must_use]
    pub fn stats(&self) -> SseConnectionStats {
        let connections = self
            .connections
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let mut stats = SseConnectionStats {
            total_connections: connections.len(),
            heartbeat_interval_seconds: self.config.heartbeat_interval_seconds,
            ..SseConnectionStats::default()
        };
        for entry in connections.values() {
            if let Some(organization_id) = &entry.connection.organization_id {
                *stats
                    .by_organization
                    .entry(organization_id.clone())
                    .or_default() += 1;
            }
            if let Some(user_id) = &entry.connection.user_id {
                *stats.by_user.entry(user_id.clone()).or_default() += 1;
            }
        }
        stats
    }

    fn matching_ids(&self, message: &PushMessage) -> Vec<String> {
        let connections = self
            .connections
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        connections
            .iter()
            .filter(|(_, entry)| {
                let target = &message.target;
                if !target.connection_ids.is_empty() {
                    return target.connection_ids.contains(&entry.connection.id);
                }
                if let Some(organization_id) = &target.organization_id
                    && entry.connection.organization_id.as_ref() == Some(organization_id)
                {
                    return true;
                }
                if let Some(user_id) = &target.user_id
                    && entry.connection.user_id.as_ref() == Some(user_id)
                {
                    return true;
                }
                !target.has_targets()
            })
            .map(|(id, _)| id.clone())
            .collect()
    }
}

#[async_trait]
impl PushAdapter for SseAdapter {
    fn channel(&self) -> PushChannel {
        PushChannel::Sse
    }

    async fn start(&self) -> Result<(), PushError> {
        if self.running.swap(true, Ordering::AcqRel) {
            return Ok(());
        }
        let running = self.running.clone();
        let connections = self.connections.clone();
        let heartbeat_interval = Duration::from_secs(self.config.heartbeat_interval_seconds);
        let stale_timeout_ms = self.config.stale_timeout_seconds.saturating_mul(1_000);
        let task = tokio::spawn(async move {
            while running.load(Ordering::Acquire) {
                tokio::time::sleep(heartbeat_interval).await;
                if !running.load(Ordering::Acquire) {
                    break;
                }
                let now_ms = unix_time_ms();
                connections
                    .lock()
                    .unwrap_or_else(std::sync::PoisonError::into_inner)
                    .retain(|_, entry| {
                        now_ms.saturating_sub(entry.connection.last_activity_ms) <= stale_timeout_ms
                    });
            }
        });
        *self
            .heartbeat_task
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = Some(task);
        Ok(())
    }

    async fn stop(&self) -> Result<(), PushError> {
        self.running.store(false, Ordering::Release);
        if let Some(task) = self
            .heartbeat_task
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .take()
        {
            task.abort();
        }
        self.connections
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clear();
        Ok(())
    }

    async fn send(&self, message: &PushMessage, now_ms: u64) -> Result<PushResult, PushError> {
        if !self.running.load(Ordering::Acquire) {
            return Err(PushError::ProviderUnavailable(
                "SSE adapter is not running".into(),
            ));
        }
        let matching = self.matching_ids(message);
        if matching.is_empty() {
            let mut result = PushResult::delivered(&message.id, PushChannel::Sse, now_ms);
            result.metadata.insert("connections".into(), Value::from(0));
            result.metadata.insert(
                "skipped".into(),
                Value::String("No matching connections".into()),
            );
            return Ok(result);
        }
        let event = self.build_event(message);
        let senders: Vec<_> = {
            let connections = self
                .connections
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            matching
                .iter()
                .filter_map(|id| {
                    connections
                        .get(id)
                        .map(|entry| (id.clone(), entry.sender.clone()))
                })
                .collect()
        };
        let mut sent = Vec::new();
        for (id, sender) in senders {
            if tokio::time::timeout(
                Duration::from_millis(self.config.send_timeout_ms),
                sender.send(event.clone()),
            )
            .await
            .is_ok_and(|result| result.is_ok())
            {
                sent.push(id);
            }
        }
        {
            let mut connections = self
                .connections
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            for id in &sent {
                if let Some(entry) = connections.get_mut(id) {
                    entry.connection.last_activity_ms = now_ms;
                    entry.connection.last_event_id = Some(message.id.clone());
                }
            }
        }
        let mut result = if sent.is_empty() {
            PushResult::failure(
                &message.id,
                PushChannel::Sse,
                PushStatus::Failed,
                "CONNECTION_SEND_FAILED",
                "No matching SSE connection accepted the event",
                now_ms,
            )
        } else {
            PushResult::delivered(&message.id, PushChannel::Sse, now_ms)
        };
        result
            .metadata
            .insert("connections_sent".into(), Value::from(sent.len()));
        result
            .metadata
            .insert("connections_matched".into(), Value::from(matching.len()));
        Ok(result)
    }

    async fn health(&self, now_ms: u64) -> PushAdapterHealth {
        let running = self.running.load(Ordering::Acquire);
        PushAdapterHealth {
            channel: PushChannel::Sse,
            status: if running {
                PushHealthStatus::Healthy
            } else {
                PushHealthStatus::Stopped
            },
            detail: self
                .last_error
                .read()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .clone(),
            checked_at_ms: now_ms,
        }
    }
}

fn unix_time_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |duration| {
            u64::try_from(duration.as_millis()).unwrap_or(u64::MAX)
        })
}
