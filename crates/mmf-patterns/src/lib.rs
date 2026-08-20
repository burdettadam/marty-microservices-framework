//! Canonical reusable consistency patterns for MMF.
//!
//! Delivery/outbox logic stays in `mmf-messaging`, read-model storage stays in
//! `mmf-data`, and saga state stays in `mmf-workflow`. This crate composes those
//! owners instead of creating parallel implementations.

#![forbid(unsafe_code)]

mod cqrs;
mod event_sourcing;
mod transactions;

use std::collections::BTreeSet;

use async_trait::async_trait;
pub use cqrs::*;
pub use event_sourcing::*;
pub use mmf_data::{Filter, InMemoryReadModelStore, ReadModelQuery, ReadModelStore, SortOrder};
pub use mmf_messaging::{DeadLetter, Message, MessageStatus, OutboxEntry};
pub use mmf_workflow::{
    SagaDefinition, SagaStepDefinition, WorkflowDefinition, WorkflowExecution, WorkflowStatus,
};
pub use transactions::*;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ConsistencyLevel {
    Eventual,
    Strong,
    BoundedStaleness,
    Session,
    ConsistentPrefix,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PersistenceMode {
    InMemory,
    Database,
    DistributedCache,
    Hybrid,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct ConsistencyPolicy {
    pub level: ConsistencyLevel,
    pub read_quorum: u32,
    pub write_quorum: u32,
    pub replication_factor: u32,
    pub maximum_staleness_ms: u64,
    pub conflict_resolution: ConflictResolution,
}

impl Default for ConsistencyPolicy {
    fn default() -> Self {
        Self {
            level: ConsistencyLevel::Eventual,
            read_quorum: 1,
            write_quorum: 1,
            replication_factor: 1,
            maximum_staleness_ms: 5_000,
            conflict_resolution: ConflictResolution::LastWriteWins,
        }
    }
}

impl ConsistencyPolicy {
    pub fn validate(&self) -> Result<(), PatternError> {
        if self.replication_factor == 0
            || self.read_quorum == 0
            || self.write_quorum == 0
            || self.read_quorum > self.replication_factor
            || self.write_quorum > self.replication_factor
        {
            return Err(PatternError::InvalidConfiguration(
                "consistency quorums must be positive and no larger than replication".to_owned(),
            ));
        }
        if self.level == ConsistencyLevel::Strong
            && self.read_quorum.saturating_add(self.write_quorum) <= self.replication_factor
        {
            return Err(PatternError::InvalidConfiguration(
                "strong consistency requires intersecting read and write quorums".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ConflictResolution {
    LastWriteWins,
    VectorClock,
    Merge,
    Reject,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ReplicaRecord {
    pub node_id: String,
    pub key: String,
    pub version: u64,
    pub updated_at_ms: u64,
    pub checksum: String,
    pub value: Value,
}

impl ReplicaRecord {
    pub fn validate(&self) -> Result<(), PatternError> {
        if self.node_id.trim().is_empty()
            || self.key.trim().is_empty()
            || self.version == 0
            || self.checksum.trim().is_empty()
        {
            return Err(PatternError::InvalidConfiguration(
                "replica records require node, key, version, and checksum".to_owned(),
            ));
        }
        Ok(())
    }
}

#[async_trait]
pub trait ConsistencyProvider: Send + Sync {
    async fn read_replicas(&self, key: &str) -> Result<Vec<ReplicaRecord>, PatternError>;
    async fn write_replicas(
        &self,
        key: &str,
        value: &Value,
        version: u64,
    ) -> Result<BTreeSet<String>, PatternError>;
    async fn delete_replicas(&self, key: &str) -> Result<BTreeSet<String>, PatternError>;
    async fn repair_replica(
        &self,
        node_id: &str,
        authoritative: &ReplicaRecord,
    ) -> Result<(), PatternError>;
}

#[derive(Clone, Debug)]
pub struct ConsistencyCoordinator {
    pub policy: ConsistencyPolicy,
}

impl ConsistencyCoordinator {
    pub fn new(policy: ConsistencyPolicy) -> Result<Self, PatternError> {
        policy.validate()?;
        Ok(Self { policy })
    }

    pub async fn read(
        &self,
        provider: &dyn ConsistencyProvider,
        key: &str,
        now_ms: u64,
    ) -> Result<Option<ReplicaRecord>, PatternError> {
        if key.trim().is_empty() {
            return Err(PatternError::InvalidConfiguration(
                "consistency reads require a key".to_owned(),
            ));
        }
        let mut replicas = provider.read_replicas(key).await?;
        for replica in &replicas {
            replica.validate()?;
        }
        if replicas.is_empty() {
            return Ok(None);
        }
        if matches!(
            self.policy.level,
            ConsistencyLevel::Strong | ConsistencyLevel::Session
        ) && replicas.len() < usize::try_from(self.policy.read_quorum).unwrap_or(usize::MAX)
        {
            return Err(PatternError::Operation(
                "read quorum was not reached".to_owned(),
            ));
        }
        replicas.sort_by_key(|record| (record.version, record.updated_at_ms));
        let Some(authoritative) = replicas.last().cloned() else {
            return Ok(None);
        };
        if self.policy.level == ConsistencyLevel::BoundedStaleness
            && now_ms.saturating_sub(authoritative.updated_at_ms) > self.policy.maximum_staleness_ms
        {
            return Err(PatternError::Operation(
                "replica exceeds bounded-staleness policy".to_owned(),
            ));
        }
        if self.policy.conflict_resolution == ConflictResolution::Reject
            && replicas
                .iter()
                .filter(|record| record.version == authoritative.version)
                .any(|record| record.checksum != authoritative.checksum)
        {
            return Err(PatternError::Operation(
                "replica conflict requires explicit resolution".to_owned(),
            ));
        }
        Ok(Some(authoritative))
    }

    pub async fn write(
        &self,
        provider: &dyn ConsistencyProvider,
        key: &str,
        value: &Value,
        version: u64,
    ) -> Result<(), PatternError> {
        if key.trim().is_empty() || version == 0 {
            return Err(PatternError::InvalidConfiguration(
                "consistency writes require a key and positive version".to_owned(),
            ));
        }
        let acknowledgements = provider.write_replicas(key, value, version).await?;
        if acknowledgements.len() < usize::try_from(self.policy.write_quorum).unwrap_or(usize::MAX)
        {
            return Err(PatternError::Operation(
                "write quorum was not reached".to_owned(),
            ));
        }
        Ok(())
    }

    pub async fn delete(
        &self,
        provider: &dyn ConsistencyProvider,
        key: &str,
    ) -> Result<(), PatternError> {
        if key.trim().is_empty() {
            return Err(PatternError::InvalidConfiguration(
                "consistency deletes require a key".to_owned(),
            ));
        }
        let acknowledgements = provider.delete_replicas(key).await?;
        if acknowledgements.len() < usize::try_from(self.policy.write_quorum).unwrap_or(usize::MAX)
        {
            return Err(PatternError::Operation(
                "delete quorum was not reached".to_owned(),
            ));
        }
        Ok(())
    }

    pub async fn repair(
        &self,
        provider: &dyn ConsistencyProvider,
        records: &[ReplicaRecord],
    ) -> Result<usize, PatternError> {
        let authoritative = records
            .iter()
            .max_by_key(|record| (record.version, record.updated_at_ms))
            .ok_or_else(|| {
                PatternError::InvalidConfiguration("repair requires replicas".to_owned())
            })?;
        authoritative.validate()?;
        let mut repaired = 0;
        for record in records {
            if record.checksum != authoritative.checksum || record.version != authoritative.version
            {
                provider
                    .repair_replica(&record.node_id, authoritative)
                    .await?;
                repaired += 1;
            }
        }
        Ok(repaired)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DataConsistencyConfig {
    pub service_name: String,
    pub service_version: String,
    pub environment: String,
    pub persistence: PersistenceMode,
    pub policy: ConsistencyPolicy,
    pub transaction_timeout_ms: u64,
    pub event_stream_page_size: usize,
    pub snapshot_frequency: u64,
    pub command_idempotency_window_ms: u64,
    pub projection_checkpoint_frequency: u64,
    pub encryption_in_transit: bool,
}

impl DataConsistencyConfig {
    pub fn validate(&self) -> Result<(), PatternError> {
        self.policy.validate()?;
        if self.service_name.trim().is_empty()
            || self.service_version.trim().is_empty()
            || self.transaction_timeout_ms == 0
            || self.event_stream_page_size == 0
            || self.command_idempotency_window_ms == 0
            || self.projection_checkpoint_frequency == 0
        {
            return Err(PatternError::InvalidConfiguration(
                "data-consistency configuration contains an empty or zero required value"
                    .to_owned(),
            ));
        }
        if self.environment.eq_ignore_ascii_case("production") && !self.encryption_in_transit {
            return Err(PatternError::InvalidConfiguration(
                "production consistency transports require encryption".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Debug, Error)]
pub enum PatternError {
    #[error("invalid pattern configuration: {0}")]
    InvalidConfiguration(String),
    #[error(
        "optimistic concurrency conflict for stream {stream_id}: expected {expected}, actual {actual}"
    )]
    Concurrency {
        stream_id: String,
        expected: u64,
        actual: u64,
    },
    #[error("duplicate operation: {0}")]
    Duplicate(String),
    #[error("handler unavailable: {0}")]
    HandlerUnavailable(String),
    #[error("operation failed: {0}")]
    Operation(String),
    #[error("transaction transition from {from:?} to {to:?} is invalid")]
    InvalidTransactionTransition {
        from: TransactionState,
        to: TransactionState,
    },
}
