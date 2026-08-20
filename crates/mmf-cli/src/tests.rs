use std::collections::BTreeMap;
use std::path::PathBuf;

use async_trait::async_trait;
use serde::Deserialize;
use serde_json::json;

use super::*;

#[derive(Deserialize)]
struct Fixture {
    schema_version: u32,
    fastapi_source: String,
    proto_source: String,
    service: ApiService,
    expected_openapi: OpenApiFixture,
    expected_artifacts: Vec<String>,
    streaming_modes: Vec<String>,
    builtin_templates: Vec<String>,
    commands: Vec<String>,
    template_source: String,
    template_header: String,
    template_expected: String,
    version_service: String,
    active_version: String,
    deprecated_version: String,
}

#[derive(Deserialize)]
struct OpenApiFixture {
    openapi: String,
    title: String,
    version: String,
    get_summary: String,
    post_deprecated: bool,
    post_deprecation_date: String,
    schema_count: usize,
}

fn fixture() -> Fixture {
    serde_json::from_str(include_str!(
        "../../../contracts/cli-documentation-behavior.json"
    ))
    .expect("valid CLI/documentation contract")
}

#[test]
fn openapi_postman_gateway_and_artifact_contract() {
    let fixture = fixture();
    assert_eq!(fixture.schema_version, 1);
    let spec = openapi_spec(&fixture.service, true).expect("OpenAPI");
    assert_eq!(spec["openapi"], fixture.expected_openapi.openapi);
    assert_eq!(spec["info"]["title"], fixture.expected_openapi.title);
    assert_eq!(spec["info"]["version"], fixture.expected_openapi.version);
    assert_eq!(
        spec["paths"]["/accounts"]["get"]["summary"],
        fixture.expected_openapi.get_summary
    );
    assert_eq!(
        spec["paths"]["/accounts"]["post"]["deprecated"],
        fixture.expected_openapi.post_deprecated
    );
    assert_eq!(
        spec["paths"]["/accounts"]["post"]["x-deprecation-date"],
        fixture.expected_openapi.post_deprecation_date
    );
    assert_eq!(
        spec["components"]["schemas"]
            .as_object()
            .expect("schemas")
            .len(),
        fixture.expected_openapi.schema_count
    );

    let postman = postman_collection(&fixture.service);
    assert_eq!(postman["item"].as_array().expect("items").len(), 2);
    assert_eq!(postman["item"][1]["request"]["method"], "POST");
    let gateway = grpc_gateway_yaml(&fixture.service);
    assert!(gateway.contains("accounts.v1.Accounts.GetAccount"));
    assert!(gateway.contains("/api/v1/getaccount"));

    let bundle = generate_documentation(
        &[fixture.service],
        &DocumentationConfig::default(),
        "2026-08-20T00:00:00Z",
    )
    .expect("bundle");
    let artifacts = bundle
        .artifacts
        .iter()
        .map(|artifact| artifact.relative_path.to_string_lossy().replace('\\', "/"))
        .collect::<Vec<_>>();
    assert_eq!(artifacts, fixture.expected_artifacts);
    assert!(bundle.artifact("accounts-grpc-clients.md").is_some());
}

#[test]
fn fastapi_and_all_proto_streaming_modes_are_discovered() {
    let fixture = fixture();
    let service = parse_fastapi_source(
        PathBuf::from("accounts/main.py").as_path(),
        &fixture.fastapi_source,
    )
    .expect("parse")
    .expect("service");
    assert_eq!(service.name, "Accounts");
    assert_eq!(service.version, "2.1.0");
    assert_eq!(service.endpoints.len(), 2);
    assert!(service.endpoints[1].deprecated);

    let services = parse_proto_source(&fixture.proto_source).expect("proto");
    assert_eq!(services.len(), 1);
    let modes = services[0]
        .grpc_methods
        .iter()
        .map(|method| serde_json::to_value(method.streaming).expect("mode"))
        .collect::<Vec<_>>();
    assert_eq!(
        modes,
        json!(fixture.streaming_modes).as_array().unwrap().clone()
    );
    assert_eq!(
        services[0].grpc_methods[3].full_name,
        "accounts.v1.Accounts.SyncAccounts"
    );
}

