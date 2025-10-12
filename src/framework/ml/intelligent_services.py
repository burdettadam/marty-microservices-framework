"""
AI/ML Integration and Intelligent Services for Marty Microservices Framework

This module provides comprehensive AI/ML integration capabilities including model serving,
feature stores, A/B testing, automated deployment pipelines, and intelligent recommendations.
"""

import builtins
import hashlib
import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import numpy as np


class ModelType(Enum):
    """ML model types."""

    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    RECOMMENDATION = "recommendation"
    NATURAL_LANGUAGE = "natural_language"
    COMPUTER_VISION = "computer_vision"
    TIME_SERIES = "time_series"
    DEEP_LEARNING = "deep_learning"
    ENSEMBLE = "ensemble"


class ModelFramework(Enum):
    """ML framework types."""

    SKLEARN = "sklearn"
    TENSORFLOW = "tensorflow"
    PYTORCH = "pytorch"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    KERAS = "keras"
    ONNX = "onnx"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"


class ModelStatus(Enum):
    """Model deployment status."""

    TRAINING = "training"
    VALIDATING = "validating"
    READY = "ready"
    DEPLOYED = "deployed"
    SERVING = "serving"
    DEPRECATED = "deprecated"
    FAILED = "failed"
    ARCHIVED = "archived"


