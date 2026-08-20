use std::collections::BTreeMap;
use std::sync::Arc;

use async_trait::async_trait;
use serde::Deserialize;
use serde_json::{Value, json};

use super::*;

#[derive(Deserialize)]
struct Fixture {
    schema_version: u32,
    model_types: Vec<String>,
    frameworks: Vec<String>,
    statuses: Vec<String>,
    feature_types: Vec<String>,
    numeric_values: Vec<f64>,
    numeric_statistics: FeatureStatistics,
    categorical_values: Vec<String>,
    categorical_statistics: FeatureStatistics,
    cache_key: CacheFixture,
    validation: ValidationFixture,
    lineage: LineageFixture,
}
#[derive(Deserialize)]
struct CacheFixture {
    model_id: String,
    input: BTreeMap<String, Value>,
    expected: String,
}
#[derive(Deserialize)]
struct ValidationFixture {
    below_minimum: String,
    wrong_type: String,
    unknown: String,
}
#[derive(Deserialize)]
struct LineageFixture {
    parent: String,
    child: String,
}
fn fixture() -> Fixture {
    serde_json::from_str(include_str!("../../../contracts/ml-behavior.json"))
        .expect("valid ML contract")
}

fn model(id: &str, name: &str, version: &str) -> MlModel {
    MlModel {
        model_id: id.into(),
        name: name.into(),
        version: version.into(),
        model_type: ModelType::Classification,
        framework: ModelFramework::Sklearn,
        status: ModelStatus::Ready,
        model_path: None,
        model_data: None,
        metadata: BTreeMap::new(),
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
        hyperparameters: BTreeMap::new(),
        endpoint_url: None,
        cpu_requirement: 1.0,
        memory_requirement_mb: 1024,
        gpu_requirement: false,
        created_at_ms: 1,
        updated_at_ms: 1,
        deployed_at_ms: None,
    }
}
fn feature(id: &str, name: &str, kind: FeatureType) -> Feature {
    Feature {
        feature_id: id.into(),
        name: name.into(),
        feature_type: kind,
        description: String::new(),
        source_table: None,
        source_column: None,
        transformation: None,
        min_value: None,
        max_value: None,
        allowed_values: None,
        required: true,
        mean: None,
        std: None,
        null_count: None,
        unique_count: None,
        created_at_ms: 1,
        updated_at_ms: 1,
    }
}

#[test]
fn enum_contract() {
    let f = fixture();
    assert_eq!(f.schema_version, 1);
    assert_eq!(
        serde_json::to_value([
            ModelType::Classification,
            ModelType::Regression,
            ModelType::Clustering,
            ModelType::Recommendation,
            ModelType::NaturalLanguage,
            ModelType::ComputerVision,
            ModelType::TimeSeries,
            ModelType::DeepLearning,
            ModelType::Ensemble
        ])
        .expect("types"),
        json!(f.model_types)
    );
    assert_eq!(
        serde_json::to_value([
            ModelFramework::Sklearn,
            ModelFramework::Tensorflow,
            ModelFramework::Pytorch,
            ModelFramework::Xgboost,
            ModelFramework::Lightgbm,
            ModelFramework::Keras,
            ModelFramework::Onnx,
            ModelFramework::Huggingface,
            ModelFramework::Custom
        ])
        .expect("frameworks"),
        json!(f.frameworks)
    );
    assert_eq!(
        serde_json::to_value([
            ModelStatus::Training,
            ModelStatus::Validating,
            ModelStatus::Ready,
            ModelStatus::Deployed,
            ModelStatus::Serving,
            ModelStatus::Deprecated,
            ModelStatus::Failed,
            ModelStatus::Archived
        ])
        .expect("statuses"),
        json!(f.statuses)
    );
    assert_eq!(
        serde_json::to_value([
            FeatureType::Numerical,
            FeatureType::Categorical,
            FeatureType::Text,
            FeatureType::Datetime,
            FeatureType::Boolean,
            FeatureType::Embedding,
            FeatureType::Array,
            FeatureType::Json
        ])
        .expect("features"),
        json!(f.feature_types)
    );
}

#[test]
fn feature_store_statistics_validation_and_time_filter_contract() {
    let f = fixture();
    let store = InMemoryFeatureStore::default();
    let mut age = feature("age", "age", FeatureType::Numerical);
    age.min_value = Some(18.0);
    store.register_feature(age).expect("register");
    for (index, value) in f.numeric_values.iter().enumerate() {
        store
            .set_online_features(
                &format!("entity-{index}"),
                BTreeMap::from([("score".into(), Value::from(*value))]),
            )
            .expect("online");
    }
    for (index, value) in f.categorical_values.iter().enumerate() {
        store
            .add_offline_features(
                &format!("entity-{index}"),
                BTreeMap::from([("state".into(), Value::String(value.clone()))]),
                u64::try_from(index).expect("index"),
            )
            .expect("offline");
    }
    let numeric = store.feature_statistics("score");
    assert_eq!(numeric, f.numeric_statistics);
    let categorical = store.feature_statistics("state");
    assert_eq!(categorical.count, f.categorical_statistics.count);
    assert_eq!(
        categorical.unique_count,
        f.categorical_statistics.unique_count
    );
    let errors = store.validate_features(&BTreeMap::from([
        ("age".into(), Value::from(17)),
        ("unknown".into(), Value::Bool(true)),
    ]));
    assert_eq!(errors["age"][0], f.validation.below_minimum);
    assert_eq!(errors["unknown"][0], f.validation.unknown);
    let wrong = store.validate_features(&BTreeMap::from([(
        "age".into(),
        Value::String("old".into()),
    )]));
    assert_eq!(wrong["age"][0], f.validation.wrong_type);
    assert_eq!(
        store
            .offline_features(&["state".into()], Some(1), Some(1))
            .len(),
        1
    );
}

