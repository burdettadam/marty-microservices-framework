use std::collections::BTreeMap;
use std::sync::{Arc, RwLock};

use crate::{Plugin, PluginError, PluginMetadata, ServiceDefinition, ServiceStatus};

#[derive(Clone)]
pub struct RegisteredPlugin {
    pub plugin: Arc<dyn Plugin>,
    pub metadata: PluginMetadata,
}

#[derive(Default)]
pub struct PluginRegistry {
    plugins: RwLock<BTreeMap<String, RegisteredPlugin>>,
}
impl PluginRegistry {
    pub fn register(&self, plugin: Arc<dyn Plugin>) -> Result<(), PluginError> {
        let metadata = plugin.metadata();
        metadata.validate()?;
        let mut plugins = self
            .plugins
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if plugins.contains_key(&metadata.name) {
            return Err(PluginError::Conflict(metadata.name));
        }
        plugins.insert(metadata.name.clone(), RegisteredPlugin { plugin, metadata });
        Ok(())
    }
    pub fn unregister(&self, name: &str) -> Result<RegisteredPlugin, PluginError> {
        self.plugins
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .remove(name)
            .ok_or_else(|| PluginError::NotFound(name.into()))
    }
    #[must_use]
    pub fn get(&self, name: &str) -> Option<RegisteredPlugin> {
        self.plugins
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(name)
            .cloned()
    }
    #[must_use]
    pub fn all(&self) -> BTreeMap<String, RegisteredPlugin> {
        self.plugins
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone()
    }
    pub fn dependency_order(&self) -> Result<Vec<String>, PluginError> {
        let plugins = self
            .plugins
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let mut marks = BTreeMap::new();
        let mut order = Vec::new();
        for name in plugins.keys() {
            visit(name, &plugins, &mut marks, &mut order)?;
        }
        Ok(order)
    }
}
fn visit(
    name: &str,
    plugins: &BTreeMap<String, RegisteredPlugin>,
    marks: &mut BTreeMap<String, u8>,
    order: &mut Vec<String>,
) -> Result<(), PluginError> {
    match marks.get(name) {
        Some(2) => return Ok(()),
        Some(1) => {
            return Err(PluginError::Dependency(format!(
                "plugin dependency cycle at {name}"
            )));
        }
        _ => {}
    }
    let plugin = plugins
        .get(name)
        .ok_or_else(|| PluginError::Dependency(format!("missing plugin dependency: {name}")))?;
    marks.insert(name.into(), 1);
    for dependency in &plugin.metadata.dependencies {
        if !plugins.contains_key(dependency) {
            return Err(PluginError::Dependency(format!(
                "{} requires missing plugin {dependency}",
                plugin.metadata.name
            )));
        }
        visit(dependency, plugins, marks, order)?;
    }
    marks.insert(name.into(), 2);
    order.push(name.into());
    Ok(())
}

#[derive(Clone, Debug)]
pub struct RegisteredService {
    pub definition: ServiceDefinition,
    pub status: ServiceStatus,
}
#[derive(Default)]
pub struct ServiceRegistry {
    services: RwLock<BTreeMap<(String, String), RegisteredService>>,
}
impl ServiceRegistry {
    pub fn register(&self, plugin: &str, definition: ServiceDefinition) -> Result<(), PluginError> {
        definition.validate()?;
        let key = (plugin.into(), definition.name.clone());
        let mut services = self
            .services
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if services.contains_key(&key) {
            return Err(PluginError::Conflict(format!(
                "service {plugin}/{}",
                definition.name
            )));
        }
        services.insert(
            key,
            RegisteredService {
                definition,
                status: ServiceStatus::Inactive,
            },
        );
        Ok(())
    }
    pub fn unregister_plugin(&self, plugin: &str) {
        self.services
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .retain(|(owner, _), _| owner != plugin);
    }
    pub fn set_status(
        &self,
        plugin: &str,
        name: &str,
        status: ServiceStatus,
    ) -> Result<(), PluginError> {
        self.services
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get_mut(&(plugin.into(), name.into()))
            .ok_or_else(|| PluginError::NotFound(format!("service {plugin}/{name}")))?
            .status = status;
        Ok(())
    }
    #[must_use]
    pub fn get(&self, plugin: &str, name: &str) -> Option<RegisteredService> {
        self.services
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(&(plugin.into(), name.into()))
            .cloned()
    }
    #[must_use]
    pub fn list(&self, plugin: Option<&str>) -> BTreeMap<String, Vec<RegisteredService>> {
        let mut result: BTreeMap<String, Vec<RegisteredService>> = BTreeMap::new();
        for ((owner, _), service) in self
            .services
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .iter()
        {
            if plugin.is_none_or(|selected| selected == owner) {
                result
                    .entry(owner.clone())
                    .or_default()
                    .push(service.clone());
            }
        }
        result
    }
}