class ExperimentStatus(Enum):
    """A/B test experiment status."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FeatureType(Enum):
    """Feature data types."""

    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"
    TEXT = "text"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    EMBEDDING = "embedding"
    ARRAY = "array"
    JSON = "json"


@dataclass
class MLModel:
    """ML model definition."""

    model_id: str
    name: str
    version: str
    model_type: ModelType
    framework: ModelFramework
    status: ModelStatus = ModelStatus.TRAINING

    # Model artifacts
    model_path: str | None = None
    model_data: bytes | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    mse: float | None = None
    mae: float | None = None
    r2_score: float | None = None
    custom_metrics: builtins.dict[str, float] = field(default_factory=dict)

    # Training information
    training_data_size: int | None = None
    training_duration: float | None = None
    hyperparameters: builtins.dict[str, Any] = field(default_factory=dict)

    # Deployment information
    endpoint_url: str | None = None
    cpu_requirement: float = 1.0
    memory_requirement: int = 1024  # MB
    gpu_requirement: bool = False

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deployed_at: datetime | None = None


@dataclass
class Feature:
    """Feature definition for ML models."""

    feature_id: str
    name: str
    feature_type: FeatureType
    description: str = ""

    # Feature metadata
    source_table: str | None = None
    source_column: str | None = None
    transformation: str | None = None

    # Validation rules
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: builtins.list[Any] | None = None
    required: bool = True

    # Statistics
    mean: float | None = None
    std: float | None = None
    null_count: int | None = None
    unique_count: int | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FeatureGroup:
    """Group of related features."""

    group_id: str
    name: str
    description: str
    features: builtins.list[Feature] = field(default_factory=list)
    online_enabled: bool = True
    offline_enabled: bool = True

    # Storage configuration
    online_store: str | None = None
    offline_store: str | None = None

    # Update frequency
    update_frequency: str = "daily"  # daily, hourly, real-time

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ModelPrediction:
    """Model prediction result."""

    prediction_id: str
    model_id: str
    input_features: builtins.dict[str, Any]
    prediction: Any
    confidence: float | None = None
    probabilities: builtins.dict[str, float] | None = None
    latency_ms: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ABTestExperiment:
    """A/B testing experiment definition."""

    experiment_id: str
    name: str
    description: str
    status: ExperimentStatus = ExperimentStatus.DRAFT

    # Experiment configuration
    control_model_id: str
    treatment_model_ids: builtins.list[str]
    traffic_split: builtins.dict[str, float]  # model_id -> percentage

    # Target metrics
    primary_metric: str
    secondary_metrics: builtins.list[str] = field(default_factory=list)

    # Experiment parameters
    min_sample_size: int = 1000
    max_duration_days: int = 30
    significance_level: float = 0.05
    power: float = 0.8

    # Results
    results: builtins.dict[str, Any] = field(default_factory=dict)
    winner_model_id: str | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    ended_at: datetime | None = None


@dataclass
class ModelMetrics:
    """Model performance metrics."""

    model_id: str
    timestamp: datetime

    # Performance metrics
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0

    # Resource metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    gpu_usage: float = 0.0

    # Business metrics
    prediction_accuracy: float | None = None
    user_satisfaction: float | None = None
    revenue_impact: float | None = None


class ModelRegistry:
    """Registry for ML models with versioning and metadata."""

    def __init__(self):
        """Initialize model registry."""
        self.models: builtins.dict[str, builtins.dict[str, MLModel]] = defaultdict(
            dict
        )  # name -> version -> model
        self.model_index: builtins.dict[str, MLModel] = {}  # model_id -> model

        # Model aliases (latest, production, etc.)
        self.aliases: builtins.dict[str, builtins.dict[str, str]] = defaultdict(
            dict
        )  # name -> alias -> version

        # Model lineage
        self.lineage: builtins.dict[str, builtins.list[str]] = defaultdict(
            list
        )  # parent_model_id -> [child_model_ids]

        # Thread safety
        self._lock = threading.RLock()

    def register_model(self, model: MLModel) -> bool:
        """Register a new model."""
        try:
            with self._lock:
                self.models[model.name][model.version] = model
                self.model_index[model.model_id] = model

                # Set as latest version
                self.aliases[model.name]["latest"] = model.version

                logging.info(f"Registered model: {model.name} v{model.version}")
                return True

        except Exception as e:
            logging.exception(f"Failed to register model: {e}")
            return False

    def get_model(self, name: str, version: str = "latest") -> MLModel | None:
        """Get model by name and version."""
        with self._lock:
            if version == "latest":
                version = self.aliases[name].get("latest")
                if not version:
                    return None

            return self.models[name].get(version)

    def get_model_by_id(self, model_id: str) -> MLModel | None:
        """Get model by ID."""
        with self._lock:
            return self.model_index.get(model_id)

    def list_models(self, name: str | None = None) -> builtins.list[MLModel]:
        """List models."""
        with self._lock:
            if name:
                return list(self.models[name].values())
            return list(self.model_index.values())

    def set_alias(self, name: str, alias: str, version: str) -> bool:
        """Set alias for model version."""
        try:
            with self._lock:
                if name in self.models and version in self.models[name]:
                    self.aliases[name][alias] = version
                    logging.info(f"Set alias {alias} for {name} v{version}")
                    return True
                return False

        except Exception as e:
            logging.exception(f"Failed to set alias: {e}")
            return False

    def update_model_status(self, model_id: str, status: ModelStatus) -> bool:
        """Update model status."""
        try:
            with self._lock:
                model = self.model_index.get(model_id)
                if model:
                    model.status = status
                    model.updated_at = datetime.now(timezone.utc)

                    if status == ModelStatus.DEPLOYED:
                        model.deployed_at = datetime.now(timezone.utc)

                    logging.info(f"Updated model {model_id} status to {status.value}")
                    return True
                return False

        except Exception as e:
            logging.exception(f"Failed to update model status: {e}")
            return False

    def add_lineage(self, parent_model_id: str, child_model_id: str):
        """Add model lineage relationship."""
        with self._lock:
            self.lineage[parent_model_id].append(child_model_id)

    def get_lineage(self, model_id: str) -> builtins.dict[str, builtins.list[str]]:
        """Get model lineage."""
        with self._lock:
            # Find children
            children = self.lineage.get(model_id, [])

            # Find parent
            parent = None
            for parent_id, child_ids in self.lineage.items():
                if model_id in child_ids:
                    parent = parent_id
                    break

            return {"parent": parent, "children": children}


class FeatureStore:
    """Feature store for ML feature management."""

    def __init__(self):
        """Initialize feature store."""
        self.features: builtins.dict[str, Feature] = {}
        self.feature_groups: builtins.dict[str, FeatureGroup] = {}

        # Feature data storage (in-memory for demo)
        self.online_store: builtins.dict[
            str, builtins.dict[str, Any]
        ] = {}  # entity_id -> features
        self.offline_store: builtins.dict[
            str, builtins.list[builtins.dict[str, Any]]
        ] = defaultdict(list)

        # Feature statistics
        self.feature_stats: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Thread safety
        self._lock = threading.RLock()

    def register_feature(self, feature: Feature) -> bool:
        """Register a feature."""
        try:
            with self._lock:
                self.features[feature.feature_id] = feature
                logging.info(f"Registered feature: {feature.name}")
                return True

        except Exception as e:
            logging.exception(f"Failed to register feature: {e}")
            return False

    def register_feature_group(self, feature_group: FeatureGroup) -> bool:
        """Register a feature group."""
        try:
            with self._lock:
                self.feature_groups[feature_group.group_id] = feature_group
                logging.info(f"Registered feature group: {feature_group.name}")
                return True

        except Exception as e:
            logging.exception(f"Failed to register feature group: {e}")
            return False

    def get_online_features(
        self, entity_id: str, feature_names: builtins.list[str]
    ) -> builtins.dict[str, Any]:
        """Get online features for an entity."""
        with self._lock:
            entity_features = self.online_store.get(entity_id, {})

            result = {}
            for feature_name in feature_names:
                result[feature_name] = entity_features.get(feature_name)

            return result

    def set_online_features(
        self, entity_id: str, features: builtins.dict[str, Any]
    ) -> bool:
        """Set online features for an entity."""
        try:
            with self._lock:
                if entity_id not in self.online_store:
                    self.online_store[entity_id] = {}

                self.online_store[entity_id].update(features)
                return True

        except Exception as e:
            logging.exception(f"Failed to set online features: {e}")
            return False

    def get_offline_features(
        self,
        feature_names: builtins.list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Get offline features for training."""
        with self._lock:
            result = []

            for entity_id, feature_history in self.offline_store.items():
                for feature_record in feature_history:
                    # Apply time filters
                    record_time = feature_record.get("timestamp")
                    if start_time and record_time and record_time < start_time:
                        continue
                    if end_time and record_time and record_time > end_time:
                        continue

                    # Extract requested features
                    filtered_record = {"entity_id": entity_id}
                    for feature_name in feature_names:
                        if feature_name in feature_record:
                            filtered_record[feature_name] = feature_record[feature_name]

                    result.append(filtered_record)

            return result

    def add_offline_features(
        self, entity_id: str, features: builtins.dict[str, Any]
    ) -> bool:
        """Add offline features for an entity."""
        try:
            with self._lock:
                features["timestamp"] = datetime.now(timezone.utc)
                self.offline_store[entity_id].append(features)
                return True

        except Exception as e:
            logging.exception(f"Failed to add offline features: {e}")
            return False

    def compute_feature_statistics(self, feature_name: str) -> builtins.dict[str, Any]:
        """Compute statistics for a feature."""
        with self._lock:
            values = []

            # Collect values from online store
            for entity_features in self.online_store.values():
                if feature_name in entity_features:
                    value = entity_features[feature_name]
                    if value is not None:
                        values.append(value)

            # Collect values from offline store
            for feature_history in self.offline_store.values():
                for feature_record in feature_history:
                    if feature_name in feature_record:
                        value = feature_record[feature_name]
                        if value is not None:
                            values.append(value)

            if not values:
                return {}

            # Compute statistics
            stats = {
                "count": len(values),
                "unique_count": len(set(values)),
                "null_count": 0,  # Already filtered out nulls
            }

            # Numerical statistics
            if all(isinstance(v, int | float) for v in values):
                stats.update(
                    {
                        "mean": np.mean(values),
                        "std": np.std(values),
                        "min": np.min(values),
                        "max": np.max(values),
                        "median": np.median(values),
                        "percentile_25": np.percentile(values, 25),
                        "percentile_75": np.percentile(values, 75),
                    }
                )

            self.feature_stats[feature_name] = stats
            return stats

    def validate_features(
        self, entity_id: str, features: builtins.dict[str, Any]
    ) -> builtins.dict[str, builtins.list[str]]:
        """Validate features against registered schema."""
        validation_errors = defaultdict(list)

        for feature_name, value in features.items():
            feature = self.features.get(feature_name)

            if not feature:
                validation_errors[feature_name].append("Feature not registered")
                continue

            # Required validation
            if feature.required and value is None:
                validation_errors[feature_name].append("Required feature is null")
                continue

            if value is None:
                continue  # Skip other validations for null values

            # Type validation
            if feature.feature_type == FeatureType.NUMERICAL and not isinstance(
                value, int | float
            ):
                validation_errors[feature_name].append("Expected numerical value")

            # Range validation
            if (
                feature.min_value is not None
                and isinstance(value, int | float)
                and value < feature.min_value
            ):
                validation_errors[feature_name].append(
                    f"Value below minimum: {feature.min_value}"
                )

            if (
                feature.max_value is not None
                and isinstance(value, int | float)
                and value > feature.max_value
            ):
                validation_errors[feature_name].append(
                    f"Value above maximum: {feature.max_value}"
                )

            # Allowed values validation
            if feature.allowed_values and value not in feature.allowed_values:
                validation_errors[feature_name].append(
                    f"Value not in allowed list: {feature.allowed_values}"
                )

        return dict(validation_errors)


