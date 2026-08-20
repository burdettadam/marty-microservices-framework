use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::DataError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CacheBackend {
    Memory,
    Redis,
    Memcached,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CachePattern {
    CacheAside,
    WriteThrough,
    WriteBehind,
    RefreshAhead,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SerializationFormat {
    Json,
    String,
    Bytes,
    /// Read compatibility only. Native MMF never decodes executable pickle.
    Pickle,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct CacheConfig {
    pub backend: CacheBackend,
    pub host: String,
    pub port: u16,
    pub url: Option<String>,
    pub database: u32,
    pub secret_reference: Option<String>,
    pub max_connections: usize,
    pub default_ttl_seconds: u64,
    pub serialization: SerializationFormat,
    pub compression_enabled: bool,
    pub key_prefix: String,
    pub namespace: String,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            backend: CacheBackend::Memory,
            host: "localhost".into(),
            port: 6_379,
            url: None,
            database: 0,
            secret_reference: None,
            max_connections: 100,
            default_ttl_seconds: 3_600,
            serialization: SerializationFormat::Json,
            compression_enabled: true,
            key_prefix: String::new(),
            namespace: "default".into(),
        }
    }
}

impl CacheConfig {
    pub fn validate(&self, production: bool) -> Result<(), DataError> {
        if self.namespace.trim().is_empty() || self.max_connections == 0 {
            return Err(DataError::InvalidConfiguration(
                "cache namespace and positive connection limit are required".into(),
            ));
        }
        if self.serialization == SerializationFormat::Pickle {
            return Err(DataError::InvalidConfiguration(
                "native MMF does not deserialize executable pickle".into(),
            ));
        }
        if production && self.backend != CacheBackend::Memory {
            let url = self.url.as_deref().ok_or_else(|| {
                DataError::ProviderUnavailable("production cache URL is required".into())
            })?;
            if !url.starts_with("rediss://") && self.backend == CacheBackend::Redis {
                return Err(DataError::InvalidConfiguration(
                    "production Redis requires TLS".into(),
                ));
            }
        }
        Ok(())
    }

    #[must_use]
    pub fn key(&self, key: &str) -> String {
        if self.key_prefix.is_empty() {
            format!("{}:{key}", self.namespace)
        } else {
            format!("{}:{}:{key}", self.namespace, self.key_prefix)
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct CacheStats {
    pub hits: u64,
    pub misses: u64,
    pub sets: u64,
    pub deletes: u64,
    pub errors: u64,
    pub total_size: u64,
}

impl CacheStats {
    #[must_use]
    pub fn hit_rate(&self) -> f64 {
        let total = self.hits.saturating_add(self.misses);
        if total == 0 {
            0.0
        } else {
            #[allow(clippy::cast_precision_loss)]
            let hits = self.hits as f64;
            #[allow(clippy::cast_precision_loss)]
            let total = total as f64;
            hits / total
        }
    }
}

pub struct CacheSerializer {
    format: SerializationFormat,
}

impl CacheSerializer {
    pub fn new(format: SerializationFormat) -> Result<Self, DataError> {
        if format == SerializationFormat::Pickle {
            return Err(DataError::InvalidConfiguration(
                "pickle is not a supported native serialization format".into(),
            ));
        }
        Ok(Self { format })
    }

    pub fn serialize(&self, value: &Value) -> Result<Vec<u8>, DataError> {
        match self.format {
            SerializationFormat::Json => serde_json::to_vec(value)
                .map_err(|error| DataError::Serialization(error.to_string())),
            SerializationFormat::String => value
                .as_str()
                .map(|value| value.as_bytes().to_vec())
                .ok_or_else(|| DataError::Serialization("string value required".into())),
            SerializationFormat::Bytes => value
                .as_array()
                .ok_or_else(|| DataError::Serialization("byte array required".into()))?
                .iter()
                .map(|item| {
                    item.as_u64()
                        .and_then(|byte| u8::try_from(byte).ok())
                        .ok_or_else(|| DataError::Serialization("invalid byte".into()))
                })
                .collect(),
            SerializationFormat::Pickle => Err(DataError::Serialization(
                "pickle is never decoded by native MMF".into(),
            )),
        }
    }

    pub fn deserialize(&self, data: &[u8]) -> Result<Value, DataError> {
        match self.format {
            SerializationFormat::Json => serde_json::from_slice(data)
                .map_err(|error| DataError::Serialization(error.to_string())),
            SerializationFormat::String => String::from_utf8(data.to_vec())
                .map(Value::String)
                .map_err(|error| DataError::Serialization(error.to_string())),
            SerializationFormat::Bytes => Ok(Value::Array(
                data.iter().map(|byte| Value::from(*byte)).collect(),
            )),
            SerializationFormat::Pickle => Err(DataError::Serialization(
                "pickle is never decoded by native MMF".into(),
            )),
        }
    }
}

#[async_trait]
pub trait CacheStore: Send + Sync {
    async fn get(&self, key: &str, now_ms: u64) -> Result<Option<Vec<u8>>, DataError>;
    async fn set(
        &self,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        now_ms: u64,
    ) -> Result<bool, DataError>;
    async fn delete(&self, key: &str) -> Result<bool, DataError>;
    async fn exists(&self, key: &str, now_ms: u64) -> Result<bool, DataError>;
    async fn clear(&self) -> Result<(), DataError>;
    async fn stats(&self) -> Result<CacheStats, DataError>;
    async fn zadd(&self, key: &str, members: BTreeMap<Vec<u8>, f64>) -> Result<usize, DataError>;
    async fn zrevrangebyscore(
        &self,
        key: &str,
        max_score: f64,
        min_score: f64,
        start: usize,
        limit: Option<usize>,
    ) -> Result<Vec<Vec<u8>>, DataError>;
    async fn zcount(&self, key: &str, min_score: f64, max_score: f64) -> Result<usize, DataError>;
    async fn zremrangebyscore(
        &self,
        key: &str,
        min_score: f64,
        max_score: f64,
    ) -> Result<usize, DataError>;
    async fn zcard(&self, key: &str) -> Result<usize, DataError>;
    async fn zremrangebyrank(
        &self,
        key: &str,
        min_rank: usize,
        max_rank: usize,
    ) -> Result<usize, DataError>;
    async fn expire(&self, key: &str, ttl_seconds: u64, now_ms: u64) -> Result<bool, DataError>;
    async fn keys(&self, pattern: &str, now_ms: u64) -> Result<Vec<String>, DataError>;
}

#[derive(Clone, Debug)]
struct Entry {
    value: Vec<u8>,
    expires_at_ms: Option<u64>,
}

#[derive(Default)]
struct MemoryState {
    entries: BTreeMap<String, Entry>,
    sorted_sets: BTreeMap<String, BTreeMap<Vec<u8>, f64>>,
    stats: CacheStats,
}

#[derive(Clone, Default)]
pub struct MemoryCache {
    state: Arc<Mutex<MemoryState>>,
}

impl MemoryCache {
    fn purge(state: &mut MemoryState, key: &str, now_ms: u64) {
        if state
            .entries
            .get(key)
            .and_then(|entry| entry.expires_at_ms)
            .is_some_and(|expires| expires <= now_ms)
            && let Some(entry) = state.entries.remove(key)
        {
            state.stats.total_size = state
                .stats
                .total_size
                .saturating_sub(entry.value.len() as u64);
        }
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, MemoryState> {
        self.state
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }
}

#[async_trait]
impl CacheStore for MemoryCache {
    async fn get(&self, key: &str, now_ms: u64) -> Result<Option<Vec<u8>>, DataError> {
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        let value = state.entries.get(key).map(|entry| entry.value.clone());
        if value.is_some() {
            state.stats.hits = state.stats.hits.saturating_add(1);
        } else {
            state.stats.misses = state.stats.misses.saturating_add(1);
        }
        Ok(value)
    }

    async fn set(
        &self,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        now_ms: u64,
    ) -> Result<bool, DataError> {
        if key.is_empty() {
            return Err(DataError::InvalidQuery("cache key is required".into()));
        }
        let expires_at_ms = ttl_seconds.map(|ttl| now_ms.saturating_add(ttl.saturating_mul(1_000)));
        let mut state = self.lock();
        if let Some(previous) = state.entries.insert(
            key.into(),
            Entry {
                value: value.clone(),
                expires_at_ms,
            },
        ) {
            state.stats.total_size = state
                .stats
                .total_size
                .saturating_sub(previous.value.len() as u64);
        }
        state.stats.total_size = state.stats.total_size.saturating_add(value.len() as u64);
        state.stats.sets = state.stats.sets.saturating_add(1);
        Ok(true)
    }

    async fn delete(&self, key: &str) -> Result<bool, DataError> {
        let mut state = self.lock();
        let removed = state.entries.remove(key);
        if let Some(entry) = &removed {
            state.stats.total_size = state
                .stats
                .total_size
                .saturating_sub(entry.value.len() as u64);
            state.stats.deletes = state.stats.deletes.saturating_add(1);
        }
        state.sorted_sets.remove(key);
        Ok(removed.is_some())
    }

    async fn exists(&self, key: &str, now_ms: u64) -> Result<bool, DataError> {
        let mut state = self.lock();
        Self::purge(&mut state, key, now_ms);
        Ok(state.entries.contains_key(key) || state.sorted_sets.contains_key(key))
    }

    async fn clear(&self) -> Result<(), DataError> {
        let mut state = self.lock();
        state.entries.clear();
        state.sorted_sets.clear();
        state.stats.total_size = 0;
        Ok(())
    }

    async fn stats(&self) -> Result<CacheStats, DataError> {
        Ok(self.lock().stats.clone())
    }

    async fn zadd(&self, key: &str, members: BTreeMap<Vec<u8>, f64>) -> Result<usize, DataError> {
        if members.values().any(|score| !score.is_finite()) {
            return Err(DataError::InvalidQuery(
                "sorted-set score must be finite".into(),
            ));
        }
        let mut state = self.lock();
        let set = state.sorted_sets.entry(key.into()).or_default();
        let mut added = 0;
        for (member, score) in members {
            added += usize::from(set.insert(member, score).is_none());
        }
        Ok(added)
    }

    async fn zrevrangebyscore(
        &self,
        key: &str,
        max_score: f64,
        min_score: f64,
        start: usize,
        limit: Option<usize>,
    ) -> Result<Vec<Vec<u8>>, DataError> {
        validate_range(min_score, max_score)?;
        let state = self.lock();
        let mut values = state
            .sorted_sets
            .get(key)
            .into_iter()
            .flat_map(|set| set.iter())
            .filter(|(_, score)| **score >= min_score && **score <= max_score)
            .map(|(member, score)| (member.clone(), *score))
            .collect::<Vec<_>>();
        values.sort_by(|left, right| {
            right
                .1
                .total_cmp(&left.1)
                .then_with(|| left.0.cmp(&right.0))
        });
        Ok(values
            .into_iter()
            .skip(start)
            .take(limit.unwrap_or(usize::MAX))
            .map(|(member, _)| member)
            .collect())
    }

    async fn zcount(&self, key: &str, min_score: f64, max_score: f64) -> Result<usize, DataError> {
        validate_range(min_score, max_score)?;
        Ok(self.lock().sorted_sets.get(key).map_or(0, |set| {
            set.values()
                .filter(|score| **score >= min_score && **score <= max_score)
                .count()
        }))
    }

    async fn zremrangebyscore(
        &self,
        key: &str,
        min_score: f64,
        max_score: f64,
    ) -> Result<usize, DataError> {
        validate_range(min_score, max_score)?;
        let mut state = self.lock();
        let Some(set) = state.sorted_sets.get_mut(key) else {
            return Ok(0);
        };
        let before = set.len();
        set.retain(|_, score| *score < min_score || *score > max_score);
        Ok(before - set.len())
    }

    async fn zcard(&self, key: &str) -> Result<usize, DataError> {
        Ok(self.lock().sorted_sets.get(key).map_or(0, BTreeMap::len))
    }

    async fn zremrangebyrank(
        &self,
        key: &str,
        min_rank: usize,
        max_rank: usize,
    ) -> Result<usize, DataError> {
        if min_rank > max_rank {
            return Err(DataError::InvalidQuery(
                "invalid sorted-set rank range".into(),
            ));
        }
        let mut state = self.lock();
        let Some(set) = state.sorted_sets.get_mut(key) else {
            return Ok(0);
        };
        let mut ranked = set
            .iter()
            .map(|(member, score)| (member.clone(), *score))
            .collect::<Vec<_>>();
        ranked.sort_by(|left, right| {
            left.1
                .total_cmp(&right.1)
                .then_with(|| left.0.cmp(&right.0))
        });
        let members = ranked
            .into_iter()
            .skip(min_rank)
            .take(max_rank.saturating_sub(min_rank).saturating_add(1))
            .map(|(member, _)| member)
            .collect::<Vec<_>>();
        for member in &members {
            set.remove(member);
        }
        Ok(members.len())
    }

    async fn expire(&self, key: &str, ttl_seconds: u64, now_ms: u64) -> Result<bool, DataError> {
        let mut state = self.lock();
        let Some(entry) = state.entries.get_mut(key) else {
            return Ok(false);
        };
        entry.expires_at_ms = Some(now_ms.saturating_add(ttl_seconds.saturating_mul(1_000)));
        Ok(true)
    }

    async fn keys(&self, pattern: &str, now_ms: u64) -> Result<Vec<String>, DataError> {
        let mut state = self.lock();
        let keys = state.entries.keys().cloned().collect::<Vec<_>>();
        for key in &keys {
            Self::purge(&mut state, key, now_ms);
        }
        Ok(state
            .entries
            .keys()
            .chain(state.sorted_sets.keys())
            .filter(|key| glob_matches(pattern, key))
            .cloned()
            .collect())
    }
}

fn validate_range(minimum: f64, maximum: f64) -> Result<(), DataError> {
    if !minimum.is_finite() || !maximum.is_finite() || minimum > maximum {
        return Err(DataError::InvalidQuery(
            "invalid sorted-set score range".into(),
        ));
    }
    Ok(())
}

fn glob_matches(pattern: &str, value: &str) -> bool {
    if pattern == "*" {
        return true;
    }
    let segments = pattern.split('*').collect::<Vec<_>>();
    let mut remainder = value;
    for (index, segment) in segments.iter().enumerate() {
        if segment.is_empty() {
            continue;
        }
        let Some(position) = remainder.find(segment) else {
            return false;
        };
        if index == 0 && !pattern.starts_with('*') && position != 0 {
            return false;
        }
        remainder = &remainder[position + segment.len()..];
    }
    pattern.ends_with('*') || remainder.is_empty()
}
