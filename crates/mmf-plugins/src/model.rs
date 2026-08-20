use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::PluginError;

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PluginStatus {
    #[default]
    Unloaded,
    Loading,
    Loaded,
    Initializing,
    Active,
    Error,
    Stopping,
    Stopped,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ServiceStatus {
    #[default]
    Inactive,
    Starting,
    Active,
    Stopping,
    Failed,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum RouteMethod {
    Get,
    Post,
    Put,
    Delete,
    Patch,
    Head,
    Options,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum PluginKind {
    #[default]
    Service,
    GatewayMiddleware,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum IsolationLevel {
    Thread,
    #[default]
    Process,
    Container,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct PluginMetadata {
    pub name: String,
    pub version: String,
    pub description: String,
    pub author: String,
    #[serde(default)]
    pub dependencies: Vec<String>,
    pub api_version: String,
    pub min_mmf_version: String,
    #[serde(default)]
    pub keywords: Vec<String>,
    pub homepage: String,
    pub license: String,
    #[serde(default)]
    pub kind: PluginKind,
}

impl PluginMetadata {
    pub fn validate(&self) -> Result<(), PluginError> {
        if self.name.trim().is_empty() || self.version.trim().is_empty() {
            return Err(PluginError::InvalidInput(
                "plugin name and version are required".into(),
            ));
        }
        if self
            .dependencies
            .iter()
            .any(|dependency| dependency == &self.name)
        {
            return Err(PluginError::Dependency(
                "plugin cannot depend on itself".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct PluginContext {
    pub plugin_id: String,
    #[serde(default)]
    pub config: BTreeMap<String, Value>,
    #[serde(default)]
    pub capabilities: BTreeMap<String, String>,
}

#[derive(Clone, Debug, Default)]
pub struct PluginContextBuilder {
    context: PluginContext,
}
impl PluginContextBuilder {
    #[must_use]
    pub fn new(plugin_id: impl Into<String>) -> Self {
        Self {
            context: PluginContext {
                plugin_id: plugin_id.into(),
                ..PluginContext::default()
            },
        }
    }
    #[must_use]
    pub fn with_config(mut self, config: BTreeMap<String, Value>) -> Self {
        self.context.config = config;
        self
    }
    #[must_use]
    pub fn with_capability(mut self, name: impl Into<String>, provider: impl Into<String>) -> Self {
        self.context
            .capabilities
            .insert(name.into(), provider.into());
        self
    }
    pub fn build(self) -> Result<PluginContext, PluginError> {
        if self.context.plugin_id.trim().is_empty() {
            Err(PluginError::InvalidInput(
                "plugin context id is required".into(),
            ))
        } else {
            Ok(self.context)
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct RouteDefinition {
    pub path: String,
    pub method: RouteMethod,
    pub handler_name: String,
    pub description: String,
    pub auth_required: bool,
    pub rate_limit_per_minute: u64,
    pub timeout_seconds: u64,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub parameters: BTreeMap<String, Value>,
    #[serde(default)]
    pub response_model: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ServiceDefinition {
    pub name: String,
    pub description: String,
    pub version: String,
    pub endpoint: String,
    #[serde(default)]
    pub routes: Vec<RouteDefinition>,
    #[serde(default)]
    pub middleware: Vec<String>,
    #[serde(default)]
    pub dependencies: Vec<String>,
    pub health_check_path: String,
    pub metrics_enabled: bool,
    pub database_required: bool,
    #[serde(default)]
    pub methods: Vec<RouteMethod>,
    pub auth_required: bool,
    pub rate_limit_per_minute: u64,
    pub timeout_seconds: u64,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
}
impl ServiceDefinition {
    pub fn validate(&self) -> Result<(), PluginError> {
        if self.name.trim().is_empty() {
            return Err(PluginError::InvalidInput("service name is required".into()));
        }
        if self.timeout_seconds == 0 {
            return Err(PluginError::InvalidInput(
                "service timeout must be greater than zero".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct PluginHealth {
    pub plugin_name: String,
    pub status: PluginStatus,
    pub healthy: bool,
    pub detail: Option<String>,
    pub checked_at_ms: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct DiscoveredPlugin {
    pub location: String,
    pub metadata: PluginMetadata,
}
