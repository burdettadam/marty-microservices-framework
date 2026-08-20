//! Layered, atomically reloadable service configuration with fail-closed secrets.

#![forbid(unsafe_code)]

use std::{
    collections::BTreeMap,
    str::FromStr,
    sync::{Arc, RwLock},
};

use mmf_core::{ErrorCode, MmfError};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ConfigFormat {
    Json,
    Toml,
}

#[derive(Clone, Debug)]
pub struct ConfigLayer {
    pub name: String,
    pub value: Value,
}

impl ConfigLayer {
    pub fn parse(
        name: impl Into<String>,
        format: ConfigFormat,
        source: &str,
    ) -> Result<Self, MmfError> {
        let value = match format {
            ConfigFormat::Json => serde_json::from_str(source).map_err(|error| {
                MmfError::new(ErrorCode::Configuration, "invalid JSON configuration")
                    .with_detail("cause", error.to_string())
            })?,
            ConfigFormat::Toml => {
                let parsed = toml::from_str::<toml::Value>(source).map_err(|error| {
                    MmfError::new(ErrorCode::Configuration, "invalid TOML configuration")
                        .with_detail("cause", error.to_string())
                })?;
                serde_json::to_value(parsed).map_err(|error| {
                    MmfError::new(ErrorCode::Configuration, "TOML conversion failed")
                        .with_detail("cause", error.to_string())
                })?
            }
        };
        if !value.is_object() {
            return Err(MmfError::new(
                ErrorCode::Configuration,
                "configuration root must be an object",
            ));
        }
        Ok(Self {
            name: name.into(),
            value,
        })
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ConfigSnapshot {
    pub revision: u64,
    pub value: Value,
    pub layers: Vec<String>,
}

#[derive(Clone, Debug, Default)]
pub struct LayeredConfig {
    layers: Vec<ConfigLayer>,
}

impl LayeredConfig {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    #[must_use]
    pub fn with_layer(mut self, layer: ConfigLayer) -> Self {
        self.layers.push(layer);
        self
    }

    pub fn with_environment<I, K, V>(mut self, prefix: &str, variables: I) -> Result<Self, MmfError>
    where
        I: IntoIterator<Item = (K, V)>,
        K: AsRef<str>,
        V: AsRef<str>,
    {
        let mut root = Value::Object(Map::new());
        for (key, raw_value) in variables {
            let key = key.as_ref();
            let Some(path) = key.strip_prefix(prefix) else {
                continue;
            };
            let segments = path
                .split("__")
                .filter(|segment| !segment.is_empty())
                .map(str::to_ascii_lowercase)
                .collect::<Vec<_>>();
            if segments.is_empty() {
                return Err(MmfError::new(
                    ErrorCode::Configuration,
                    "environment override has an empty path",
                ));
            }
            set_path(&mut root, &segments, parse_scalar(raw_value.as_ref()))?;
        }
        self.layers.push(ConfigLayer {
            name: "environment".to_owned(),
            value: root,
        });
        Ok(self)
    }

    #[must_use]
    pub fn build(self, revision: u64) -> ConfigSnapshot {
        let mut merged = Value::Object(Map::new());
        let mut names = Vec::with_capacity(self.layers.len());
        for layer in self.layers {
            merge_value(&mut merged, layer.value);
            names.push(layer.name);
        }
        ConfigSnapshot {
            revision,
            value: merged,
            layers: names,
        }
    }
}

#[derive(Clone, Debug)]
pub struct ConfigStore {
    snapshot: Arc<RwLock<ConfigSnapshot>>,
}

impl ConfigStore {
    #[must_use]
    pub fn new(initial: ConfigSnapshot) -> Self {
        Self {
            snapshot: Arc::new(RwLock::new(initial)),
        }
    }

    pub fn snapshot(&self) -> Result<ConfigSnapshot, MmfError> {
        self.snapshot
            .read()
            .map(|snapshot| snapshot.clone())
            .map_err(|_| MmfError::new(ErrorCode::Internal, "configuration lock poisoned"))
    }

    pub fn replace(&self, mut next: ConfigSnapshot) -> Result<ConfigSnapshot, MmfError> {
        let mut current = self
            .snapshot
            .write()
            .map_err(|_| MmfError::new(ErrorCode::Internal, "configuration lock poisoned"))?;
        if next.revision <= current.revision {
            return Err(MmfError::new(
                ErrorCode::Conflict,
                "configuration revision must increase",
            ));
        }
        std::mem::swap(&mut *current, &mut next);
        Ok(next)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SecretReference {
    pub provider: String,
    pub key: String,
}

impl FromStr for SecretReference {
    type Err = MmfError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let inner = value
            .strip_prefix("${SECRET:")
            .and_then(|value| value.strip_suffix('}'))
            .ok_or_else(|| MmfError::new(ErrorCode::Configuration, "invalid secret reference"))?;
        let (provider, key) = inner.split_once(':').ok_or_else(|| {
            MmfError::new(
                ErrorCode::Configuration,
                "secret provider or key is missing",
            )
        })?;
        if provider.is_empty()
            || key.is_empty()
            || !provider.chars().all(|character| {
                character.is_ascii_alphanumeric() || matches!(character, '-' | '_')
            })
        {
            return Err(MmfError::new(
                ErrorCode::Configuration,
                "secret reference contains an invalid provider or key",
            ));
        }
        Ok(Self {
            provider: provider.to_owned(),
            key: key.to_owned(),
        })
    }
}

pub trait SecretResolver: Send + Sync {
    fn resolve(&self, key: &str) -> Result<String, MmfError>;
}

#[derive(Default)]
pub struct SecretRegistry {
    providers: BTreeMap<String, Arc<dyn SecretResolver>>,
}

impl SecretRegistry {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(
        &mut self,
        provider: impl Into<String>,
        resolver: Arc<dyn SecretResolver>,
    ) -> Result<(), MmfError> {
        let provider = provider.into();
        if self.providers.insert(provider.clone(), resolver).is_some() {
            return Err(MmfError::new(
                ErrorCode::Conflict,
                format!("secret provider {provider} is already registered"),
            ));
        }
        Ok(())
    }

    pub fn resolve_value(&self, value: &Value) -> Result<Value, MmfError> {
        match value {
            Value::String(candidate) if candidate.starts_with("${SECRET:") => {
                let reference = SecretReference::from_str(candidate)?;
                let resolver = self.providers.get(&reference.provider).ok_or_else(|| {
                    MmfError::new(
                        ErrorCode::DependencyUnavailable,
                        format!("secret provider {} is unavailable", reference.provider),
                    )
                })?;
                resolver.resolve(&reference.key).map(Value::String)
            }
            Value::Array(values) => values
                .iter()
                .map(|value| self.resolve_value(value))
                .collect::<Result<Vec<_>, _>>()
                .map(Value::Array),
            Value::Object(values) => values
                .iter()
                .map(|(key, value)| Ok((key.clone(), self.resolve_value(value)?)))
                .collect::<Result<Map<_, _>, MmfError>>()
                .map(Value::Object),
            _ => Ok(value.clone()),
        }
    }
}

fn parse_scalar(value: &str) -> Value {
    serde_json::from_str(value).unwrap_or_else(|_| Value::String(value.to_owned()))
}

fn merge_value(target: &mut Value, overlay: Value) {
    match (target, overlay) {
        (Value::Object(target), Value::Object(overlay)) => {
            for (key, value) in overlay {
                merge_value(target.entry(key).or_insert(Value::Null), value);
            }
        }
        (target, overlay) => *target = overlay,
    }
}

fn set_path(target: &mut Value, path: &[String], value: Value) -> Result<(), MmfError> {
    let (head, tail) = path
        .split_first()
        .ok_or_else(|| MmfError::new(ErrorCode::Configuration, "configuration path is empty"))?;
    let object = target.as_object_mut().ok_or_else(|| {
        MmfError::new(
            ErrorCode::Configuration,
            "configuration path crosses a scalar",
        )
    })?;
    if tail.is_empty() {
        object.insert(head.clone(), value);
        return Ok(());
    }
    let child = object
        .entry(head.clone())
        .or_insert_with(|| Value::Object(Map::new()));
    set_path(child, tail, value)
}

#[cfg(test)]
mod tests {
    use std::{str::FromStr, sync::Arc};

    use mmf_core::{ErrorCode, MmfError};
    use serde_json::json;

    use super::{
        ConfigFormat, ConfigLayer, LayeredConfig, SecretReference, SecretRegistry, SecretResolver,
    };

    struct TestSecrets;

    impl SecretResolver for TestSecrets {
        fn resolve(&self, key: &str) -> Result<String, MmfError> {
            match key {
                "database/password" => Ok("resolved-secret".to_owned()),
                _ => Err(MmfError::new(ErrorCode::NotFound, "secret not found")),
            }
        }
    }

    #[test]
    fn later_layers_and_environment_override_nested_values() {
        let base = ConfigLayer::parse(
            "base",
            ConfigFormat::Toml,
            "[server]\nport = 8000\n[feature]\nenabled = false",
        )
        .expect("base");
        let environment = ConfigLayer::parse(
            "beta",
            ConfigFormat::Json,
            r#"{"feature":{"enabled":true}}"#,
        )
        .expect("beta");
        let snapshot = LayeredConfig::new()
            .with_layer(base)
            .with_layer(environment)
            .with_environment("MMF__", [("MMF__SERVER__PORT", "9000")])
            .expect("environment")
            .build(1);
        assert_eq!(snapshot.value["server"]["port"], 9000);
        assert_eq!(snapshot.value["feature"]["enabled"], true);
        assert_eq!(snapshot.layers, ["base", "beta", "environment"]);
    }

    #[test]
    fn secrets_resolve_through_registered_provider_and_missing_provider_fails_closed() {
        let reference = SecretReference::from_str("${SECRET:vault:database/password}")
            .expect("secret reference");
        assert_eq!(reference.provider, "vault");

        let value = json!({"password": "${SECRET:vault:database/password}"});
        let empty = SecretRegistry::new();
        assert_eq!(
            empty
                .resolve_value(&value)
                .expect_err("missing provider")
                .code,
            ErrorCode::DependencyUnavailable
        );

        let mut registry = SecretRegistry::new();
        registry
            .register("vault", Arc::new(TestSecrets))
            .expect("register provider");
        assert_eq!(
            registry.resolve_value(&value).expect("resolved")["password"],
            "resolved-secret"
        );
    }
}
