use std::collections::BTreeMap;
use std::sync::{Arc, RwLock};

use serde_json::Value;

use crate::{
    DiscoveredPlugin, Plugin, PluginConfigManager, PluginContext, PluginDiscovery, PluginError,
    PluginEventHandler, PluginHealth, PluginLoader, PluginRegistry, PluginStatus, ServiceRegistry,
    ServiceStatus,
};

pub struct PluginManager {
    pub registry: Arc<PluginRegistry>,
    pub services: Arc<ServiceRegistry>,
    pub configs: Arc<PluginConfigManager>,
    statuses: RwLock<BTreeMap<String, PluginStatus>>,
    contexts: RwLock<BTreeMap<String, PluginContext>>,
    subscriptions: RwLock<BTreeMap<(String, String), Arc<dyn PluginEventHandler>>>,
    discovery: Option<Arc<dyn PluginDiscovery>>,
    loader: Option<Arc<dyn PluginLoader>>,
}
impl Default for PluginManager {
    fn default() -> Self {
        Self {
            registry: Arc::new(PluginRegistry::default()),
            services: Arc::new(ServiceRegistry::default()),
            configs: Arc::new(PluginConfigManager::default()),
            statuses: RwLock::new(BTreeMap::new()),
            contexts: RwLock::new(BTreeMap::new()),
            subscriptions: RwLock::new(BTreeMap::new()),
            discovery: None,
            loader: None,
        }
    }
}
impl PluginManager {
    #[must_use]
    pub fn with_providers(
        discovery: Arc<dyn PluginDiscovery>,
        loader: Arc<dyn PluginLoader>,
    ) -> Self {
        Self {
            discovery: Some(discovery),
            loader: Some(loader),
            ..Self::default()
        }
    }

    pub async fn discover(
        &self,
        locations: &[String],
    ) -> Result<Vec<DiscoveredPlugin>, PluginError> {
        self.discovery
            .as_ref()
            .ok_or_else(|| {
                PluginError::ProviderUnavailable("plugin discovery provider is required".into())
            })?
            .discover(locations)
            .await
    }

    pub async fn load_discovered(
        &self,
        discovered: &DiscoveredPlugin,
        context: PluginContext,
    ) -> Result<(), PluginError> {
        if context.plugin_id != discovered.metadata.name {
            return Err(PluginError::InvalidInput(
                "discovered plugin context id must match metadata name".into(),
            ));
        }
        let plugin = self
            .loader
            .as_ref()
            .ok_or_else(|| {
                PluginError::ProviderUnavailable("plugin loader provider is required".into())
            })?
            .load(discovered)
            .await?;
        if plugin.metadata() != discovered.metadata {
            return Err(PluginError::InvalidInput(
                "loaded plugin metadata differs from discovery metadata".into(),
            ));
        }
        self.register(plugin, context)
    }
    pub fn register(
        &self,
        plugin: Arc<dyn Plugin>,
        context: PluginContext,
    ) -> Result<(), PluginError> {
        let metadata = plugin.metadata();
        if context.plugin_id != metadata.name {
            return Err(PluginError::InvalidInput(
                "plugin context id must match metadata name".into(),
            ));
        }
        self.registry.register(plugin)?;
        self.contexts
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert(metadata.name.clone(), context);
        self.statuses
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert(metadata.name, PluginStatus::Unloaded);
        Ok(())
    }
    #[must_use]
    pub fn status(&self, name: &str) -> PluginStatus {
        self.statuses
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(name)
            .copied()
            .unwrap_or(PluginStatus::Unloaded)
    }
    #[must_use]
    pub fn list(&self) -> BTreeMap<String, PluginStatus> {
        self.statuses
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .clone()
    }
    pub async fn initialize(&self, name: &str) -> Result<(), PluginError> {
        if self.status(name) != PluginStatus::Unloaded {
            return Err(PluginError::InvalidTransition(format!(
                "{name} must be unloaded before initialization"
            )));
        }
        let registered = self
            .registry
            .get(name)
            .ok_or_else(|| PluginError::NotFound(name.into()))?;
        for dependency in &registered.metadata.dependencies {
            if !matches!(
                self.status(dependency),
                PluginStatus::Loaded | PluginStatus::Active | PluginStatus::Stopped
            ) {
                return Err(PluginError::Dependency(format!(
                    "dependency {dependency} is not initialized"
                )));
            }
        }
        self.set_status(name, PluginStatus::Initializing);
        let context = self
            .contexts
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .get(name)
            .cloned()
            .ok_or_else(|| PluginError::NotFound(format!("context for {name}")))?;
        if let Err(error) = registered.plugin.initialize(&context).await {
            self.set_status(name, PluginStatus::Error);
            return Err(error);
        }
        for service in registered.plugin.service_definitions() {
            self.services.register(name, service)?;
        }
        self.set_status(name, PluginStatus::Loaded);
        Ok(())
    }
    pub async fn initialize_all(&self) -> Result<Vec<String>, PluginError> {
        let order = self.registry.dependency_order()?;
        for name in &order {
            self.initialize(name).await?;
        }
        Ok(order)
    }
    pub async fn start(&self, name: &str) -> Result<(), PluginError> {
        if self.status(name) != PluginStatus::Loaded && self.status(name) != PluginStatus::Stopped {
            return Err(PluginError::InvalidTransition(format!(
                "{name} must be loaded or stopped before start"
            )));
        }
        let registered = self
            .registry
            .get(name)
            .ok_or_else(|| PluginError::NotFound(name.into()))?;
        for dependency in &registered.metadata.dependencies {
            if self.status(dependency) != PluginStatus::Active {
                return Err(PluginError::Dependency(format!(
                    "dependency {dependency} is not active"
                )));
            }
        }
        for service in registered.plugin.service_definitions() {
            self.services
                .set_status(name, &service.name, ServiceStatus::Starting)?;
        }
        if let Err(error) = registered.plugin.start().await {
            self.set_status(name, PluginStatus::Error);
            for service in registered.plugin.service_definitions() {
                let _ = self
                    .services
                    .set_status(name, &service.name, ServiceStatus::Failed);
            }
            return Err(error);
        }
        for service in registered.plugin.service_definitions() {
            self.services
                .set_status(name, &service.name, ServiceStatus::Active)?;
        }
        self.set_status(name, PluginStatus::Active);
        Ok(())
    }
    pub async fn start_all(&self) -> Result<Vec<String>, PluginError> {
        let order = self.registry.dependency_order()?;
        for name in &order {
            self.start(name).await?;
        }
        Ok(order)
    }
    pub async fn stop(&self, name: &str) -> Result<(), PluginError> {
        if self.status(name) != PluginStatus::Active {
            return Ok(());
        }
        for (dependent, registered) in self.registry.all() {
            if registered
                .metadata
                .dependencies
                .iter()
                .any(|dependency| dependency == name)
                && self.status(&dependent) == PluginStatus::Active
            {
                return Err(PluginError::Dependency(format!(
                    "active plugin {dependent} depends on {name}"
                )));
            }
        }
        let registered = self
            .registry
            .get(name)
            .ok_or_else(|| PluginError::NotFound(name.into()))?;
        self.set_status(name, PluginStatus::Stopping);
        for service in registered.plugin.service_definitions() {
            self.services
                .set_status(name, &service.name, ServiceStatus::Stopping)?;
        }
        if let Err(error) = registered.plugin.stop().await {
            self.set_status(name, PluginStatus::Error);
            return Err(error);
        }
        for service in registered.plugin.service_definitions() {
            self.services
                .set_status(name, &service.name, ServiceStatus::Inactive)?;
        }
        self.set_status(name, PluginStatus::Stopped);
        Ok(())
    }
    pub async fn stop_all(&self) -> Result<Vec<String>, PluginError> {
        let mut order = self.registry.dependency_order()?;
        order.reverse();
        for name in &order {
            self.stop(name).await?;
        }
        Ok(order)
    }
    pub async fn unload(&self, name: &str) -> Result<(), PluginError> {
        if self.status(name) == PluginStatus::Active {
            return Err(PluginError::InvalidTransition(format!(
                "active plugin {name} must be stopped before unload"
            )));
        }
        for (dependent, registered) in self.registry.all() {
            if dependent != name
                && registered
                    .metadata
                    .dependencies
                    .iter()
                    .any(|dependency| dependency == name)
            {
                return Err(PluginError::Dependency(format!(
                    "registered plugin {dependent} depends on {name}"
                )));
            }
        }
        let registered = self
            .registry
            .get(name)
            .ok_or_else(|| PluginError::NotFound(name.into()))?;
        registered.plugin.cleanup().await?;
        if let Some(loader) = &self.loader {
            loader.unload(name).await?;
        }
        self.registry.unregister(name)?;
        self.services.unregister_plugin(name);
        self.contexts
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .remove(name);
        self.statuses
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .remove(name);
        self.subscriptions
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .retain(|(plugin, _), _| plugin != name);
        Ok(())
    }