#[test]
fn registry_latest_alias_status_and_lineage_contract() {
    let f = fixture();
    let registry = InMemoryModelRegistry::default();
    registry
        .register(model(&f.lineage.parent, "risk", "v1"))
        .expect("parent");
    registry
        .register(model(&f.lineage.child, "risk", "v2"))
        .expect("child");
    assert_eq!(
        registry.get("risk", "latest").expect("latest").version,
        "v2"
    );
    registry
        .set_alias("risk", "production", "v1")
        .expect("alias");
    registry
        .add_lineage(&f.lineage.parent, &f.lineage.child)
        .expect("lineage");
    let lineage = registry.lineage(&f.lineage.child);
    assert_eq!(lineage["parent"], vec![f.lineage.parent]);
    registry
        .update_status(&f.lineage.child, ModelStatus::Deployed, 10)
        .expect("status");
    assert_eq!(
        registry
            .by_id(&f.lineage.child)
            .expect("model")
            .deployed_at_ms,
        Some(10)
    );
}

#[test]
fn cache_key_and_training_contract() {
    let f = fixture();
    assert_eq!(
        prediction_cache_key(&f.cache_key.model_id, &f.cache_key.input),
        f.cache_key.expected
    );
    let mut trained = ModelTrainingService::start(
        "risk",
        ModelType::Classification,
        ModelFramework::Onnx,
        &["age".into()],
        BTreeMap::new(),
        1,
    );
    ModelTrainingService::complete(
        &mut trained,
        &BTreeMap::from([("accuracy".into(), 0.9)]),
        vec![1, 2],
        2,
    );
    assert_eq!(trained.status, ModelStatus::Ready);
    assert_eq!(trained.accuracy, Some(0.9));
    assert_eq!(trained.model_data, Some(vec![1, 2]));
}

struct Provider;
#[async_trait]
impl InferenceProvider for Provider {
    async fn load(&self, _: &MlModel) -> Result<(), MlError> {
        Ok(())
    }
    async fn unload(&self, _: &str) -> Result<(), MlError> {
        Ok(())
    }
    async fn predict(
        &self,
        _: &MlModel,
        _features: &BTreeMap<String, Value>,
    ) -> Result<InferenceOutput, MlError> {
        Ok(InferenceOutput {
            prediction: json!("approved"),
            confidence: Some(0.95),
            probabilities: None,
        })
    }
    async fn health(&self) -> Result<(), MlError> {
        Ok(())
    }
}

#[tokio::test]
async fn serving_load_feature_resolution_cache_metrics_and_unload_contract() {
    let registry = Arc::new(InMemoryModelRegistry::default());
    let features = Arc::new(InMemoryFeatureStore::default());
    let mut candidate = model("model-1", "risk", "v1");
    candidate
        .metadata
        .insert("required_features".into(), json!(["age", "score"]));
    registry.register(candidate).expect("register");
    features
        .set_online_features("entity-1", BTreeMap::from([("score".into(), json!(8))]))
        .expect("features");
    let server = ModelServer::new(registry.clone(), features, Arc::new(Provider));
    let input = BTreeMap::from([
        ("entity_id".into(), json!("entity-1")),
        ("age".into(), json!(42)),
    ]);
    let first = server
        .predict("model-1", &input, true, 10)
        .await
        .expect("predict");
    let second = server
        .predict("model-1", &input, true, 11)
        .await
        .expect("cache");
    assert_eq!(first, second);
    assert_eq!(first.input_features.len(), 2);
    assert_eq!(server.status().loaded_models, 1);
    assert_eq!(server.status().cache_size, 1);
    assert_eq!(server.metrics("model-1")[0].request_count, 1);
    server.unload_model("model-1", 12).await.expect("unload");
    assert_eq!(
        registry.by_id("model-1").expect("model").status,
        ModelStatus::Ready
    );
}

#[test]
fn malformed_models_and_experiments_fail_closed() {
    let mut invalid = model("", "risk", "v1");
    assert!(invalid.validate().is_err());
    invalid.model_id = "id".into();
    invalid.accuracy = Some(2.0);
    assert!(invalid.validate().is_err());
    let experiment = AbTestExperiment {
        experiment_id: "e".into(),
        name: "test".into(),
        description: String::new(),
        control_model_id: "a".into(),
        treatment_model_ids: vec!["b".into()],
        traffic_split: BTreeMap::from([("a".into(), 0.2), ("b".into(), 0.2)]),
        primary_metric: "accuracy".into(),
        status: ExperimentStatus::Draft,
        secondary_metrics: Vec::new(),
        min_sample_size: 1,
        max_duration_days: 1,
        significance_level: 0.05,
        power: 0.8,
        results: BTreeMap::new(),
        winner_model_id: None,
        created_at_ms: 1,
        started_at_ms: None,
        ended_at_ms: None,
    };
    assert!(experiment.validate().is_err());
}