#[test]
fn template_engine_preserves_variables_filters_conditions_loops_includes_and_macros() {
    let fixture = fixture();
    let engine = TemplateEngine::new(BTreeMap::from([
        ("service".into(), fixture.template_source),
        ("header".into(), fixture.template_header),
    ]));
    let context = TemplateContext::default()
        .with("project_name", "risk service")
        .with("enabled", true)
        .with("items", json!(["one", "two"]));
    assert_eq!(
        engine.render("service", &context, None).expect("render"),
        fixture.template_expected
    );
    assert!(engine.render("missing", &context, None).is_err());
    assert!(
        engine
            .render(
                "service",
                &TemplateContext::default().with("enabled", true),
                None
            )
            .is_err()
    );
}

#[test]
fn versions_are_persistent_serializable_and_missing_transitions_fail_closed() {
    let fixture = fixture();
    let mut versions = VersionRegistry::default();
    versions
        .register(
            &fixture.version_service,
            &fixture.active_version,
            "2026-08-20T00:00:00Z",
            None,
            None,
        )
        .expect("active");
    versions
        .register(
            &fixture.version_service,
            &fixture.deprecated_version,
            "2025-01-01T00:00:00Z",
            None,
            None,
        )
        .expect("old");
    versions
        .deprecate(
            &fixture.version_service,
            &fixture.deprecated_version,
            "2026-01-01",
            "upgrade",
        )
        .expect("deprecate");
    assert_eq!(
        versions.active_versions(&fixture.version_service),
        vec![fixture.active_version]
    );
    assert_eq!(
        versions.deprecated_versions(&fixture.version_service),
        vec![fixture.deprecated_version]
    );
    let encoded = serde_json::to_string(&versions).expect("serialize");
    assert_eq!(
        serde_json::from_str::<VersionRegistry>(&encoded).expect("restore"),
        versions
    );
    assert!(
        versions
            .deprecate("missing", "v1", "2026-01-01", "upgrade")
            .is_err()
    );
}

#[test]
fn all_intended_templates_generate_rust_first_operational_projects() {
    let fixture = fixture();
    let templates = builtin_templates();
    assert_eq!(
        templates
            .iter()
            .map(|template| template.name.clone())
            .collect::<Vec<_>>(),
        fixture.builtin_templates
    );
    for descriptor in templates {
        descriptor.validate().expect("descriptor");
        let project = ScaffoldGenerator::generate(&ProjectConfig {
            name: "ExampleService".into(),
            template: ServiceTemplate::parse(&descriptor.name).expect("template"),
            output_path: PathBuf::from("generated"),
            author: "Marty".into(),
            email: "dev@example.test".into(),
            description: descriptor.description,
            license: "AGPL-3.0-only".into(),
            git_repository: String::new(),
            docker_enabled: true,
            kubernetes_enabled: true,
            monitoring_enabled: true,
            testing_enabled: true,
            ci_cd_enabled: true,
            environment: "development".into(),
            http_port: 8_000,
            grpc_port: 50_051,
            variables: BTreeMap::new(),
        })
        .expect("scaffold");
        assert!(
            project
                .files
                .iter()
                .any(|file| file.relative_path.as_path() == std::path::Path::new("Cargo.toml"))
        );
        assert!(
            project
                .files
                .iter()
                .any(|file| file.relative_path.as_path() == std::path::Path::new("src/main.rs"))
        );
        assert!(
            project
                .files
                .iter()
                .any(|file| file.relative_path.as_path() == std::path::Path::new("Dockerfile"))
        );
        let cargo = project
            .files
            .iter()
            .find(|file| file.relative_path.as_path() == std::path::Path::new("Cargo.toml"))
            .expect("Cargo manifest");
        assert!(cargo.content.contains("mmf = \"0.1.0\""));
        let library = project
            .files
            .iter()
            .find(|file| file.relative_path.as_path() == std::path::Path::new("src/lib.rs"))
            .expect("library");
        assert!(library.content.contains("mmf::"));
        assert!(!project.files.iter().any(|file| {
            file.relative_path
                .extension()
                .is_some_and(|extension| extension == "py")
        }));
    }
}