    pub async fn enable(&self, name: &str) -> Result<(), PluginError> {
        match self.status(name) {
            PluginStatus::Unloaded => {
                self.initialize(name).await?;
                self.start(name).await
            }
            PluginStatus::Loaded | PluginStatus::Stopped => self.start(name).await,
            PluginStatus::Active => Ok(()),
            status => Err(PluginError::InvalidTransition(format!(
                "cannot enable {name} from {status:?}"
            ))),
        }
    }

    pub async fn disable(&self, name: &str) -> Result<(), PluginError> {
        self.stop(name).await
    }
    pub fn subscribe(
        &self,
        plugin: &str,
        event_type: &str,
        handler: Arc<dyn PluginEventHandler>,
    ) -> Result<(), PluginError> {
        if self.registry.get(plugin).is_none() {
            return Err(PluginError::NotFound(plugin.into()));
        }
        self.subscriptions
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert((plugin.into(), event_type.into()), handler);
        Ok(())
    }
    pub fn unsubscribe(&self, plugin: &str, event_type: &str) -> bool {
        self.subscriptions
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .remove(&(plugin.into(), event_type.into()))
            .is_some()
    }
    pub async fn publish(
        &self,
        event_type: &str,
        payload: &Value,
    ) -> BTreeMap<String, Result<(), PluginError>> {
        let handlers: Vec<_> = self
            .subscriptions
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .iter()
            .filter(|((_, kind), _)| kind == event_type)
            .map(|((plugin, _), handler)| (plugin.clone(), handler.clone()))
            .collect();
        let mut results = BTreeMap::new();
        for (plugin, handler) in handlers {
            results.insert(plugin, handler.handle(event_type, payload).await);
        }
        results
    }
    pub async fn health(&self, now_ms: u64) -> BTreeMap<String, PluginHealth> {
        let plugins = self.registry.all();
        let mut health = BTreeMap::new();
        for (name, registered) in plugins {
            health.insert(name, registered.plugin.health(now_ms).await);
        }
        health
    }
    fn set_status(&self, name: &str, status: PluginStatus) {
        self.statuses
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .insert(name.into(), status);
    }
}
