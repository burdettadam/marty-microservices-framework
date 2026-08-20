use std::collections::BTreeMap;
use std::sync::RwLock;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{IsolationLevel, PluginError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ConfigValueType {
    String,
    Integer,
    Number,
    Boolean,
    Array,
    Object,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ConfigField {
    pub value_type: ConfigValueType,
    pub required: bool,
    pub default: Option<Value>,
    pub description: String,
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct PluginConfigSchema {
    #[serde(default)]
    pub fields: BTreeMap<String, ConfigField>,
    pub allow_extra: bool,
}
impl PluginConfigSchema {
    pub fn validate(&self, config: &BTreeMap<String, Value>) -> Result<(), PluginError> {
        for (name, field) in &self.fields {
            let value = config.get(name).or(field.default.as_ref());
            if field.required && value.is_none() {
                return Err(PluginError::InvalidInput(format!(
                    "missing required plugin config field: {name}"
                )));
            }
            if let Some(value) = value
                && !matches_type(value, field.value_type)
            {
                return Err(PluginError::InvalidInput(format!(
                    "invalid type for plugin config field: {name}"
                )));
            }
        }
        if !self.allow_extra && config.keys().any(|key| !self.fields.contains_key(key)) {
            return Err(PluginError::InvalidInput(
                "plugin config contains unknown fields".into(),
            ));
        }
        Ok(())
    }
    #[must_use]
    pub fn template(&self) -> BTreeMap<String, Value> {
        self.fields
            .iter()
            .filter_map(|(name, field)| field.default.clone().map(|value| (name.clone(), value)))
            .collect()
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct PluginPlatformConfig {
    pub plugins_enabled: bool,
    pub discovery_paths: Vec<String>,
    pub config_directory: String,
    pub auto_discovery: bool,
    pub isolation_level: IsolationLevel,
}
impl Default for PluginPlatformConfig {
    fn default() -> Self {
        Self {
            plugins_enabled: true,
            discovery_paths: vec!["./plugins".into(), "/opt/mmf/plugins".into()],
            config_directory: "./config/plugins".into(),
            auto_discovery: true,
            isolation_level: IsolationLevel::Process,
        }
    }
}

#[derive(Default)]
pub struct PluginConfigManager {
    schemas: RwLock<BTreeMap<String, PluginConfigSchema>>,
    values: RwLock<BTreeMap<(String, String), BTreeMap<String, Value>>>,
}
impl PluginConfigManager {
    pub fn register(&self, name: &str, schema: PluginConfigSchema) -> Result<(), PluginError> {
        if name.trim().is_empty() {
            return Err(PluginError::InvalidInput("plugin name is required".into()));
        }
        self.schemas
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert(name.into(), schema);
        Ok(())
    }
    pub fn update(
        &self,
        name: &str,
        key: &str,
        config: BTreeMap<String, Value>,
    ) -> Result<(), PluginError> {
        let schemas = self
            .schemas
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let schema = schemas
            .get(name)
            .ok_or_else(|| PluginError::NotFound(format!("config schema for {name}")))?;
        schema.validate(&config)?;
        drop(schemas);
        self.values
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert((name.into(), key.into()), config);
        Ok(())
    }
    pub fn get(&self, name: &str, key: &str) -> Result<BTreeMap<String, Value>, PluginError> {
        if let Some(value) = self
            .values
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(&(name.into(), key.into()))
            .cloned()
        {
            return Ok(value);
        }
        self.schemas
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(name)
            .map(PluginConfigSchema::template)
            .ok_or_else(|| PluginError::NotFound(format!("config for {name}")))
    }
    #[must_use]
    pub fn registered_plugins(&self) -> Vec<String> {
        self.schemas
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .keys()
            .cloned()
            .collect()
    }
}
fn matches_type(value: &Value, kind: ConfigValueType) -> bool {
    match kind {
        ConfigValueType::String => value.is_string(),
        ConfigValueType::Integer => value.as_i64().is_some() || value.as_u64().is_some(),
        ConfigValueType::Number => value.is_number(),
        ConfigValueType::Boolean => value.is_boolean(),
        ConfigValueType::Array => value.is_array(),
        ConfigValueType::Object => value.is_object(),
    }
}
