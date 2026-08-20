use std::collections::BTreeMap;
use std::sync::Mutex;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::PatternError;

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct DomainEvent {
    pub event_id: String,
    pub aggregate_id: String,
    pub aggregate_type: String,
    pub event_type: String,
    pub version: u64,
    pub occurred_at_ms: u64,
    #[serde(default)]
    pub data: Value,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

impl DomainEvent {
    pub fn validate(&self) -> Result<(), PatternError> {
        if self.event_id.trim().is_empty()
            || self.aggregate_id.trim().is_empty()
            || self.aggregate_type.trim().is_empty()
            || self.event_type.trim().is_empty()
            || self.version == 0
        {
            return Err(PatternError::InvalidConfiguration(
                "domain event requires IDs, types, and a positive version".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct EventStream {
    pub stream_id: String,
    pub events: Vec<DomainEvent>,
    pub version: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Snapshot {
    pub aggregate_id: String,
    pub aggregate_type: String,
    pub version: u64,
    pub created_at_ms: u64,
    pub data: Value,
}

#[async_trait]
pub trait EventStore: Send + Sync {
    async fn append(
        &self,
        stream_id: &str,
        expected_version: u64,
        events: Vec<DomainEvent>,
    ) -> Result<u64, PatternError>;
    async fn load(
        &self,
        stream_id: &str,
        from_version: u64,
        limit: Option<usize>,
    ) -> Result<EventStream, PatternError>;
}

#[derive(Debug, Default)]
pub struct InMemoryEventStore {
    streams: Mutex<BTreeMap<String, Vec<DomainEvent>>>,
}

#[async_trait]
impl EventStore for InMemoryEventStore {
    async fn append(
        &self,
        stream_id: &str,
        expected_version: u64,
        events: Vec<DomainEvent>,
    ) -> Result<u64, PatternError> {
        if stream_id.trim().is_empty() || events.is_empty() {
            return Err(PatternError::InvalidConfiguration(
                "event append requires a stream and events".to_owned(),
            ));
        }
        for event in &events {
            event.validate()?;
        }
        let mut streams = self
            .streams
            .lock()
            .map_err(|_| PatternError::Operation("event store poisoned".to_owned()))?;
        let stream = streams.entry(stream_id.to_owned()).or_default();
        let actual = stream.len() as u64;
        if actual != expected_version {
            return Err(PatternError::Concurrency {
                stream_id: stream_id.to_owned(),
                expected: expected_version,
                actual,
            });
        }
        for (offset, event) in events.iter().enumerate() {
            let expected_event_version = actual + offset as u64 + 1;
            if event.version != expected_event_version {
                return Err(PatternError::InvalidConfiguration(format!(
                    "event '{}' has version {}, expected {expected_event_version}",
                    event.event_id, event.version
                )));
            }
        }
        stream.extend(events);
        Ok(stream.len() as u64)
    }

    async fn load(
        &self,
        stream_id: &str,
        from_version: u64,
        limit: Option<usize>,
    ) -> Result<EventStream, PatternError> {
        let streams = self
            .streams
            .lock()
            .map_err(|_| PatternError::Operation("event store poisoned".to_owned()))?;
        let all = streams.get(stream_id).cloned().unwrap_or_default();
        let events = all
            .iter()
            .filter(|event| event.version >= from_version.max(1))
            .take(limit.unwrap_or(usize::MAX))
            .cloned()
            .collect();
        Ok(EventStream {
            stream_id: stream_id.to_owned(),
            events,
            version: all.len() as u64,
        })
    }
}

#[async_trait]
pub trait SnapshotStore: Send + Sync {
    async fn save(&self, snapshot: Snapshot) -> Result<(), PatternError>;
    async fn load(&self, aggregate_id: &str) -> Result<Option<Snapshot>, PatternError>;
    async fn delete(&self, aggregate_id: &str) -> Result<bool, PatternError>;
}

#[derive(Debug, Default)]
pub struct InMemorySnapshotStore {
    snapshots: Mutex<BTreeMap<String, Snapshot>>,
}

#[async_trait]
impl SnapshotStore for InMemorySnapshotStore {
    async fn save(&self, snapshot: Snapshot) -> Result<(), PatternError> {
        if snapshot.aggregate_id.trim().is_empty()
            || snapshot.aggregate_type.trim().is_empty()
            || snapshot.version == 0
        {
            return Err(PatternError::InvalidConfiguration(
                "snapshot requires an aggregate and positive version".to_owned(),
            ));
        }
        self.snapshots
            .lock()
            .map_err(|_| PatternError::Operation("snapshot store poisoned".to_owned()))?
            .insert(snapshot.aggregate_id.clone(), snapshot);
        Ok(())
    }

    async fn load(&self, aggregate_id: &str) -> Result<Option<Snapshot>, PatternError> {
        Ok(self
            .snapshots
            .lock()
            .map_err(|_| PatternError::Operation("snapshot store poisoned".to_owned()))?
            .get(aggregate_id)
            .cloned())
    }

    async fn delete(&self, aggregate_id: &str) -> Result<bool, PatternError> {
        Ok(self
            .snapshots
            .lock()
            .map_err(|_| PatternError::Operation("snapshot store poisoned".to_owned()))?
            .remove(aggregate_id)
            .is_some())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AggregateDocument {
    pub aggregate_id: String,
    pub aggregate_type: String,
    pub version: u64,
    pub state: Value,
    #[serde(default)]
    pub uncommitted_events: Vec<DomainEvent>,
}

impl AggregateDocument {
    #[must_use]
    pub fn new(aggregate_id: impl Into<String>, aggregate_type: impl Into<String>) -> Self {
        Self {
            aggregate_id: aggregate_id.into(),
            aggregate_type: aggregate_type.into(),
            version: 0,
            state: Value::Object(serde_json::Map::new()),
            uncommitted_events: Vec::new(),
        }
    }

    pub fn raise(
        &mut self,
        event_id: impl Into<String>,
        event_type: impl Into<String>,
        data: Value,
        occurred_at_ms: u64,
    ) -> Result<(), PatternError> {
        let event = DomainEvent {
            event_id: event_id.into(),
            aggregate_id: self.aggregate_id.clone(),
            aggregate_type: self.aggregate_type.clone(),
            event_type: event_type.into(),
            version: self.version + 1,
            occurred_at_ms,
            data,
            metadata: BTreeMap::new(),
        };
        event.validate()?;
        self.apply(&event)?;
        self.uncommitted_events.push(event);
        Ok(())
    }

    pub fn replay(&mut self, events: &[DomainEvent]) -> Result<(), PatternError> {
        for event in events {
            if event.aggregate_id != self.aggregate_id || event.version != self.version + 1 {
                return Err(PatternError::Concurrency {
                    stream_id: self.aggregate_id.clone(),
                    expected: self.version + 1,
                    actual: event.version,
                });
            }
            self.apply(event)?;
        }
        Ok(())
    }

    pub fn mark_committed(&mut self) {
        self.uncommitted_events.clear();
    }

    #[must_use]
    pub fn snapshot(&self, now_ms: u64) -> Snapshot {
        Snapshot {
            aggregate_id: self.aggregate_id.clone(),
            aggregate_type: self.aggregate_type.clone(),
            version: self.version,
            created_at_ms: now_ms,
            data: self.state.clone(),
        }
    }

    pub fn restore(&mut self, snapshot: &Snapshot) -> Result<(), PatternError> {
        if snapshot.aggregate_id != self.aggregate_id
            || snapshot.aggregate_type != self.aggregate_type
        {
            return Err(PatternError::InvalidConfiguration(
                "snapshot aggregate does not match".to_owned(),
            ));
        }
        self.version = snapshot.version;
        self.state = snapshot.data.clone();
        self.uncommitted_events.clear();
        Ok(())
    }

    fn apply(&mut self, event: &DomainEvent) -> Result<(), PatternError> {
        let state = self.state.as_object_mut().ok_or_else(|| {
            PatternError::InvalidConfiguration("aggregate state must be an object".to_owned())
        })?;
        let changes = event.data.as_object().ok_or_else(|| {
            PatternError::InvalidConfiguration("event data must be an object".to_owned())
        })?;
        state.extend(changes.clone());
        self.version = event.version;
        Ok(())
    }
}

#[async_trait]
pub trait Projection: Send + Sync {
    fn name(&self) -> &str;
    async fn apply(&self, event: &DomainEvent) -> Result<(), PatternError>;
    async fn rebuild(&self, events: &[DomainEvent]) -> Result<(), PatternError>;
}

#[async_trait]
pub trait ProjectionCheckpointStore: Send + Sync {
    async fn load(&self, projection: &str) -> Result<u64, PatternError>;
    async fn save(&self, projection: &str, version: u64) -> Result<(), PatternError>;
}
