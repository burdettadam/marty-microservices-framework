use async_trait::async_trait;

use crate::{
    Deployment, DeploymentConfig, InfrastructureAsCodeConfig, PipelineConfig, PlatformError,
    ServiceInstance, ServiceQuery,
};

#[async_trait]
pub trait ServiceRegistry: Send + Sync {
    async fn register(&self, instance: &ServiceInstance) -> Result<(), PlatformError>;
    async fn deregister(&self, service: &str, instance_id: &str) -> Result<bool, PlatformError>;
    async fn discover(&self, query: &ServiceQuery) -> Result<Vec<ServiceInstance>, PlatformError>;
    async fn heartbeat(
        &self,
        service: &str,
        instance_id: &str,
        now_ms: u64,
    ) -> Result<(), PlatformError>;
    async fn healthy(&self) -> Result<bool, PlatformError>;
}

#[async_trait]
pub trait ConsulRegistry: ServiceRegistry {}

#[async_trait]
pub trait DnsRegistry: ServiceRegistry {}

#[async_trait]
pub trait UpstreamClient: Send + Sync {
    async fn send(
        &self,
        instance: &ServiceInstance,
        request: crate::GatewayRequest,
    ) -> Result<crate::GatewayResponse, PlatformError>;
}

#[async_trait]
pub trait DeploymentProvider: Send + Sync {
    async fn deploy(&self, config: DeploymentConfig) -> Result<Deployment, PlatformError>;
    async fn rollback(&self, deployment_id: &str) -> Result<Deployment, PlatformError>;
    async fn scale(&self, deployment_id: &str, replicas: u32) -> Result<Deployment, PlatformError>;
    async fn status(&self, deployment_id: &str) -> Result<Deployment, PlatformError>;
}

#[async_trait]
pub trait InfrastructureProviderPort: Send + Sync {
    async fn plan(&self, config: &InfrastructureAsCodeConfig) -> Result<String, PlatformError>;
    async fn apply(&self, config: &InfrastructureAsCodeConfig) -> Result<String, PlatformError>;
    async fn destroy(&self, config: &InfrastructureAsCodeConfig) -> Result<String, PlatformError>;
    async fn state(&self, config: &InfrastructureAsCodeConfig) -> Result<String, PlatformError>;
}

#[async_trait]
pub trait PipelineProviderPort: Send + Sync {
    async fn generate(&self, config: &PipelineConfig) -> Result<String, PlatformError>;
    async fn execute(&self, config: &PipelineConfig) -> Result<String, PlatformError>;
    async fn cancel(&self, execution_id: &str) -> Result<(), PlatformError>;
}

#[async_trait]
pub trait KubernetesDeploymentProvider: DeploymentProvider {}

#[async_trait]
pub trait TerraformInfrastructureProvider: InfrastructureProviderPort {}

#[async_trait]
pub trait GitHubActionsPipelineProvider: PipelineProviderPort {}
