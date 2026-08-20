use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use serde::Deserialize;
use serde_json::{Value, json};

use super::*;

#[derive(Deserialize)]
struct Fixture {
    schema_version: u32,
    plugin_statuses: Vec<String>,
    service_statuses: Vec<String>,
    route_methods: Vec<String>,
    default_metadata: BTreeMap<String, String>,
    dependency_order: Vec<String>,
    reverse_stop_order: Vec<String>,
    config: ConfigFixture,
    failure_codes: Vec<String>,
}
#[derive(Deserialize)]
struct ConfigFixture {
    defaults: BTreeMap<String, Value>,
    valid: BTreeMap<String, Value>,
    missing_required_error: String,
}
fn fixture() -> Fixture {
    serde_json::from_str(include_str!("../../../contracts/plugins-behavior.json"))
        .expect("valid plugin contract")
}

fn metadata(name: &str, dependencies: Vec<String>) -> PluginMetadata {
    PluginMetadata {
        name: name.into(),
        version: "1.0.0".into(),
        description: String::new(),
        author: String::new(),
        dependencies,
        api_version: "1.0".into(),
        min_mmf_version: "1.0.0".into(),
        keywords: Vec::new(),
        homepage: String::new(),
        license: String::new(),
        kind: PluginKind::Service,
    }
}
fn service(name: &str) -> ServiceDefinition {
    ServiceDefinition {
        name: name.into(),
        description: String::new(),
        version: "1.0.0".into(),
        endpoint: format!("/{name}"),
        routes: Vec::new(),
        middleware: Vec::new(),
        dependencies: Vec::new(),
        health_check_path: "/health".into(),
        metrics_enabled: true,
        database_required: false,
        methods: vec![RouteMethod::Get],
        auth_required: true,
        rate_limit_per_minute: 0,
        timeout_seconds: 30,
        tags: Vec::new(),
        metadata: BTreeMap::new(),
    }
}

struct TestPlugin {
    metadata: PluginMetadata,
    calls: Arc<Mutex<Vec<String>>>,
}
#[async_trait]
impl Plugin for TestPlugin {
    fn metadata(&self) -> PluginMetadata {
        self.metadata.clone()
    }
    fn service_definitions(&self) -> Vec<ServiceDefinition> {
        vec![service(&format!("{}-service", self.metadata.name))]
    }
    async fn initialize(&self, _: &PluginContext) -> Result<(), PluginError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(format!("initialize:{}", self.metadata.name));
        Ok(())
    }
    async fn start(&self) -> Result<(), PluginError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(format!("start:{}", self.metadata.name));
        Ok(())
    }
    async fn stop(&self) -> Result<(), PluginError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(format!("stop:{}", self.metadata.name));
        Ok(())
    }
    async fn cleanup(&self) -> Result<(), PluginError> {
        self.calls
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(format!("cleanup:{}", self.metadata.name));
        Ok(())
    }
    async fn health(&self, now_ms: u64) -> PluginHealth {
        PluginHealth {
            plugin_name: self.metadata.name.clone(),
            status: PluginStatus::Active,
            healthy: true,
            detail: None,
            checked_at_ms: now_ms,
        }
    }
}

#[test]
fn language_neutral_enum_and_default_contract() {
    let f = fixture();
    assert_eq!(f.schema_version, 1);
    assert_eq!(
        serde_json::to_value([
            PluginStatus::Unloaded,
            PluginStatus::Loading,
            PluginStatus::Loaded,
            PluginStatus::Initializing,
            PluginStatus::Active,
            PluginStatus::Error,
            PluginStatus::Stopping,
            PluginStatus::Stopped
        ])
        .expect("plugin statuses"),
        json!(f.plugin_statuses)
    );
    assert_eq!(
        serde_json::to_value([
            ServiceStatus::Inactive,
            ServiceStatus::Starting,
            ServiceStatus::Active,
            ServiceStatus::Stopping,
            ServiceStatus::Failed
        ])
        .expect("service statuses"),
        json!(f.service_statuses)
    );
    assert_eq!(
        serde_json::to_value([
            RouteMethod::Get,
            RouteMethod::Post,
            RouteMethod::Put,
            RouteMethod::Delete,
            RouteMethod::Patch,
            RouteMethod::Head,
            RouteMethod::Options
        ])
        .expect("methods"),
        json!(f.route_methods)
    );
    let meta = metadata("plugin", Vec::new());
    assert_eq!(meta.api_version, f.default_metadata["api_version"]);
    assert_eq!(meta.min_mmf_version, f.default_metadata["min_mmf_version"]);
}

