use std::collections::BTreeMap;
use std::sync::Arc;

use async_trait::async_trait;
use mmf_core::{ErrorCode, MmfError};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::RwLock;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum HostingEnvironment {
    Local,
    SelfHosted,
    Aws,
    GoogleCloud,
    Azure,
    Kubernetes,
    Docker,
    Unknown,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SecretBackendKind {
    Vault,
    AwsSecretsManager,
    AzureKeyVault,
    GcpSecretManager,
    Kubernetes,
    Environment,
    File,
    Memory,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ConfigurationStrategy {
    Hierarchical,
    Explicit,
    Fallback,
    AutoDetect,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DeploymentEnvironment {
    Development,
    Test,
    Beta,
    Staging,
    Production,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SecretMetadata {
    pub created_at_ms: u64,
    pub expires_at_ms: Option<u64>,
    pub rotation_interval_ms: Option<u64>,
    pub last_rotated_ms: Option<u64>,
    #[serde(default)]
    pub tags: BTreeMap<String, String>,
    pub backend: SecretBackendKind,
    pub encrypted: bool,
}

impl SecretMetadata {
    pub fn validate(&self) -> Result<(), MmfError> {
        if self
            .expires_at_ms
            .is_some_and(|expires| expires <= self.created_at_ms)
            || self.rotation_interval_ms == Some(0)
            || self
                .last_rotated_ms
                .is_some_and(|rotated| rotated < self.created_at_ms)
        {
            return Err(MmfError::new(
                ErrorCode::Configuration,
                "secret metadata timestamps are invalid",
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn expired(&self, now_ms: u64) -> bool {
        self.expires_at_ms.is_some_and(|expires| expires <= now_ms)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ConfigurationContext {
    pub service_name: String,
    pub environment: DeploymentEnvironment,
    pub config_dir: Option<String>,
    pub plugins_dir: Option<String>,
    pub enable_secrets: bool,
    pub enable_hot_reload: bool,
    pub enable_plugins: bool,
    pub cache_ttl_ms: u64,
    pub strategy: ConfigurationStrategy,
}

impl ConfigurationContext {
    pub fn validate(&self) -> Result<(), MmfError> {
        if self.service_name.trim().is_empty() || self.cache_ttl_ms == 0 {
            return Err(MmfError::new(
                ErrorCode::Configuration,
                "configuration service name and cache TTL are required",
            ));
        }
        if self.environment == DeploymentEnvironment::Production && self.enable_hot_reload {
            return Err(MmfError::new(
                ErrorCode::Configuration,
                "production configuration hot reload requires an explicit deployment mechanism",
            ));
        }
        Ok(())
    }
}

#[async_trait]
pub trait SecretBackend: Send + Sync {
    async fn get_secret(&self, key: &str, now_ms: u64) -> Result<Option<String>, MmfError>;
    async fn set_secret(
        &self,
        key: &str,
        value: String,
        metadata: SecretMetadata,
    ) -> Result<(), MmfError>;
    async fn delete_secret(&self, key: &str) -> Result<bool, MmfError>;
    async fn list_secrets(&self, prefix: &str) -> Result<Vec<String>, MmfError>;
    async fn health_check(&self) -> Result<(), MmfError>;
}

#[async_trait]
pub trait ConfigurationBackend: Send + Sync {
    async fn load_config(&self, name: &str) -> Result<Value, MmfError>;
    async fn save_config(&self, name: &str, config: Value) -> Result<(), MmfError>;
}

#[derive(Clone, Default)]
pub struct InMemorySecretBackend {
    secrets: Arc<RwLock<BTreeMap<String, (String, SecretMetadata)>>>,
}

#[async_trait]
impl SecretBackend for InMemorySecretBackend {
    async fn get_secret(&self, key: &str, now_ms: u64) -> Result<Option<String>, MmfError> {
        let secrets = self.secrets.read().await;
        let Some((value, metadata)) = secrets.get(key) else {
            return Ok(None);
        };
        if metadata.expired(now_ms) {
            return Err(MmfError::new(ErrorCode::Unauthorized, "secret has expired"));
        }
        Ok(Some(value.clone()))
    }

    async fn set_secret(
        &self,
        key: &str,
        value: String,
        metadata: SecretMetadata,
    ) -> Result<(), MmfError> {
        if key.trim().is_empty() || value.is_empty() {
            return Err(MmfError::new(
                ErrorCode::InvalidInput,
                "secret key and value are required",
            ));
        }
        metadata.validate()?;
        self.secrets
            .write()
            .await
            .insert(key.into(), (value, metadata));
        Ok(())
    }

    async fn delete_secret(&self, key: &str) -> Result<bool, MmfError> {
        Ok(self.secrets.write().await.remove(key).is_some())
    }

    async fn list_secrets(&self, prefix: &str) -> Result<Vec<String>, MmfError> {
        Ok(self
            .secrets
            .read()
            .await
            .keys()
            .filter(|key| key.starts_with(prefix))
            .cloned()
            .collect())
    }

    async fn health_check(&self) -> Result<(), MmfError> {
        Ok(())
    }
}

#[must_use]
pub fn detect_hosting_environment(variables: &BTreeMap<String, String>) -> HostingEnvironment {
    if variables.contains_key("AWS_REGION")
        || variables.contains_key("AWS_EXECUTION_ENV")
        || variables.contains_key("AWS_LAMBDA_FUNCTION_NAME")
    {
        HostingEnvironment::Aws
    } else if variables.contains_key("GOOGLE_CLOUD_PROJECT")
        || variables.contains_key("GCLOUD_PROJECT")
        || variables.contains_key("GCP_PROJECT")
    {
        HostingEnvironment::GoogleCloud
    } else if variables.contains_key("AZURE_CLIENT_ID")
        || variables.contains_key("AZURE_SUBSCRIPTION_ID")
        || variables.contains_key("AZURE_HTTP_USER_AGENT")
        || variables.contains_key("WEBSITE_INSTANCE_ID")
    {
        HostingEnvironment::Azure
    } else if variables.contains_key("KUBERNETES_SERVICE_HOST") {
        HostingEnvironment::Kubernetes
    } else if variables.contains_key("DOTNET_RUNNING_IN_CONTAINER")
        || variables.contains_key("MMF_DOCKER")
    {
        HostingEnvironment::Docker
    } else if variables
        .get("MMF_SELF_HOSTED")
        .is_some_and(|value| value == "true")
    {
        HostingEnvironment::SelfHosted
    } else if variables
        .get("MMF_ENV")
        .or_else(|| variables.get("ENVIRONMENT"))
        .is_some_and(|value| {
            matches!(
                value.to_ascii_lowercase().as_str(),
                "local" | "development" | "dev"
            )
        })
    {
        HostingEnvironment::Local
    } else {
        HostingEnvironment::SelfHosted
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        hosting: Vec<HostingCase>,
        secret: SecretCase,
    }

    #[derive(Deserialize)]
    struct HostingCase {
        variables: BTreeMap<String, String>,
        expected: HostingEnvironment,
    }

    #[derive(Deserialize)]
    #[allow(clippy::struct_field_names)]
    struct SecretCase {
        created_at_ms: u64,
        expires_at_ms: u64,
        valid_at_ms: u64,
        expired_at_ms: u64,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/config-runtime-behavior.json"
        ))
        .expect("valid config/runtime fixture")
    }

    #[test]
    fn hosting_detection_matches_the_shared_contract() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        for case in fixture.hosting {
            assert_eq!(detect_hosting_environment(&case.variables), case.expected);
        }
    }

    #[tokio::test]
    async fn expired_secrets_fail_closed() {
        let case = fixture().secret;
        let backend = InMemorySecretBackend::default();
        backend
            .set_secret(
                "database/password",
                "opaque".into(),
                SecretMetadata {
                    created_at_ms: case.created_at_ms,
                    expires_at_ms: Some(case.expires_at_ms),
                    rotation_interval_ms: None,
                    last_rotated_ms: None,
                    tags: BTreeMap::new(),
                    backend: SecretBackendKind::Memory,
                    encrypted: true,
                },
            )
            .await
            .expect("set secret");
        assert_eq!(
            backend
                .get_secret("database/password", case.valid_at_ms)
                .await
                .expect("valid secret"),
            Some("opaque".into())
        );
        assert!(
            backend
                .get_secret("database/password", case.expired_at_ms)
                .await
                .is_err()
        );
    }
}
