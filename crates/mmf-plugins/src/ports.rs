use async_trait::async_trait;
use serde_json::Value;

use crate::{
    DiscoveredPlugin, PluginContext, PluginError, PluginHealth, PluginMetadata, ServiceDefinition,
};

#[async_trait]
pub trait Plugin: Send + Sync {
    fn metadata(&self) -> PluginMetadata;
    fn service_definitions(&self) -> Vec<ServiceDefinition>;
    fn configuration_schema(&self) -> serde_json::Value {
        Value::Object(serde_json::Map::new())
    }
    async fn initialize(&self, context: &PluginContext) -> Result<(), PluginError>;
    async fn start(&self) -> Result<(), PluginError>;
    async fn stop(&self) -> Result<(), PluginError>;
    async fn cleanup(&self) -> Result<(), PluginError>;
    async fn health(&self, now_ms: u64) -> PluginHealth;
}

#[async_trait]
pub trait PluginDiscovery: Send + Sync {
    async fn discover(&self, locations: &[String]) -> Result<Vec<DiscoveredPlugin>, PluginError>;
}

#[async_trait]
pub trait PluginLoader: Send + Sync {
    async fn load(
        &self,
        discovered: &DiscoveredPlugin,
    ) -> Result<std::sync::Arc<dyn Plugin>, PluginError>;
    async fn unload(&self, plugin_name: &str) -> Result<(), PluginError>;
}

#[async_trait]
pub trait PluginEventHandler: Send + Sync {
    async fn handle(&self, event_type: &str, payload: &Value) -> Result<(), PluginError>;
}

#[async_trait]
pub trait PluginConfigProvider: Send + Sync {
    async fn load(
        &self,
        plugin_name: &str,
        key: &str,
    ) -> Result<std::collections::BTreeMap<String, Value>, PluginError>;
    async fn save(
        &self,
        plugin_name: &str,
        key: &str,
        config: &std::collections::BTreeMap<String, Value>,
    ) -> Result<(), PluginError>;
    async fn watch(&self, plugin_name: &str, key: &str) -> Result<(), PluginError>;
}