#[tokio::test]
async fn dependency_order_lifecycle_services_health_and_reverse_stop_contract() {
    let f = fixture();
    let manager = PluginManager::default();
    let calls = Arc::new(Mutex::new(Vec::new()));
    for (name, deps) in [
        ("database", vec![]),
        ("identity", vec!["database".into()]),
        ("wallet", vec!["identity".into()]),
    ] {
        manager
            .register(
                Arc::new(TestPlugin {
                    metadata: metadata(name, deps),
                    calls: calls.clone(),
                }),
                PluginContextBuilder::new(name).build().expect("context"),
            )
            .expect("register");
    }
    assert_eq!(
        manager.initialize_all().await.expect("initialize"),
        f.dependency_order
    );
    assert_eq!(
        manager.start_all().await.expect("start"),
        f.dependency_order
    );
    assert_eq!(
        manager
            .services
            .list(None)
            .values()
            .map(Vec::len)
            .sum::<usize>(),
        3
    );
    assert!(
        manager
            .health(10)
            .await
            .values()
            .all(|health| health.healthy)
    );
    assert_eq!(
        manager.stop_all().await.expect("stop"),
        f.reverse_stop_order
    );
    assert_eq!(manager.status("database"), PluginStatus::Stopped);
}

#[test]
fn config_is_namespaced_validated_and_templated_contract() {
    let f = fixture();
    let manager = PluginConfigManager::default();
    manager
        .register(
            "wallet",
            PluginConfigSchema {
                fields: BTreeMap::from([
                    (
                        "enabled".into(),
                        ConfigField {
                            value_type: ConfigValueType::Boolean,
                            required: true,
                            default: Some(Value::Bool(true)),
                            description: String::new(),
                        },
                    ),
                    (
                        "timeout".into(),
                        ConfigField {
                            value_type: ConfigValueType::Integer,
                            required: false,
                            default: Some(Value::from(30)),
                            description: String::new(),
                        },
                    ),
                ]),
                allow_extra: false,
            },
        )
        .expect("schema");
    assert_eq!(
        manager.get("wallet", "default").expect("defaults"),
        f.config.defaults
    );
    manager
        .update("wallet", "default", f.config.valid.clone())
        .expect("valid");
    assert_eq!(
        manager.get("wallet", "default").expect("stored"),
        f.config.valid
    );
    let required = PluginConfigSchema {
        fields: BTreeMap::from([(
            "enabled".into(),
            ConfigField {
                value_type: ConfigValueType::Boolean,
                required: true,
                default: None,
                description: String::new(),
            },
        )]),
        allow_extra: false,
    };
    assert_eq!(
        required
            .validate(&BTreeMap::new())
            .expect_err("missing")
            .to_string(),
        format!("invalid plugin input: {}", f.config.missing_required_error)
    );
}

#[test]
fn missing_dependencies_cycles_transitions_and_providers_fail_closed() {
    let f = fixture();
    assert_eq!(f.failure_codes.len(), 4);
    let missing = PluginRegistry::default();
    missing
        .register(Arc::new(TestPlugin {
            metadata: metadata("wallet", vec!["identity".into()]),
            calls: Arc::new(Mutex::new(Vec::new())),
        }))
        .expect("register");
    assert!(matches!(
        missing.dependency_order(),
        Err(PluginError::Dependency(_))
    ));
    let cycle = PluginRegistry::default();
    for (name, dependency) in [("a", "b"), ("b", "a")] {
        cycle
            .register(Arc::new(TestPlugin {
                metadata: metadata(name, vec![dependency.into()]),
                calls: Arc::new(Mutex::new(Vec::new())),
            }))
            .expect("register");
    }
    assert!(matches!(
        cycle.dependency_order(),
        Err(PluginError::Dependency(_))
    ));
    let manager = PluginManager::default();
    assert!(matches!(
        tokio_test(manager.start("missing")),
        Err(PluginError::InvalidTransition(_))
    ));
    assert!(matches!(
        tokio_test(manager.discover(&[])),
        Err(PluginError::ProviderUnavailable(_))
    ));
}
fn tokio_test<T>(future: impl std::future::Future<Output = T>) -> T {
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .expect("runtime")
        .block_on(future)
}

struct EventRecorder(Arc<Mutex<Vec<Value>>>);
#[async_trait]
impl PluginEventHandler for EventRecorder {
    async fn handle(&self, _: &str, payload: &Value) -> Result<(), PluginError> {
        self.0
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .push(payload.clone());
        Ok(())
    }
}
#[tokio::test]
async fn subscriptions_publish_and_unsubscribe_without_cross_plugin_leaks() {
    let manager = PluginManager::default();
    let calls = Arc::new(Mutex::new(Vec::new()));
    manager
        .register(
            Arc::new(TestPlugin {
                metadata: metadata("audit", Vec::new()),
                calls,
            }),
            PluginContextBuilder::new("audit").build().expect("context"),
        )
        .expect("register");
    let events = Arc::new(Mutex::new(Vec::new()));
    manager
        .subscribe(
            "audit",
            "user.created",
            Arc::new(EventRecorder(events.clone())),
        )
        .expect("subscribe");
    assert!(manager.publish("user.created", &json!({"id":"1"})).await["audit"].is_ok());
    assert_eq!(
        events
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .len(),
        1
    );
    assert!(manager.unsubscribe("audit", "user.created"));
    assert!(manager.publish("user.created", &json!({})).await.is_empty());
}
