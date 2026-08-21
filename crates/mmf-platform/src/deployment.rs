use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::PlatformError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DeploymentStatus {
    Pending,
    Preparing,
    Deploying,
    Deployed,
    Scaling,
    RollingBack,
    RolledBack,
    Failed,
    Cancelled,
    Terminated,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DeploymentStrategy {
    RollingUpdate,
    Recreate,
    BlueGreen,
    Canary,
    #[serde(rename = "a_b_testing")]
    AbTesting,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EnvironmentType {
    Development,
    Testing,
    Staging,
    Beta,
    Production,
    Sandbox,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InfrastructureProvider {
    Kubernetes,
    DockerSwarm,
    AwsEcs,
    AwsEks,
    AzureAks,
    GcpGke,
    SelfHosted,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InfrastructureAsCodeProvider {
    Terraform,
    OpenTofu,
    Pulumi,
    CloudFormation,
    Bicep,
    Arm,
    Cdk,
    Kubernetes,
    Helm,
    Kustomize,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PipelineProvider {
    GitHubActions,
    GitLabCi,
    Jenkins,
    AzureDevOps,
    ArgoCd,
    Flux,
    Tekton,
    ArgoWorkflows,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DeploymentTarget {
    pub provider: InfrastructureProvider,
    pub environment: EnvironmentType,
    pub cluster: String,
    pub namespace: String,
    pub region: Option<String>,
    pub account_id: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ResourceRequirements {
    pub cpu_request_millicores: u32,
    pub cpu_limit_millicores: u32,
    pub memory_request_mebibytes: u32,
    pub memory_limit_mebibytes: u32,
    pub minimum_replicas: u32,
    pub maximum_replicas: u32,
}

impl ResourceRequirements {
    pub fn validate(&self) -> Result<(), PlatformError> {
        if self.cpu_request_millicores == 0
            || self.memory_request_mebibytes == 0
            || self.minimum_replicas == 0
            || self.cpu_limit_millicores < self.cpu_request_millicores
            || self.memory_limit_mebibytes < self.memory_request_mebibytes
            || self.maximum_replicas < self.minimum_replicas
        {
            return Err(PlatformError::InvalidConfiguration(
                "deployment resource requests, limits, or replica bounds are invalid".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DeploymentHealthCheck {
    pub path: String,
    pub port: u16,
    pub initial_delay_seconds: u32,
    pub period_seconds: u32,
    pub timeout_seconds: u32,
    pub failure_threshold: u32,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DeploymentConfig {
    pub service_name: String,
    pub image: String,
    pub image_digest: Option<String>,
    pub target: DeploymentTarget,
    pub strategy: DeploymentStrategy,
    pub resources: ResourceRequirements,
    #[serde(default)]
    pub ports: BTreeMap<String, u16>,
    #[serde(default)]
    pub environment: BTreeMap<String, String>,
    #[serde(default)]
    pub secret_references: BTreeMap<String, String>,
    #[serde(default)]
    pub labels: BTreeMap<String, String>,
    pub readiness: DeploymentHealthCheck,
    pub liveness: DeploymentHealthCheck,
    pub service_account: Option<String>,
}

impl DeploymentConfig {
    pub fn validate(&self) -> Result<(), PlatformError> {
        self.resources.validate()?;
        if self.service_name.trim().is_empty()
            || self.image.trim().is_empty()
            || self.target.namespace.trim().is_empty()
            || self.ports.is_empty()
        {
            return Err(PlatformError::InvalidConfiguration(
                "deployment service, image, namespace, and ports are required".into(),
            ));
        }
        if self.target.environment == EnvironmentType::Production && self.image_digest.is_none() {
            return Err(PlatformError::InvalidConfiguration(
                "production images must be pinned by digest".into(),
            ));
        }
        Ok(())
    }

    pub fn kubernetes_manifest(&self) -> Result<String, PlatformError> {
        self.validate()?;
        let replicas = self.resources.minimum_replicas;
        let image = self.image_digest.as_ref().map_or_else(
            || self.image.clone(),
            |digest| format!("{}@{digest}", self.image),
        );
        let labels = self
            .labels
            .iter()
            .map(|(key, value)| format!("    {key}: {value}"))
            .collect::<Vec<_>>()
            .join("\n");
        let ports = self
            .ports
            .iter()
            .map(|(name, port)| format!("        - name: {name}\n          containerPort: {port}"))
            .collect::<Vec<_>>()
            .join("\n");
        let environment = self
            .environment
            .iter()
            .map(|(name, value)| format!("        - name: {name}\n          value: {value:?}"))
            .collect::<Vec<_>>()
            .join("\n");
        Ok(format!(
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {name}\n  namespace: {namespace}\n  labels:\n    app.kubernetes.io/name: {name}\n{labels}\nspec:\n  replicas: {replicas}\n  selector:\n    matchLabels:\n      app.kubernetes.io/name: {name}\n  template:\n    metadata:\n      labels:\n        app.kubernetes.io/name: {name}\n    spec:\n      containers:\n      - name: {name}\n        image: {image}\n        ports:\n{ports}\n        env:\n{environment}\n        resources:\n          requests:\n            cpu: {cpu_request}m\n            memory: {memory_request}Mi\n          limits:\n            cpu: {cpu_limit}m\n            memory: {memory_limit}Mi\n        readinessProbe:\n          httpGet:\n            path: {readiness_path}\n            port: {readiness_port}\n        livenessProbe:\n          httpGet:\n            path: {liveness_path}\n            port: {liveness_port}\n",
            name = self.service_name,
            namespace = self.target.namespace,
            cpu_request = self.resources.cpu_request_millicores,
            memory_request = self.resources.memory_request_mebibytes,
            cpu_limit = self.resources.cpu_limit_millicores,
            memory_limit = self.resources.memory_limit_mebibytes,
            readiness_path = self.readiness.path,
            readiness_port = self.readiness.port,
            liveness_path = self.liveness.path,
            liveness_port = self.liveness.port,
        ))
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DeploymentEvent {
    pub event_type: String,
    pub message: String,
    pub timestamp_ms: u64,
    #[serde(default)]
    pub details: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Deployment {
    pub id: String,
    pub config: DeploymentConfig,
    pub status: DeploymentStatus,
    pub created_at_ms: u64,
    pub updated_at_ms: u64,
    #[serde(default)]
    pub events: Vec<DeploymentEvent>,
    pub revision: u64,
}

impl Deployment {
    pub fn new(config: DeploymentConfig, now_ms: u64) -> Result<Self, PlatformError> {
        config.validate()?;
        Ok(Self {
            id: Uuid::new_v4().to_string(),
            config,
            status: DeploymentStatus::Pending,
            created_at_ms: now_ms,
            updated_at_ms: now_ms,
            events: Vec::new(),
            revision: 0,
        })
    }

    pub fn transition(
        &mut self,
        expected_revision: u64,
        status: DeploymentStatus,
        now_ms: u64,
    ) -> Result<(), PlatformError> {
        if self.revision != expected_revision {
            return Err(PlatformError::Conflict(format!(
                "deployment revision expected {expected_revision}, actual {}",
                self.revision
            )));
        }
        if !valid_transition(self.status, status) {
            return Err(PlatformError::Conflict(format!(
                "invalid deployment transition {:?} -> {status:?}",
                self.status
            )));
        }
        self.status = status;
        self.updated_at_ms = now_ms;
        self.revision = self.revision.saturating_add(1);
        Ok(())
    }
}

const fn valid_transition(current: DeploymentStatus, next: DeploymentStatus) -> bool {
    matches!(
        (current, next),
        (
            DeploymentStatus::Pending,
            DeploymentStatus::Preparing | DeploymentStatus::Cancelled
        ) | (
            DeploymentStatus::Preparing,
            DeploymentStatus::Deploying | DeploymentStatus::Failed
        ) | (
            DeploymentStatus::Deploying | DeploymentStatus::Scaling,
            DeploymentStatus::Deployed | DeploymentStatus::Failed
        ) | (
            DeploymentStatus::Deployed,
            DeploymentStatus::Scaling
                | DeploymentStatus::RollingBack
                | DeploymentStatus::Terminated
                | DeploymentStatus::Failed
        ) | (
            DeploymentStatus::RollingBack,
            DeploymentStatus::RolledBack | DeploymentStatus::Failed
        )
    )
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct InfrastructureAsCodeConfig {
    pub provider: InfrastructureAsCodeProvider,
    pub working_directory: String,
    pub state_backend: Option<String>,
    #[serde(default)]
    pub variables: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct PipelineConfig {
    pub provider: PipelineProvider,
    pub repository: String,
    pub branch: String,
    pub environment: EnvironmentType,
    pub requires_approval: bool,
    pub deployment: DeploymentConfig,
}