class ModelServer:
    """Model serving infrastructure."""

    def __init__(self, model_registry: ModelRegistry, feature_store: FeatureStore):
        """Initialize model server."""
        self.model_registry = model_registry
        self.feature_store = feature_store

        # Loaded models cache
        self.loaded_models: builtins.dict[str, Any] = {}

        # Prediction cache
        self.prediction_cache: builtins.dict[str, ModelPrediction] = {}

        # Performance tracking
        self.model_metrics: builtins.dict[
            str, builtins.list[ModelMetrics]
        ] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

    async def load_model(self, model_id: str) -> bool:
        """Load model into memory."""
        try:
            model = self.model_registry.get_model_by_id(model_id)
            if not model:
                return False

            with self._lock:
                # Simulate model loading
                if model.framework == ModelFramework.SKLEARN:
                    # Load sklearn model
                    if model.model_path:
                        # In practice: model_obj = joblib.load(model.model_path)
                        model_obj = {"type": "sklearn", "path": model.model_path}
                    else:
                        # In practice: model_obj = pickle.loads(model.model_data)
                        model_obj = {"type": "sklearn", "data": "serialized_model"}

                elif model.framework == ModelFramework.TENSORFLOW:
                    # Load TensorFlow model
                    model_obj = {"type": "tensorflow", "path": model.model_path}

                else:
                    # Generic model loading
                    model_obj = {"type": "generic", "framework": model.framework.value}

                self.loaded_models[model_id] = model_obj

                # Update model status
                self.model_registry.update_model_status(model_id, ModelStatus.SERVING)

                logging.info(f"Loaded model: {model_id}")
                return True

        except Exception as e:
            logging.exception(f"Failed to load model {model_id}: {e}")
            return False

    async def unload_model(self, model_id: str) -> bool:
        """Unload model from memory."""
        try:
            with self._lock:
                if model_id in self.loaded_models:
                    del self.loaded_models[model_id]

                    # Update model status
                    self.model_registry.update_model_status(model_id, ModelStatus.READY)

                    logging.info(f"Unloaded model: {model_id}")
                    return True
                return False

        except Exception as e:
            logging.exception(f"Failed to unload model {model_id}: {e}")
            return False

    async def predict(
        self, model_id: str, input_data: builtins.dict[str, Any], use_cache: bool = True
    ) -> ModelPrediction | None:
        """Make prediction using model."""
        start_time = time.time()

        try:
            # Check cache first
            if use_cache:
                cache_key = self._generate_cache_key(model_id, input_data)
                cached_prediction = self.prediction_cache.get(cache_key)

                if cached_prediction:
                    return cached_prediction

            # Load model if not loaded
            if model_id not in self.loaded_models:
                success = await self.load_model(model_id)
                if not success:
                    return None

            self.model_registry.get_model_by_id(model_id)
            model_obj = self.loaded_models[model_id]

            # Prepare features
            features = await self._prepare_features(model_id, input_data)

            # Make prediction
            prediction_result = await self._make_prediction(model_obj, features)

            # Create prediction object
            prediction = ModelPrediction(
                prediction_id=str(uuid.uuid4()),
                model_id=model_id,
                input_features=features,
                prediction=prediction_result["prediction"],
                confidence=prediction_result.get("confidence"),
                probabilities=prediction_result.get("probabilities"),
                latency_ms=(time.time() - start_time) * 1000,
            )

            # Cache prediction
            if use_cache:
                cache_key = self._generate_cache_key(model_id, input_data)
                self.prediction_cache[cache_key] = prediction

            # Update metrics
            self._update_model_metrics(model_id, prediction.latency_ms, success=True)

            return prediction

        except Exception as e:
            self._update_model_metrics(
                model_id, (time.time() - start_time) * 1000, success=False
            )
            logging.exception(f"Prediction error for model {model_id}: {e}")
            return None

    async def _prepare_features(
        self, model_id: str, input_data: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Prepare features for prediction."""
        # Get feature names from model metadata
        model = self.model_registry.get_model_by_id(model_id)
        required_features = model.metadata.get("required_features", [])

        features = {}

        for feature_name in required_features:
            if feature_name in input_data:
                features[feature_name] = input_data[feature_name]
            else:
                # Try to get from feature store
                entity_id = input_data.get("entity_id")
                if entity_id:
                    feature_value = self.feature_store.get_online_features(
                        entity_id, [feature_name]
                    ).get(feature_name)

                    if feature_value is not None:
                        features[feature_name] = feature_value

        return features

    async def _make_prediction(
        self, model_obj: Any, features: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Make prediction using loaded model."""
        # Simulate prediction based on model type
        framework = model_obj.get("type", "generic")

        if framework == "sklearn":
            # Simulate sklearn prediction
            # In practice: prediction = model_obj.predict([list(features.values())])[0]
            prediction = np.random.random()
            confidence = np.random.random()

            return {"prediction": prediction, "confidence": confidence}

        if framework == "tensorflow":
            # Simulate TensorFlow prediction
            prediction = np.random.random(10)  # Multi-class prediction
            probabilities = {
                f"class_{i}": float(pred) for i, pred in enumerate(prediction)
            }

            return {
                "prediction": int(np.argmax(prediction)),
                "probabilities": probabilities,
                "confidence": float(np.max(prediction)),
            }

        # Generic prediction
        return {"prediction": np.random.random(), "confidence": np.random.random()}

    def _generate_cache_key(
        self, model_id: str, input_data: builtins.dict[str, Any]
    ) -> str:
        """Generate cache key for prediction."""
        # Create deterministic hash of model_id and input_data
        cache_input = {"model_id": model_id, "input_data": input_data}

        cache_string = json.dumps(cache_input, sort_keys=True)
        return hashlib.sha256(cache_string.encode()).hexdigest()[:16]

    def _update_model_metrics(self, model_id: str, latency_ms: float, success: bool):
        """Update model performance metrics."""
        with self._lock:
            # Get current metrics or create new
            current_metrics = self.model_metrics[model_id]

            if not current_metrics or len(current_metrics) == 0:
                metrics = ModelMetrics(
                    model_id=model_id, timestamp=datetime.now(timezone.utc)
                )
                self.model_metrics[model_id].append(metrics)
            else:
                metrics = current_metrics[-1]

                # Create new metrics if current one is too old (> 1 minute)
                if (
                    datetime.now(timezone.utc) - metrics.timestamp
                ).total_seconds() > 60:
                    metrics = ModelMetrics(
                        model_id=model_id, timestamp=datetime.now(timezone.utc)
                    )
                    self.model_metrics[model_id].append(metrics)

            # Update metrics
            metrics.request_count += 1

            if success:
                metrics.success_count += 1
            else:
                metrics.error_count += 1

            # Update latency (moving average)
            if metrics.request_count == 1:
                metrics.avg_latency = latency_ms
            else:
                metrics.avg_latency = (
                    metrics.avg_latency * (metrics.request_count - 1) + latency_ms
                ) / metrics.request_count

            # Update percentiles (simplified)
            metrics.p95_latency = max(metrics.p95_latency, latency_ms)
            metrics.p99_latency = max(metrics.p99_latency, latency_ms)

    def get_model_metrics(self, model_id: str) -> builtins.list[ModelMetrics]:
        """Get performance metrics for a model."""
        with self._lock:
            return self.model_metrics.get(model_id, [])

    def get_serving_status(self) -> builtins.dict[str, Any]:
        """Get overall serving status."""
        with self._lock:
            total_models = len(self.loaded_models)
            total_requests = sum(
                sum(m.request_count for m in metrics)
                for metrics in self.model_metrics.values()
            )

            return {
                "loaded_models": total_models,
                "total_requests": total_requests,
                "cache_size": len(self.prediction_cache),
                "loaded_model_ids": list(self.loaded_models.keys()),
            }


class ABTestManager:
    """Manages A/B testing for ML models."""

    def __init__(self, model_server: ModelServer):
        """Initialize A/B test manager."""
        self.model_server = model_server
        self.experiments: builtins.dict[str, ABTestExperiment] = {}

        # Experiment data
        self.experiment_data: builtins.dict[
            str, builtins.list[builtins.dict[str, Any]]
        ] = defaultdict(list)

        # Traffic routing
        self.traffic_router = TrafficRouter()

        # Thread safety
        self._lock = threading.RLock()

    def create_experiment(self, experiment: ABTestExperiment) -> bool:
        """Create A/B test experiment."""
        try:
            with self._lock:
                # Validate traffic split
                total_traffic = sum(experiment.traffic_split.values())
                if abs(total_traffic - 1.0) > 0.01:  # Allow small floating point errors
                    logging.error(f"Traffic split must sum to 1.0, got {total_traffic}")
                    return False

                self.experiments[experiment.experiment_id] = experiment

                logging.info(f"Created experiment: {experiment.name}")
                return True

        except Exception as e:
            logging.exception(f"Failed to create experiment: {e}")
            return False

    def start_experiment(self, experiment_id: str) -> bool:
        """Start A/B test experiment."""
        try:
            with self._lock:
                experiment = self.experiments.get(experiment_id)
                if not experiment:
                    return False

                experiment.status = ExperimentStatus.RUNNING
                experiment.started_at = datetime.now(timezone.utc)

                # Configure traffic router
                self.traffic_router.configure_experiment(experiment)

                logging.info(f"Started experiment: {experiment.name}")
                return True

        except Exception as e:
            logging.exception(f"Failed to start experiment: {e}")
            return False

    def stop_experiment(self, experiment_id: str) -> bool:
        """Stop A/B test experiment."""
        try:
            with self._lock:
                experiment = self.experiments.get(experiment_id)
                if not experiment:
                    return False

                experiment.status = ExperimentStatus.COMPLETED
                experiment.ended_at = datetime.now(timezone.utc)

                # Analyze results
                results = self._analyze_experiment_results(experiment)
                experiment.results = results

                # Determine winner
                experiment.winner_model_id = results.get("winner_model_id")

                logging.info(f"Stopped experiment: {experiment.name}")
                return True

        except Exception as e:
            logging.exception(f"Failed to stop experiment: {e}")
            return False

    async def route_prediction(
        self, experiment_id: str, input_data: builtins.dict[str, Any]
    ) -> ModelPrediction | None:
        """Route prediction through A/B test."""
        with self._lock:
            experiment = self.experiments.get(experiment_id)
            if not experiment or experiment.status != ExperimentStatus.RUNNING:
                return None

        # Route to model based on traffic split
        selected_model_id = self.traffic_router.route_request(experiment_id, input_data)

        if not selected_model_id:
            return None

        # Make prediction
        prediction = await self.model_server.predict(selected_model_id, input_data)

        if prediction:
            # Record experiment data
            experiment_record = {
                "experiment_id": experiment_id,
                "model_id": selected_model_id,
                "input_data": input_data,
                "prediction": prediction.prediction,
                "confidence": prediction.confidence,
                "latency_ms": prediction.latency_ms,
                "timestamp": prediction.timestamp,
            }

            with self._lock:
                self.experiment_data[experiment_id].append(experiment_record)

        return prediction

    def record_feedback(
        self, experiment_id: str, prediction_id: str, feedback: builtins.dict[str, Any]
    ) -> bool:
        """Record user feedback for experiment."""
        try:
            with self._lock:
                # Find the prediction record
                for record in self.experiment_data[experiment_id]:
                    if record.get("prediction_id") == prediction_id:
                        record["feedback"] = feedback
                        record["feedback_timestamp"] = datetime.now(timezone.utc)
                        return True

                return False

        except Exception as e:
            logging.exception(f"Failed to record feedback: {e}")
            return False

    def _analyze_experiment_results(
        self, experiment: ABTestExperiment
    ) -> builtins.dict[str, Any]:
        """Analyze A/B test results."""
        experiment_records = self.experiment_data.get(experiment.experiment_id, [])

        if not experiment_records:
            return {"error": "No experiment data available"}

        # Group by model
        model_results = defaultdict(list)
        for record in experiment_records:
            model_id = record["model_id"]
            model_results[model_id].append(record)

        # Calculate metrics for each model
        model_metrics = {}

        for model_id, records in model_results.items():
            total_predictions = len(records)
            avg_latency = np.mean([r["latency_ms"] for r in records])
            avg_confidence = np.mean(
                [r["confidence"] for r in records if r["confidence"]]
            )

            # Calculate primary metric (if feedback available)
            primary_metric_values = []
            for record in records:
                if (
                    "feedback" in record
                    and experiment.primary_metric in record["feedback"]
                ):
                    primary_metric_values.append(
                        record["feedback"][experiment.primary_metric]
                    )

            avg_primary_metric = (
                np.mean(primary_metric_values) if primary_metric_values else None
            )

            model_metrics[model_id] = {
                "total_predictions": total_predictions,
                "avg_latency": avg_latency,
                "avg_confidence": avg_confidence,
                "avg_primary_metric": avg_primary_metric,
                "sample_size": len(primary_metric_values),
            }

        # Determine winner (highest primary metric)
        winner_model_id = None
        if any(m["avg_primary_metric"] is not None for m in model_metrics.values()):
            winner_model_id = max(
                model_metrics.keys(),
                key=lambda mid: model_metrics[mid]["avg_primary_metric"] or 0,
            )

        return {
            "model_metrics": model_metrics,
            "winner_model_id": winner_model_id,
            "total_samples": len(experiment_records),
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_experiment_status(
        self, experiment_id: str
    ) -> builtins.dict[str, Any] | None:
        """Get experiment status and results."""
        with self._lock:
            experiment = self.experiments.get(experiment_id)
            if not experiment:
                return None

            data_count = len(self.experiment_data.get(experiment_id, []))

            return {
                "experiment_id": experiment.experiment_id,
                "name": experiment.name,
                "status": experiment.status.value,
                "data_points": data_count,
                "traffic_split": experiment.traffic_split,
                "results": experiment.results,
                "winner_model_id": experiment.winner_model_id,
                "created_at": experiment.created_at.isoformat(),
                "started_at": experiment.started_at.isoformat()
                if experiment.started_at
                else None,
                "ended_at": experiment.ended_at.isoformat()
                if experiment.ended_at
                else None,
            }


class TrafficRouter:
    """Routes traffic for A/B testing."""

    def __init__(self):
        """Initialize traffic router."""
        self.experiment_configs: builtins.dict[str, ABTestExperiment] = {}
        self.routing_history: builtins.dict[str, builtins.list[str]] = defaultdict(list)

    def configure_experiment(self, experiment: ABTestExperiment):
        """Configure experiment for traffic routing."""
        self.experiment_configs[experiment.experiment_id] = experiment

    def route_request(
        self, experiment_id: str, input_data: builtins.dict[str, Any]
    ) -> str | None:
        """Route request to appropriate model."""
        experiment = self.experiment_configs.get(experiment_id)
        if not experiment:
            return None

        # Generate deterministic routing based on user ID or session
        user_id = input_data.get(
            "user_id", input_data.get("session_id", str(uuid.uuid4()))
        )

        # Create hash for consistent routing
        hash_input = f"{experiment_id}:{user_id}"
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest()[:8], 16)
        routing_value = (hash_value % 10000) / 10000.0  # Convert to 0-1 range

        # Route based on traffic split
        cumulative_split = 0.0
        for model_id, traffic_percentage in experiment.traffic_split.items():
            cumulative_split += traffic_percentage
            if routing_value <= cumulative_split:
                self.routing_history[experiment_id].append(model_id)
                return model_id

        # Fallback to control model
        return experiment.control_model_id


class MLObservability:
    """ML observability and monitoring."""

    def __init__(self):
        """Initialize ML observability."""
        self.metrics_collectors: builtins.dict[str, Callable] = {}
        self.alerting_rules: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.dashboards: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Monitoring data
        self.monitoring_data: builtins.dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )

        # Alert state
        self.alert_states: builtins.dict[str, bool] = {}

    def register_metrics_collector(
        self, name: str, collector: Callable[[], builtins.dict[str, float]]
    ):
        """Register metrics collector."""
        self.metrics_collectors[name] = collector
        logging.info(f"Registered metrics collector: {name}")

    def create_alerting_rule(
        self, rule_name: str, metric_name: str, threshold: float, operator: str = ">"
    ):
        """Create alerting rule."""
        self.alerting_rules[rule_name] = {
            "metric_name": metric_name,
            "threshold": threshold,
            "operator": operator,
            "created_at": datetime.now(timezone.utc),
        }

        self.alert_states[rule_name] = False
        logging.info(f"Created alerting rule: {rule_name}")

    async def collect_metrics(self):
        """Collect metrics from all collectors."""
        timestamp = datetime.now(timezone.utc)

        for collector_name, collector_func in self.metrics_collectors.items():
            try:
                metrics = collector_func()

                for metric_name, value in metrics.items():
                    metric_record = {
                        "timestamp": timestamp,
                        "collector": collector_name,
                        "value": value,
                    }

                    self.monitoring_data[metric_name].append(metric_record)

            except Exception as e:
                logging.exception(f"Metrics collection error for {collector_name}: {e}")

    async def check_alerts(self):
        """Check alerting rules."""
        for rule_name, rule in self.alerting_rules.items():
            try:
                metric_name = rule["metric_name"]
                threshold = rule["threshold"]
                operator = rule["operator"]

                # Get latest metric value
                latest_metrics = self.monitoring_data.get(metric_name, deque())
                if not latest_metrics:
                    continue

                latest_value = latest_metrics[-1]["value"]

                # Evaluate condition
                alert_triggered = False
                if operator == ">":
                    alert_triggered = latest_value > threshold
                elif operator == "<":
                    alert_triggered = latest_value < threshold
                elif operator == ">=":
                    alert_triggered = latest_value >= threshold
                elif operator == "<=":
                    alert_triggered = latest_value <= threshold
                elif operator == "==":
                    alert_triggered = latest_value == threshold

                # Check for state change
                previous_state = self.alert_states.get(rule_name, False)

                if alert_triggered and not previous_state:
                    # Alert fired
                    await self._fire_alert(
                        rule_name, metric_name, latest_value, threshold
                    )
                    self.alert_states[rule_name] = True
                elif not alert_triggered and previous_state:
                    # Alert resolved
                    await self._resolve_alert(rule_name, metric_name, latest_value)
                    self.alert_states[rule_name] = False

            except Exception as e:
                logging.exception(f"Alert checking error for {rule_name}: {e}")

    async def _fire_alert(
        self, rule_name: str, metric_name: str, current_value: float, threshold: float
    ):
        """Fire alert."""
        logging.warning(
            f"ALERT FIRED: {rule_name} - {metric_name} = {current_value} "
            f"(threshold: {threshold})"
        )

        # In practice, this would send notifications (email, Slack, PagerDuty, etc.)

    async def _resolve_alert(
        self, rule_name: str, metric_name: str, current_value: float
    ):
        """Resolve alert."""
        logging.info(f"ALERT RESOLVED: {rule_name} - {metric_name} = {current_value}")

    def get_metrics_summary(
        self, metric_name: str, window_minutes: int = 60
    ) -> builtins.dict[str, Any]:
        """Get metrics summary for a time window."""
        metrics_data = self.monitoring_data.get(metric_name, deque())

        if not metrics_data:
            return {}

        # Filter to time window
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        recent_metrics = [m for m in metrics_data if m["timestamp"] >= cutoff_time]

        if not recent_metrics:
            return {}

        values = [m["value"] for m in recent_metrics]

        return {
            "metric_name": metric_name,
            "window_minutes": window_minutes,
            "count": len(values),
            "mean": np.mean(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "latest": values[-1] if values else None,
            "trend": "increasing"
            if len(values) >= 2 and values[-1] > values[0]
            else "decreasing",
        }


def create_ml_platform() -> builtins.dict[str, Any]:
    """Create complete ML platform."""
    model_registry = ModelRegistry()
    feature_store = FeatureStore()
    model_server = ModelServer(model_registry, feature_store)
    ab_test_manager = ABTestManager(model_server)
    observability = MLObservability()

    return {
        "model_registry": model_registry,
        "feature_store": feature_store,
        "model_server": model_server,
        "ab_test_manager": ab_test_manager,
        "observability": observability,
    }
