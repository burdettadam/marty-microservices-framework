//! Canonical provider-neutral machine-learning platform for MMF.

#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, RwLock};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use thiserror::Error;
use uuid::Uuid;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ModelType {
    Classification,
    Regression,
    Clustering,
    Recommendation,
    NaturalLanguage,
    ComputerVision,
    TimeSeries,
    DeepLearning,
    Ensemble,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ModelFramework {
    Sklearn,
    Tensorflow,
    Pytorch,
    Xgboost,
    Lightgbm,
    Keras,
    Onnx,
    Huggingface,
    Custom,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ModelStatus {
    #[default]
    Training,
    Validating,
    Ready,
    Deployed,
    Serving,
    Deprecated,
    Failed,
    Archived,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ExperimentStatus {
    #[default]
    Draft,
    Running,
    Paused,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FeatureType {
    Numerical,
    Categorical,
    Text,
    Datetime,
    Boolean,
    Embedding,
    Array,
    Json,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MlModel {
    pub model_id: String,
    pub name: String,
    pub version: String,
    pub model_type: ModelType,
    pub framework: ModelFramework,
    pub status: ModelStatus,
    pub model_path: Option<String>,
    #[serde(skip_serializing)]
    pub model_data: Option<Vec<u8>>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
    pub accuracy: Option<f64>,
    pub precision: Option<f64>,
    pub recall: Option<f64>,
    pub f1_score: Option<f64>,
    pub mse: Option<f64>,
    pub mae: Option<f64>,
    pub r2_score: Option<f64>,
    #[serde(default)]
    pub custom_metrics: BTreeMap<String, f64>,
    pub training_data_size: Option<u64>,
    pub training_duration: Option<f64>,
    #[serde(default)]
    pub hyperparameters: BTreeMap<String, Value>,
    pub endpoint_url: Option<String>,
    pub cpu_requirement: f64,
    pub memory_requirement_mb: u64,
    pub gpu_requirement: bool,
    pub created_at_ms: u64,
    pub updated_at_ms: u64,
    pub deployed_at_ms: Option<u64>,
}

impl MlModel {
    pub fn validate(&self) -> Result<(), MlError> {
        if self.model_id.trim().is_empty()
            || self.name.trim().is_empty()
            || self.version.trim().is_empty()
        {
            return Err(MlError::InvalidInput(
                "model id, name, and version are required".into(),
            ));
        }
        if !self.cpu_requirement.is_finite()
            || self.cpu_requirement <= 0.0
            || self.memory_requirement_mb == 0
        {
            return Err(MlError::InvalidInput(
                "model resource requirements must be positive".into(),
            ));
        }
        for metric in [self.accuracy, self.precision, self.recall, self.f1_score]
            .into_iter()
            .flatten()
        {
            if !metric.is_finite() || !(0.0..=1.0).contains(&metric) {
                return Err(MlError::InvalidInput(
                    "bounded model metrics must be between zero and one".into(),
                ));
            }
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Feature {
    pub feature_id: String,
    pub name: String,
    pub feature_type: FeatureType,
    pub description: String,
    pub source_table: Option<String>,
    pub source_column: Option<String>,
    pub transformation: Option<String>,
    pub min_value: Option<f64>,
    pub max_value: Option<f64>,
    pub allowed_values: Option<Vec<Value>>,
    pub required: bool,
    pub mean: Option<f64>,
    pub std: Option<f64>,
    pub null_count: Option<u64>,
    pub unique_count: Option<u64>,
    pub created_at_ms: u64,
    pub updated_at_ms: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct FeatureGroup {
    pub group_id: String,
    pub name: String,
    pub description: String,
    #[serde(default)]
    pub features: Vec<Feature>,
    pub online_enabled: bool,
    pub offline_enabled: bool,
    pub online_store: Option<String>,
    pub offline_store: Option<String>,
    pub update_frequency: String,
    pub created_at_ms: u64,
    pub updated_at_ms: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ModelPrediction {
    pub prediction_id: String,
    pub model_id: String,
    pub input_features: BTreeMap<String, Value>,
    pub prediction: Value,
    pub confidence: Option<f64>,
    pub probabilities: Option<BTreeMap<String, f64>>,
    pub latency_ms: Option<f64>,
    pub timestamp_ms: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AbTestExperiment {
    pub experiment_id: String,
    pub name: String,
    pub description: String,
    pub control_model_id: String,
    pub treatment_model_ids: Vec<String>,
    pub traffic_split: BTreeMap<String, f64>,
    pub primary_metric: String,
    pub status: ExperimentStatus,
    #[serde(default)]
    pub secondary_metrics: Vec<String>,
    pub min_sample_size: u64,
    pub max_duration_days: u64,
    pub significance_level: f64,
    pub power: f64,
    #[serde(default)]
    pub results: BTreeMap<String, Value>,
    pub winner_model_id: Option<String>,
    pub created_at_ms: u64,
    pub started_at_ms: Option<u64>,
    pub ended_at_ms: Option<u64>,
}

impl AbTestExperiment {
    pub fn validate(&self) -> Result<(), MlError> {
        let total: f64 = self.traffic_split.values().sum();
        if (total - 1.0).abs() > 1e-9 && (total - 100.0).abs() > 1e-9 {
            return Err(MlError::InvalidInput(
                "experiment traffic split must total 1 or 100".into(),
            ));
        }
        if self.min_sample_size == 0
            || self.max_duration_days == 0
            || !(0.0..1.0).contains(&self.significance_level)
            || !(0.0..=1.0).contains(&self.power)
        {
            return Err(MlError::InvalidInput(
                "invalid experiment statistical parameters".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ModelMetrics {
    pub model_id: String,
    pub timestamp_ms: u64,
    pub request_count: u64,
    pub success_count: u64,
    pub error_count: u64,
    pub avg_latency_ms: f64,
    pub p95_latency_ms: f64,
    pub p99_latency_ms: f64,
    pub cpu_usage: f64,
    pub memory_usage: f64,
    pub gpu_usage: f64,
    pub prediction_accuracy: Option<f64>,
    pub user_satisfaction: Option<f64>,
    pub revenue_impact: Option<f64>,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct FeatureStatistics {
    pub count: u64,
    pub unique_count: u64,
    pub null_count: u64,
    pub mean: Option<f64>,
    pub std: Option<f64>,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub median: Option<f64>,
    pub percentile_25: Option<f64>,
    pub percentile_75: Option<f64>,
}

#[derive(Clone, Debug, Eq, Error, PartialEq)]
pub enum MlError {
    #[error("invalid ML input: {0}")]
    InvalidInput(String),
    #[error("ML object not found: {0}")]
    NotFound(String),
    #[error("ML object already exists: {0}")]
    Conflict(String),
    #[error("ML provider unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("ML inference failed: {0}")]
    Inference(String),
}

#[derive(Clone, Debug)]
struct OfflineRecord {
    entity_id: String,
    timestamp_ms: u64,
    values: BTreeMap<String, Value>,
}

#[derive(Default)]
pub struct InMemoryFeatureStore {
    features: RwLock<BTreeMap<String, Feature>>,
    groups: RwLock<BTreeMap<String, FeatureGroup>>,
    online: RwLock<BTreeMap<String, BTreeMap<String, Value>>>,
    offline: RwLock<Vec<OfflineRecord>>,
}

impl InMemoryFeatureStore {
    pub fn register_feature(&self, feature: Feature) -> Result<(), MlError> {
        if feature.feature_id.trim().is_empty() || feature.name.trim().is_empty() {
            return Err(MlError::InvalidInput(
                "feature id and name are required".into(),
            ));
        }
        self.features
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert(feature.feature_id.clone(), feature);
        Ok(())
    }
    pub fn register_feature_group(&self, group: FeatureGroup) -> Result<(), MlError> {
        if group.group_id.trim().is_empty() {
            return Err(MlError::InvalidInput("feature group id is required".into()));
        }
        self.groups
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert(group.group_id.clone(), group);
        Ok(())
    }
    pub fn set_online_features(
        &self,
        entity_id: &str,
        features: BTreeMap<String, Value>,
    ) -> Result<(), MlError> {
        if entity_id.trim().is_empty() {
            return Err(MlError::InvalidInput("entity id is required".into()));
        }
        self.online
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .entry(entity_id.into())
            .or_default()
            .extend(features);
        Ok(())
    }
    #[must_use]
    pub fn online_features(&self, entity_id: &str, names: &[String]) -> BTreeMap<String, Value> {
        let online = self
            .online
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let values = online.get(entity_id);
        names
            .iter()
            .map(|name| {
                (
                    name.clone(),
                    values
                        .and_then(|v| v.get(name))
                        .cloned()
                        .unwrap_or(Value::Null),
                )
            })
            .collect()
    }
    pub fn add_offline_features(
        &self,
        entity_id: &str,
        values: BTreeMap<String, Value>,
        timestamp_ms: u64,
    ) -> Result<(), MlError> {
        if entity_id.trim().is_empty() {
            return Err(MlError::InvalidInput("entity id is required".into()));
        }
        self.offline
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(OfflineRecord {
                entity_id: entity_id.into(),
                timestamp_ms,
                values,
            });
        Ok(())
    }
    #[must_use]
    pub fn offline_features(
        &self,
        names: &[String],
        start_ms: Option<u64>,
        end_ms: Option<u64>,
    ) -> Vec<BTreeMap<String, Value>> {
        self.offline
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .iter()
            .filter(|r| {
                start_ms.is_none_or(|s| r.timestamp_ms >= s)
                    && end_ms.is_none_or(|e| r.timestamp_ms <= e)
            })
            .map(|r| {
                let mut out =
                    BTreeMap::from([("entity_id".into(), Value::String(r.entity_id.clone()))]);
                for name in names {
                    if let Some(value) = r.values.get(name) {
                        out.insert(name.clone(), value.clone());
                    }
                }
                out
            })
            .collect()
    }
    #[must_use]
    pub fn validate_features(
        &self,
        features: &BTreeMap<String, Value>,
    ) -> BTreeMap<String, Vec<String>> {
        let definitions = self
            .features
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let mut errors = BTreeMap::new();
        for (name, value) in features {
            let mut item = Vec::new();
            let Some(feature) = definitions
                .values()
                .find(|f| f.name == *name || f.feature_id == *name)
            else {
                errors.insert(name.clone(), vec!["Feature not registered".into()]);
                continue;
            };
            if feature.required && value.is_null() {
                item.push("Required feature is null".into());
            }
            if !value.is_null() {
                if feature.feature_type == FeatureType::Numerical && value.as_f64().is_none() {
                    item.push("Expected numerical value".into());
                }
                if let Some(number) = value.as_f64() {
                    if feature.min_value.is_some_and(|min| number < min) {
                        item.push(format!(
                            "Value below minimum: {}",
                            feature.min_value.unwrap_or_default()
                        ));
                    }
                    if feature.max_value.is_some_and(|max| number > max) {
                        item.push(format!(
                            "Value above maximum: {}",
                            feature.max_value.unwrap_or_default()
                        ));
                    }
                }
                if feature
                    .allowed_values
                    .as_ref()
                    .is_some_and(|allowed| !allowed.contains(value))
                {
                    item.push(format!(
                        "Value not in allowed list: {:?}",
                        feature.allowed_values.as_ref().unwrap_or(&Vec::new())
                    ));
                }
            }
            if !item.is_empty() {
                errors.insert(name.clone(), item);
            }
        }
        errors
    }
    #[must_use]
    pub fn feature_statistics(&self, name: &str) -> FeatureStatistics {
        let mut values = Vec::new();
        for record in self
            .online
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .values()
        {
            if let Some(value) = record.get(name)
                && !value.is_null()
            {
                values.push(value.clone());
            }
        }
        for record in self
            .offline
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .iter()
        {
            if let Some(value) = record.values.get(name)
                && !value.is_null()
            {
                values.push(value.clone());
            }
        }
        feature_statistics(&values)
    }
}

#[derive(Default)]
pub struct InMemoryModelRegistry {
    models: RwLock<BTreeMap<String, MlModel>>,
    aliases: RwLock<BTreeMap<(String, String), String>>,
    lineage: RwLock<BTreeMap<String, BTreeSet<String>>>,
}
impl InMemoryModelRegistry {
    pub fn register(&self, model: MlModel) -> Result<(), MlError> {
        model.validate()?;
        let key = format!("{}:{}", model.name, model.version);
        let mut models = self
            .models
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if models.contains_key(&model.model_id)
            || models
                .values()
                .any(|m| format!("{}:{}", m.name, m.version) == key)
        {
            return Err(MlError::Conflict(key));
        }
        self.aliases
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert((model.name.clone(), "latest".into()), model.version.clone());
        models.insert(model.model_id.clone(), model);
        Ok(())
    }
    #[must_use]
    pub fn by_id(&self, id: &str) -> Option<MlModel> {
        self.models
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(id)
            .cloned()
    }
    #[must_use]
    pub fn get(&self, name: &str, version: &str) -> Option<MlModel> {
        let version = if version == "latest" {
            self.aliases
                .read()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .get(&(name.into(), "latest".into()))
                .cloned()?
        } else {
            version.into()
        };
        self.models
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .values()
            .find(|m| m.name == name && m.version == version)
            .cloned()
    }
    #[must_use]
    pub fn list(&self, name: Option<&str>) -> Vec<MlModel> {
        self.models
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .values()
            .filter(|m| name.is_none_or(|n| m.name == n))
            .cloned()
            .collect()
    }
    pub fn set_alias(&self, name: &str, alias: &str, version: &str) -> Result<(), MlError> {
        if self.get(name, version).is_none() {
            return Err(MlError::NotFound(format!("{name}:{version}")));
        }
        self.aliases
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert((name.into(), alias.into()), version.into());
        Ok(())
    }
    pub fn update_status(&self, id: &str, status: ModelStatus, now_ms: u64) -> Result<(), MlError> {
        let mut models = self
            .models
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let model = models
            .get_mut(id)
            .ok_or_else(|| MlError::NotFound(id.into()))?;
        model.status = status;
        model.updated_at_ms = now_ms;
        if status == ModelStatus::Deployed {
            model.deployed_at_ms = Some(now_ms);
        }
        Ok(())
    }
    pub fn add_lineage(&self, parent: &str, child: &str) -> Result<(), MlError> {
        if self.by_id(parent).is_none() || self.by_id(child).is_none() {
            return Err(MlError::NotFound("lineage model".into()));
        }
        self.lineage
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .entry(parent.into())
            .or_default()
            .insert(child.into());
        Ok(())
    }
    #[must_use]
    pub fn lineage(&self, id: &str) -> BTreeMap<String, Vec<String>> {
        let lineage = self
            .lineage
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let parent = lineage
            .iter()
            .find(|(_, children)| children.contains(id))
            .map(|(p, _)| p.clone())
            .into_iter()
            .collect();
        let children = lineage
            .get(id)
            .map(|v| v.iter().cloned().collect())
            .unwrap_or_default();
        BTreeMap::from([("parent".into(), parent), ("children".into(), children)])
    }
}

#[async_trait]
pub trait InferenceProvider: Send + Sync {
    async fn load(&self, model: &MlModel) -> Result<(), MlError>;
    async fn unload(&self, model_id: &str) -> Result<(), MlError>;
    async fn predict(
        &self,
        model: &MlModel,
        features: &BTreeMap<String, Value>,
    ) -> Result<InferenceOutput, MlError>;
    async fn health(&self) -> Result<(), MlError>;
}
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct InferenceOutput {
    pub prediction: Value,
    pub confidence: Option<f64>,
    pub probabilities: Option<BTreeMap<String, f64>>,
}
#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ServingStatus {
    pub loaded_models: usize,
    pub total_requests: u64,
    pub cache_size: usize,
    pub loaded_model_ids: Vec<String>,
}

pub struct ModelServer {
    registry: Arc<InMemoryModelRegistry>,
    features: Arc<InMemoryFeatureStore>,
    provider: Arc<dyn InferenceProvider>,
    loaded: RwLock<BTreeSet<String>>,
    cache: RwLock<BTreeMap<String, ModelPrediction>>,
    metrics: RwLock<BTreeMap<String, Vec<ModelMetrics>>>,
}
impl ModelServer {
    #[must_use]
    pub fn new(
        registry: Arc<InMemoryModelRegistry>,
        features: Arc<InMemoryFeatureStore>,
        provider: Arc<dyn InferenceProvider>,
    ) -> Self {
        Self {
            registry,
            features,
            provider,
            loaded: RwLock::new(BTreeSet::new()),
            cache: RwLock::new(BTreeMap::new()),
            metrics: RwLock::new(BTreeMap::new()),
        }
    }
    pub async fn load_model(&self, id: &str, now_ms: u64) -> Result<(), MlError> {
        let model = self
            .registry
            .by_id(id)
            .ok_or_else(|| MlError::NotFound(id.into()))?;
        self.provider.load(&model).await?;
        self.loaded
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert(id.into());
        self.registry
            .update_status(id, ModelStatus::Serving, now_ms)
    }
    pub async fn unload_model(&self, id: &str, now_ms: u64) -> Result<(), MlError> {
        if !self
            .loaded
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .remove(id)
        {
            return Err(MlError::NotFound(id.into()));
        }
        self.provider.unload(id).await?;
        self.registry.update_status(id, ModelStatus::Ready, now_ms)
    }
    pub async fn predict(
        &self,
        id: &str,
        input: &BTreeMap<String, Value>,
        use_cache: bool,
        now_ms: u64,
    ) -> Result<ModelPrediction, MlError> {
        let key = cache_key(id, input);
        if use_cache
            && let Some(found) = self
                .cache
                .read()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .get(&key)
                .cloned()
        {
            return Ok(found);
        }
        if !self
            .loaded
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .contains(id)
        {
            self.load_model(id, now_ms).await?;
        }
        let model = self
            .registry
            .by_id(id)
            .ok_or_else(|| MlError::NotFound(id.into()))?;
        let required = model
            .metadata
            .get("required_features")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let names: Vec<String> = required
            .iter()
            .filter_map(Value::as_str)
            .map(str::to_owned)
            .collect();
        let mut prepared = BTreeMap::new();
        let stored = input
            .get("entity_id")
            .and_then(Value::as_str)
            .map(|entity| self.features.online_features(entity, &names))
            .unwrap_or_default();
        for name in names {
            if let Some(value) = input.get(&name).or_else(|| stored.get(&name))
                && !value.is_null()
            {
                prepared.insert(name, value.clone());
            }
        }
        let output = match self.provider.predict(&model, &prepared).await {
            Ok(output) => output,
            Err(error) => {
                self.record_metric(id, 0.0, false, now_ms);
                return Err(error);
            }
        };
        let prediction = ModelPrediction {
            prediction_id: Uuid::new_v4().to_string(),
            model_id: id.into(),
            input_features: prepared,
            prediction: output.prediction,
            confidence: output.confidence,
            probabilities: output.probabilities,
            latency_ms: None,
            timestamp_ms: now_ms,
        };
        if use_cache {
            self.cache
                .write()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .insert(key, prediction.clone());
        }
        self.record_metric(id, 0.0, true, now_ms);
        Ok(prediction)
    }
    #[allow(clippy::cast_precision_loss)]
    fn record_metric(&self, id: &str, latency: f64, success: bool, now_ms: u64) {
        let mut all = self
            .metrics
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let windows = all.entry(id.into()).or_default();
        if windows
            .last()
            .is_none_or(|m| now_ms.saturating_sub(m.timestamp_ms) > 60_000)
        {
            windows.push(ModelMetrics {
                model_id: id.into(),
                timestamp_ms: now_ms,
                ..ModelMetrics::default()
            });
        }
        let current = windows.last_mut().expect("metrics window exists");
        current.request_count = current.request_count.saturating_add(1);
        if success {
            current.success_count = current.success_count.saturating_add(1);
        } else {
            current.error_count = current.error_count.saturating_add(1);
        }
        current.avg_latency_ms = (current.avg_latency_ms * ((current.request_count - 1) as f64)
            + latency)
            / (current.request_count as f64);
        current.p95_latency_ms = current.p95_latency_ms.max(latency);
        current.p99_latency_ms = current.p99_latency_ms.max(latency);
    }
    #[must_use]
    pub fn metrics(&self, id: &str) -> Vec<ModelMetrics> {
        self.metrics
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(id)
            .cloned()
            .unwrap_or_default()
    }
    #[must_use]
    pub fn status(&self) -> ServingStatus {
        let loaded = self
            .loaded
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        ServingStatus {
            loaded_models: loaded.len(),
            total_requests: self
                .metrics
                .read()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .values()
                .flatten()
                .map(|m| m.request_count)
                .sum(),
            cache_size: self
                .cache
                .read()
                .unwrap_or_else(std::sync::PoisonError::into_inner)
                .len(),
            loaded_model_ids: loaded.iter().cloned().collect(),
        }
    }
}

pub struct ModelTrainingService;
impl ModelTrainingService {
    #[must_use]
    pub fn start(
        name: &str,
        model_type: ModelType,
        framework: ModelFramework,
        features: &[String],
        params: BTreeMap<String, Value>,
        now_ms: u64,
    ) -> MlModel {
        MlModel {
            model_id: Uuid::new_v4().to_string(),
            name: name.into(),
            version: "v1".into(),
            model_type,
            framework,
            status: ModelStatus::Training,
            model_path: None,
            model_data: None,
            metadata: BTreeMap::from([
                ("feature_names".into(), json!(features)),
                ("started_at_ms".into(), Value::from(now_ms)),
            ]),
            accuracy: None,
            precision: None,
            recall: None,
            f1_score: None,
            mse: None,
            mae: None,
            r2_score: None,
            custom_metrics: BTreeMap::new(),
            training_data_size: None,
            training_duration: None,
            hyperparameters: params,
            endpoint_url: None,
            cpu_requirement: 1.0,
            memory_requirement_mb: 1024,
            gpu_requirement: false,
            created_at_ms: now_ms,
            updated_at_ms: now_ms,
            deployed_at_ms: None,
        }
    }
    pub fn complete(
        model: &mut MlModel,
        metrics: &BTreeMap<String, f64>,
        artifact: Vec<u8>,
        now_ms: u64,
    ) {
        model.status = ModelStatus::Ready;
        model.model_data = Some(artifact);
        model.accuracy = metrics.get("accuracy").copied();
        model.precision = metrics.get("precision").copied();
        model.recall = metrics.get("recall").copied();
        model.f1_score = metrics.get("f1_score").copied();
        model.training_duration = metrics.get("duration").copied();
        model.updated_at_ms = now_ms;
    }
}

#[must_use]
pub fn prediction_cache_key(id: &str, input: &BTreeMap<String, Value>) -> String {
    let encoded = python_json_string(&json!({"model_id":id,"input_data":input}));
    let digest = Sha256::digest(encoded);
    digest[..8].iter().fold(String::new(), |mut out, byte| {
        use std::fmt::Write as _;
        let _ = write!(out, "{byte:02x}");
        out
    })
}
fn cache_key(id: &str, input: &BTreeMap<String, Value>) -> String {
    prediction_cache_key(id, input)
}

#[allow(clippy::cast_precision_loss)]
fn feature_statistics(values: &[Value]) -> FeatureStatistics {
    if values.is_empty() {
        return FeatureStatistics::default();
    }
    let unique_count = values
        .iter()
        .map(python_json_string)
        .collect::<BTreeSet<_>>()
        .len();
    let count = values.len();
    let Some(mut numeric) = values.iter().map(Value::as_f64).collect::<Option<Vec<_>>>() else {
        return FeatureStatistics {
            count: u64::try_from(count).unwrap_or(u64::MAX),
            unique_count: u64::try_from(unique_count).unwrap_or(u64::MAX),
            ..FeatureStatistics::default()
        };
    };
    numeric.sort_by(f64::total_cmp);
    let mean = numeric.iter().sum::<f64>() / (count as f64);
    let variance = numeric.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (count as f64);
    FeatureStatistics {
        count: u64::try_from(count).unwrap_or(u64::MAX),
        unique_count: u64::try_from(unique_count).unwrap_or(u64::MAX),
        null_count: 0,
        mean: Some(mean),
        std: Some(variance.sqrt()),
        min: numeric.first().copied(),
        max: numeric.last().copied(),
        median: Some(percentile(&numeric, 50.0)),
        percentile_25: Some(percentile(&numeric, 25.0)),
        percentile_75: Some(percentile(&numeric, 75.0)),
    }
}

fn python_json_string(value: &Value) -> String {
    match value {
        Value::Null => "null".into(),
        Value::Bool(value) => value.to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => serde_json::to_string(value).unwrap_or_else(|_| "\"\"".into()),
        Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(python_json_string)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(values) => format!(
            "{{{}}}",
            values
                .iter()
                .map(|(key, value)| format!(
                    "{}: {}",
                    serde_json::to_string(key).unwrap_or_else(|_| "\"\"".into()),
                    python_json_string(value)
                ))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}
#[allow(
    clippy::cast_possible_truncation,
    clippy::cast_precision_loss,
    clippy::cast_sign_loss
)]
fn percentile(values: &[f64], percent: f64) -> f64 {
    if values.len() == 1 {
        return values[0];
    }
    let rank = (percent / 100.0) * ((values.len() - 1) as f64);
    let lower = rank.floor() as usize;
    let upper = rank.ceil() as usize;
    values[lower] + (values[upper] - values[lower]) * (rank - (lower as f64))
}

#[cfg(test)]
mod tests;