#[test]
fn intended_command_catalog_parses_and_dangerous_plans_fail_closed() {
    let fixture = fixture();
    for command in &fixture.commands {
        assert!(
            command_help().contains(command),
            "missing help for {command}"
        );
    }
    let command = parse_cli(&[
        "new".into(),
        "fastapi-service".into(),
        "risk-service".into(),
        "--no-docker".into(),
        "--port".into(),
        "8081".into(),
    ])
    .expect("new command");
    let CliCommand::New(config) = command else {
        panic!("wrong command");
    };
    assert!(!config.docker_enabled);
    assert_eq!(config.http_port, 8_081);

    let build = CliCommand::Build(BuildOptions {
        push: true,
        ..BuildOptions::default()
    });
    assert!(plan_command(&build, std::path::Path::new("project")).is_err());
    let production = CliCommand::Deploy(DeployOptions {
        environment: EnvironmentType::Production,
        ..DeployOptions::default()
    });
    assert!(plan_command(&production, std::path::Path::new("project")).is_err());
}

struct EchoExecutor;

#[async_trait]
impl ContractExecutor for EchoExecutor {
    async fn execute(
        &self,
        _: &Contract,
        interaction: &ContractInteraction,
    ) -> Result<ExecutedInteraction, CliError> {
        Ok(ExecutedInteraction {
            response: interaction.response.clone(),
            duration_ms: 5,
        })
    }
}

struct MissingExecutor;

#[async_trait]
impl ContractExecutor for MissingExecutor {
    async fn execute(
        &self,
        _: &Contract,
        _: &ContractInteraction,
    ) -> Result<ExecutedInteraction, CliError> {
        Err(CliError::ProviderUnavailable("offline".into()))
    }
}

#[tokio::test]
async fn contract_registry_execution_docs_junit_and_provider_failure_contract() {
    let contract = create_contract(
        "ui",
        "identity",
        "1.0.0",
        ContractType::Http,
        vec![example_http_interaction()],
        BTreeMap::new(),
    )
    .expect("contract");
    let mut registry = ContractRegistry::default();
    registry.register(contract.clone()).expect("register");
    assert!(registry.register(contract.clone()).is_err());
    assert_eq!(
        registry
            .list(&ContractQuery {
                provider: Some("identity".into()),
                ..ContractQuery::default()
            })
            .len(),
        1
    );
    let passed = test_contract(&contract, VerificationLevel::Strict, &EchoExecutor).await;
    let summary = summarize_contract_tests(vec![passed]);
    assert!(summary.passed);
    assert!(junit_report(&summary).contains("failures=\"0\""));
    assert!(contract_documentation(&[&contract]).contains("ui -> identity"));

    let failed = test_contract(&contract, VerificationLevel::Strict, &MissingExecutor).await;
    assert!(!failed.passed);
    assert!(
        failed.interactions[0]
            .error
            .as_ref()
            .is_some_and(|error| error.contains("provider unavailable"))
    );
}

#[test]
fn malformed_inputs_paths_monitors_and_mesh_fail_closed() {
    assert!(
        parse_proto_source("service Broken {")
            .expect("parse")
            .is_empty()
    );
    assert!(
        ApiService {
            name: String::new(),
            ..ApiService::default()
        }
        .validate()
        .is_err()
    );
    assert!(
        GeneratedProject {
            root: PathBuf::from("project"),
            template: ServiceTemplate::MinimalService,
            files: vec![GeneratedArtifact {
                relative_path: PathBuf::from("../escape"),
                media_type: "text/plain".into(),
                content: String::new(),
            }],
            post_generation: Vec::new(),
        }
        .validate()
        .is_err()
    );
    assert!(
        ContractMonitorConfig {
            providers: Vec::new(),
            interval_seconds: 0,
            webhook_url: Some("http://unsafe.test".into()),
            fail_fast: true,
            verification_level: VerificationLevel::Strict,
        }
        .validate()
        .is_err()
    );
    assert!(generate_mesh_artifacts("", "example.test", MeshType::Istio, "default").is_err());
}
