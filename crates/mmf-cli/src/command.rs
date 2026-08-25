use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::{
    CliError, DocumentationConfig, DocumentationTheme, EnvironmentType, GeneratedArtifact,
    MeshType, ProcessInvocation, ProjectConfig, ServiceTemplate, TemplateCategory,
};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "command", content = "options", rename_all = "kebab-case")]
pub enum CliCommand {
    New(ProjectConfig),
    Templates(TemplateQuery),
    Build(BuildOptions),
    Test(TestOptions),
    Run(RunOptions),
    Deploy(DeployOptions),
    Info(InfoOptions),
    Config(ConfigCommand),
    Api(ApiCommand),
    Migrate(MigrationCommand),
    ServiceMesh(ServiceMeshCommand),
    Plugin(PluginCommand),
    Service(ServiceCommand),
    Security(SecurityCommand),
    Database(DatabaseCommand),
}

impl CliCommand {
    #[must_use]
    pub const fn name(&self) -> &'static str {
        match self {
            Self::New(_) => "new",
            Self::Templates(_) => "templates",
            Self::Build(_) => "build",
            Self::Test(_) => "test",
            Self::Run(_) => "run",
            Self::Deploy(_) => "deploy",
            Self::Info(_) => "info",
            Self::Config(_) => "config",
            Self::Api(_) => "api",
            Self::Migrate(_) => "migrate",
            Self::ServiceMesh(_) => "service-mesh",
            Self::Plugin(_) => "plugin",
            Self::Service(_) => "service",
            Self::Security(_) => "security",
            Self::Database(_) => "db",
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct TemplateQuery {
    pub name: Option<String>,
    pub category: Option<TemplateCategory>,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct BuildOptions {
    pub release: bool,
    pub docker: bool,
    pub push: bool,
    pub tag: Option<String>,
    pub no_cache: bool,
    pub locked: bool,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TestSelection {
    #[default]
    All,
    Unit,
    Integration,
    Contract,
    EndToEnd,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct TestOptions {
    pub selection: TestSelection,
    pub coverage: bool,
    pub watch: bool,
    pub release: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RunOptions {
    pub port: Option<u16>,
    pub grpc_port: Option<u16>,
    pub environment_file: Option<PathBuf>,
    pub environment: String,
    pub host: String,
    pub workers: u16,
    pub debug: bool,
    pub reload: bool,
    pub log_level: String,
    pub metrics: bool,
    pub service_name: Option<String>,
}

impl Default for RunOptions {
    fn default() -> Self {
        Self {
            port: None,
            grpc_port: None,
            environment_file: None,
            environment: "development".into(),
            host: "0.0.0.0".into(),
            workers: 1,
            debug: false,
            reload: false,
            log_level: "info".into(),
            metrics: true,
            service_name: None,
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DeployOptions {
    pub environment: EnvironmentType,
    pub namespace: String,
    pub context: Option<String>,
    pub image: Option<String>,
    pub image_digest: Option<String>,
    pub dry_run: bool,
    pub wait: bool,
}

impl Default for DeployOptions {
    fn default() -> Self {
        Self {
            environment: EnvironmentType::Development,
            namespace: "default".into(),
            context: None,
            image: None,
            image_digest: None,
            dry_run: false,
            wait: false,
        }
    }
}

impl DeployOptions {
    pub fn validate(&self) -> Result<(), CliError> {
        if self.namespace.trim().is_empty() {
            return Err(CliError::InvalidInput(
                "deployment namespace is required".into(),
            ));
        }
        if self.environment == EnvironmentType::Production && self.image_digest.is_none() {
            return Err(CliError::InvalidInput(
                "production deployment requires an immutable image digest".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct InfoOptions {
    pub dependencies: bool,
    pub config: bool,
    pub status: bool,
    pub output_json: bool,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum ConfigCommand {
    Set {
        values: BTreeMap<String, String>,
    },
    Show {
        service_path: Option<PathBuf>,
        environment: Option<String>,
    },
    Reset,
    Validate {
        service_path: PathBuf,
        plugin: Option<String>,
    },
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum ApiCommand {
    Docs {
        source_paths: Vec<PathBuf>,
        config: DocumentationConfig,
        overwrite: bool,
    },
    CreateContract {
        consumer: String,
        provider: String,
        version: String,
        contract_type: String,
        service_name: Option<String>,
    },
    TestContracts {
        provider: Option<String>,
        endpoint: Option<String>,
        consumer: Option<String>,
        version: Option<String>,
        strict: bool,
        junit_output: Option<PathBuf>,
    },
    ListContracts {
        consumer: Option<String>,
        provider: Option<String>,
        contract_type: Option<String>,
    },
    RegisterVersion {
        service_name: String,
        version: String,
        deprecation_date: Option<String>,
        migration_guide: Option<String>,
    },
    ListVersions {
        service_name: Option<String>,
        status: Option<String>,
    },
    GrpcContract {
        proto_file: PathBuf,
        consumer: String,
        provider: String,
        output_dir: PathBuf,
    },
    ContractDocs {
        contracts_dir: PathBuf,
        docs_dir: PathBuf,
        format: String,
    },
    Monitor {
        providers: Vec<String>,
        interval_seconds: u64,
        webhook_url: Option<String>,
        fail_fast: bool,
    },
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum MigrationCommand {
    HelmToKustomize {
        chart_path: PathBuf,
        output_path: PathBuf,
        service_name: String,
        namespace: String,
        environment: String,
        validate: bool,
    },
    GenerateOverlay {
        base_path: PathBuf,
        output_path: PathBuf,
        environment: String,
        namespace: String,
        replicas: u32,
        image_tag: Option<String>,
        marty_services: bool,
    },
    Validate {
        helm_path: PathBuf,
        kustomize_path: PathBuf,
        strict: bool,
    },
    CheckCompatibility {
        service_name: String,
        chart_path: Option<PathBuf>,
    },
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum ServiceMeshCommand {
    Install {
        mesh_type: MeshType,
        namespace: String,
        cluster_name: String,
        monitoring: bool,
    },
    ApplyPolicies {
        mesh_type: MeshType,
        namespace: String,
        service_name: Option<String>,
        strict_mtls: bool,
        authorization: bool,
        rate_limit: bool,
    },
    Status {
        mesh_type: MeshType,
        namespace: String,
    },
    Generate {
        project_name: String,
        output_dir: PathBuf,
        domain: String,
        mesh_type: MeshType,
        namespace: String,
    },
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum PluginCommand {
    Init {
        name: String,
        features: Vec<String>,
        template: String,
        interactive: bool,
    },
    List,
    Status {
        name: String,
    },
    ServiceAdd {
        plugin: String,
        name: String,
        service_type: String,
        features: Vec<String>,
    },
    ServiceList {
        plugin: Option<String>,
    },
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum ServiceCommand {
    Init {
        service_type: ServiceTemplate,
        name: String,
        description: String,
        author: String,
        grpc_port: u16,
        http_port: u16,
        mesh_type: Option<MeshType>,
        namespace: String,
        domain: String,
    },
    List,
    Status {
        name: String,
    },
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum SecurityCommand {
    Scan {
        service_path: PathBuf,
    },
    PolicyTest {
        principal: String,
        resource: String,
        action: String,
    },
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum DatabaseCommand {
    Seed {
        service_path: PathBuf,
        host: String,
        port: u16,
        database: String,
        user: String,
        password_secret: String,
    },
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct CommandPlan {
    pub command: String,
    pub summary: String,
    #[serde(default)]
    pub processes: Vec<ProcessInvocation>,
    #[serde(default)]
    pub artifacts: Vec<GeneratedArtifact>,
    #[serde(default)]
    pub requires_internal_handler: bool,
    #[serde(default)]
    pub dry_run: bool,
}

pub fn plan_command(command: &CliCommand, project_root: &Path) -> Result<CommandPlan, CliError> {
    let mut plan = CommandPlan {
        command: command.name().into(),
        summary: format!("execute Marty {} command", command.name()),
        ..CommandPlan::default()
    };
    match command {
        CliCommand::Build(options) => plan_build(options, project_root, &mut plan)?,
        CliCommand::Test(options) => plan_test(options, project_root, &mut plan),
        CliCommand::Run(options) => plan_run(options, project_root, &mut plan)?,
        CliCommand::Deploy(options) => plan_deploy(options, project_root, &mut plan)?,
        CliCommand::Migrate(MigrationCommand::GenerateOverlay {
            output_path,
            environment,
            namespace,
            replicas,
            image_tag,
            ..
        }) => {
            plan.artifacts = generate_kustomize_overlay(
                environment,
                namespace,
                *replicas,
                image_tag.as_deref(),
            )?;
            plan.summary = format!("generate Kustomize overlay at {}", output_path.display());
        }
        CliCommand::ServiceMesh(ServiceMeshCommand::Generate {
            project_name,
            domain,
            mesh_type,
            namespace,
            ..
        }) => {
            plan.artifacts = generate_mesh_artifacts(project_name, domain, *mesh_type, namespace)?;
        }
        _ => plan.requires_internal_handler = true,
    }
    for process in &plan.processes {
        process.validate()?;
    }
    Ok(plan)
}

fn plan_build(options: &BuildOptions, root: &Path, plan: &mut CommandPlan) -> Result<(), CliError> {
    if options.push && !options.docker {
        return Err(CliError::InvalidInput(
            "--push requires a Docker build".into(),
        ));
    }
    if options.docker {
        let tag = options.tag.clone().unwrap_or_else(|| "latest".into());
        let mut arguments = vec!["build".into(), "-t".into(), tag.clone()];
        if options.no_cache {
            arguments.push("--no-cache".into());
        }
        arguments.push(".".into());
        plan.processes.push(process("docker", arguments, root));
        if options.push {
            plan.processes
                .push(process("docker", vec!["push".into(), tag], root));
        }
    } else {
        let mut arguments = vec!["build".into()];
        if options.release {
            arguments.push("--release".into());
        }
        if options.locked {
            arguments.push("--locked".into());
        }
        plan.processes.push(process("cargo", arguments, root));
    }
    Ok(())
}

fn plan_test(options: &TestOptions, root: &Path, plan: &mut CommandPlan) {
    let mut arguments = if options.coverage {
        vec!["llvm-cov".into(), "--all-features".into()]
    } else {
        vec!["test".into()]
    };
    if options.release {
        arguments.push("--release".into());
    }
    match options.selection {
        TestSelection::All => {}
        TestSelection::Unit => arguments.extend(["--lib".into()]),
        TestSelection::Integration => arguments.extend(["--tests".into()]),
        TestSelection::Contract => arguments.extend(["contract".into()]),
        TestSelection::EndToEnd => arguments.extend(["--test".into(), "e2e".into()]),
    }
    plan.processes.push(process("cargo", arguments, root));
    if options.watch {
        plan.summary
            .push_str(" (watch mode requested through provider)");
    }
}

fn plan_run(options: &RunOptions, root: &Path, plan: &mut CommandPlan) -> Result<(), CliError> {
    if options.workers == 0 || options.host.trim().is_empty() {
        return Err(CliError::InvalidInput(
            "run host and workers are invalid".into(),
        ));
    }
    let mut invocation = process("cargo", vec!["run".into()], root);
    invocation
        .environment
        .insert("MARTY_ENVIRONMENT".into(), options.environment.clone());
    invocation
        .environment
        .insert("MARTY_HOST".into(), options.host.clone());
    invocation
        .environment
        .insert("MARTY_WORKERS".into(), options.workers.to_string());
    invocation
        .environment
        .insert("MARTY_LOG_LEVEL".into(), options.log_level.clone());
    invocation
        .environment
        .insert("MARTY_METRICS".into(), options.metrics.to_string());
    if let Some(port) = options.port {
        invocation
            .environment
            .insert("MARTY_PORT".into(), port.to_string());
    }
    if let Some(port) = options.grpc_port {
        invocation
            .environment
            .insert("MARTY_GRPC_PORT".into(), port.to_string());
    }
    if let Some(path) = &options.environment_file {
        invocation
            .environment
            .insert("MARTY_ENV_FILE".into(), path.to_string_lossy().into_owned());
    }
    plan.processes.push(invocation);
    Ok(())
}

fn plan_deploy(
    options: &DeployOptions,
    root: &Path,
    plan: &mut CommandPlan,
) -> Result<(), CliError> {
    options.validate()?;
    let mut arguments = vec![
        "apply".into(),
        "-k".into(),
        format!("k8s/overlays/{}", environment_name(options.environment)),
        "--namespace".into(),
        options.namespace.clone(),
    ];
    if let Some(context) = &options.context {
        arguments.extend(["--context".into(), context.clone()]);
    }
    if options.dry_run {
        arguments.push("--dry-run=server".into());
    }
    if options.wait {
        arguments.push("--wait".into());
    }
    plan.processes.push(process("kubectl", arguments, root));
    plan.dry_run = options.dry_run;
    Ok(())
}

pub fn generate_kustomize_overlay(
    environment: &str,
    namespace: &str,
    replicas: u32,
    image_tag: Option<&str>,
) -> Result<Vec<GeneratedArtifact>, CliError> {
    if environment.trim().is_empty() || namespace.trim().is_empty() || replicas == 0 {
        return Err(CliError::InvalidInput(
            "overlay environment, namespace, and positive replicas are required".into(),
        ));
    }
    let path = format!("overlays/{environment}");
    let mut kustomization = format!(
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nnamespace: {namespace}\nresources:\n  - ../../base\npatches:\n  - path: deployment-patch.yaml\n"
    );
    if let Some(tag) = image_tag {
        let _ = write!(
            kustomization,
            "images:\n  - name: service\n    newTag: {tag}\n"
        );
    }
    Ok(vec![
        artifact(
            format!("{path}/kustomization.yaml"),
            "application/yaml",
            kustomization,
        ),
        artifact(
            format!("{path}/deployment-patch.yaml"),
            "application/yaml",
            format!(
                "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: service\nspec:\n  replicas: {replicas}\n"
            ),
        ),
    ])
}

pub fn generate_mesh_artifacts(
    project_name: &str,
    domain: &str,
    mesh_type: MeshType,
    namespace: &str,
) -> Result<Vec<GeneratedArtifact>, CliError> {
    if project_name.trim().is_empty() || domain.trim().is_empty() || namespace.trim().is_empty() {
        return Err(CliError::InvalidInput(
            "mesh project, domain, and namespace are required".into(),
        ));
    }
    let label = match mesh_type {
        MeshType::Istio => "istio-injection: enabled",
        MeshType::Linkerd => "linkerd.io/inject: enabled",
        MeshType::Consul => "consul.hashicorp.com/connect-inject: 'true'",
        MeshType::Kuma => "kuma.io/sidecar-injection: enabled",
        MeshType::None => "mmf.dev/mesh-injection: disabled",
    };
    let namespace_manifest = format!(
        "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {namespace}\n  labels:\n    {label}\n"
    );
    let policy = format!(
        "apiVersion: security.istio.io/v1\nkind: PeerAuthentication\nmetadata:\n  name: {project_name}-strict-mtls\n  namespace: {namespace}\nspec:\n  mtls:\n    mode: STRICT\n---\napiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata:\n  name: {project_name}-default-deny\n  namespace: {namespace}\nspec:\n  podSelector: {{}}\n  policyTypes: [Ingress, Egress]\n# service domain: {domain}\n"
    );
    Ok(vec![
        artifact("namespace.yaml", "application/yaml", namespace_manifest),
        artifact("security-policy.yaml", "application/yaml", policy),
    ])
}

pub fn parse_cli(arguments: &[String]) -> Result<CliCommand, CliError> {
    let mut cursor = Arguments::new(arguments);
    let command = cursor.required("command")?;
    match command.as_str() {
        "new" => parse_new(&mut cursor),
        "templates" => Ok(CliCommand::Templates(TemplateQuery {
            name: cursor.positional(),
            category: cursor
                .option("--category")?
                .map(|value| parse_category(&value))
                .transpose()?,
        })),
        "build" => Ok(CliCommand::Build(BuildOptions {
            release: cursor.flag("--release"),
            docker: cursor.flag("--docker"),
            push: cursor.flag("--push"),
            tag: cursor.option("--tag")?,
            no_cache: cursor.flag("--no-cache"),
            locked: cursor.flag("--locked"),
        })),
        "test" => Ok(parse_test(&mut cursor)),
        "run" | "runservice" => parse_run(&mut cursor),
        "deploy" => parse_deploy(&mut cursor),
        "info" => Ok(CliCommand::Info(InfoOptions {
            dependencies: cursor.flag("--dependencies"),
            config: cursor.flag("--config"),
            status: cursor.flag("--status"),
            output_json: cursor.flag("--json"),
        })),
        "config" => parse_config(&mut cursor),
        "api" => parse_api(&mut cursor),
        "migrate" => parse_migrate(&mut cursor),
        "service-mesh" => parse_mesh(&mut cursor),
        "plugin" => parse_plugin(&mut cursor),
        "service" => parse_service(&mut cursor),
        "security" => parse_security(&mut cursor),
        "db" => parse_database(&mut cursor),
        _ => Err(CliError::NotFound(format!("command {command}"))),
    }
}

fn parse_new(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    let template = ServiceTemplate::parse(&cursor.required("template")?)?;
    let name = cursor.required("name")?;
    Ok(CliCommand::New(ProjectConfig {
        name,
        template,
        output_path: cursor
            .option("--path")?
            .map_or_else(|| PathBuf::from("."), PathBuf::from),
        author: cursor.option("--author")?.unwrap_or_default(),
        email: cursor.option("--email")?.unwrap_or_default(),
        description: cursor.option("--description")?.unwrap_or_default(),
        license: cursor
            .option("--license")?
            .unwrap_or_else(|| "AGPL-3.0-only".into()),
        git_repository: cursor.option("--git-repo")?.unwrap_or_default(),
        docker_enabled: !cursor.flag("--no-docker"),
        kubernetes_enabled: !cursor.flag("--no-k8s"),
        monitoring_enabled: !cursor.flag("--no-monitoring"),
        testing_enabled: !cursor.flag("--no-testing"),
        ci_cd_enabled: !cursor.flag("--no-ci-cd"),
        environment: cursor
            .option("--environment")?
            .unwrap_or_else(|| "development".into()),
        http_port: parse_u16(cursor.option("--port")?, 8_000, "port")?,
        grpc_port: parse_u16(cursor.option("--grpc-port")?, 50_051, "gRPC port")?,
        variables: BTreeMap::new(),
    }))
}

fn parse_test(cursor: &mut Arguments) -> CliCommand {
    let selection = if cursor.flag("--unit") {
        TestSelection::Unit
    } else if cursor.flag("--integration") {
        TestSelection::Integration
    } else if cursor.flag("--contract") {
        TestSelection::Contract
    } else if cursor.flag("--e2e") {
        TestSelection::EndToEnd
    } else {
        TestSelection::All
    };
    CliCommand::Test(TestOptions {
        selection,
        coverage: cursor.flag("--coverage"),
        watch: cursor.flag("--watch"),
        release: cursor.flag("--release"),
    })
}

fn parse_run(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    Ok(CliCommand::Run(RunOptions {
        port: parse_optional_u16(cursor.option("--port")?, "port")?,
        grpc_port: parse_optional_u16(cursor.option("--grpc-port")?, "gRPC port")?,
        environment_file: cursor.option("--env")?.map(PathBuf::from),
        environment: cursor
            .option("--environment")?
            .unwrap_or_else(|| "development".into()),
        host: cursor.option("--host")?.unwrap_or_else(|| "0.0.0.0".into()),
        workers: parse_u16(cursor.option("--workers")?, 1, "workers")?,
        debug: cursor.flag("--debug"),
        reload: cursor.flag("--reload"),
        log_level: cursor
            .option("--log-level")?
            .unwrap_or_else(|| "info".into()),
        metrics: !cursor.flag("--no-metrics"),
        service_name: cursor.positional(),
    }))
}

fn parse_deploy(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    Ok(CliCommand::Deploy(DeployOptions {
        environment: cursor
            .option("--environment")?
            .map_or(Ok(EnvironmentType::Development), |value| {
                parse_environment(&value)
            })?,
        namespace: cursor
            .option("--namespace")?
            .unwrap_or_else(|| "default".into()),
        context: cursor.option("--context")?,
        image: cursor.option("--image")?,
        image_digest: cursor.option("--image-digest")?,
        dry_run: cursor.flag("--dry-run"),
        wait: cursor.flag("--wait"),
    }))
}

fn parse_config(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    match cursor.required("config operation")?.as_str() {
        "set" => {
            let mut values = BTreeMap::new();
            for (flag, key) in [
                ("--author", "author"),
                ("--email", "email"),
                ("--license", "license"),
                ("--registry", "registry"),
                ("--rust-version", "rust_version"),
            ] {
                if let Some(value) = cursor.option(flag)? {
                    values.insert(key.into(), value);
                }
            }
            Ok(CliCommand::Config(ConfigCommand::Set { values }))
        }
        "show" => Ok(CliCommand::Config(ConfigCommand::Show {
            service_path: cursor.option("--service-path")?.map(PathBuf::from),
            environment: cursor.option("--environment")?,
        })),
        "reset" => Ok(CliCommand::Config(ConfigCommand::Reset)),
        "validate" => Ok(CliCommand::Config(ConfigCommand::Validate {
            service_path: cursor
                .option("--service-path")?
                .map_or_else(|| PathBuf::from("."), PathBuf::from),
            plugin: cursor.option("--plugin")?,
        })),
        operation => Err(CliError::NotFound(format!("config operation {operation}"))),
    }
}

fn parse_api(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    match cursor.required("API operation")?.as_str() {
        "docs" => {
            let source_paths = cursor
                .positionals_until_option()
                .into_iter()
                .map(PathBuf::from)
                .collect::<Vec<_>>();
            if source_paths.is_empty() {
                return Err(CliError::InvalidInput(
                    "API docs require source paths".into(),
                ));
            }
            let theme = cursor
                .option("--theme")?
                .map_or(Ok(DocumentationTheme::Redoc), |value| parse_theme(&value))?;
            let output_dir = cursor
                .option("--output-dir")?
                .map_or_else(|| PathBuf::from("docs/api"), PathBuf::from);
            Ok(CliCommand::Api(ApiCommand::Docs {
                source_paths,
                config: DocumentationConfig {
                    output_dir,
                    theme,
                    include_examples: !cursor.flag("--no-examples"),
                    ..DocumentationConfig::default()
                },
                overwrite: cursor.flag("--overwrite"),
            }))
        }
        "create-contract" => Ok(CliCommand::Api(ApiCommand::CreateContract {
            consumer: cursor.required_option("--consumer")?,
            provider: cursor.required_option("--provider")?,
            version: cursor
                .option("--version")?
                .unwrap_or_else(|| "1.0.0".into()),
            contract_type: cursor.option("--type")?.unwrap_or_else(|| "http".into()),
            service_name: cursor.option("--service-name")?,
        })),
        "test-contracts" => Ok(CliCommand::Api(ApiCommand::TestContracts {
            provider: cursor.option("--provider")?,
            endpoint: cursor.option("--url")?.or(cursor.option("--grpc-address")?),
            consumer: cursor.option("--consumer")?,
            version: cursor.option("--version")?,
            strict: cursor.flag("--strict"),
            junit_output: cursor.option("--junit")?.map(PathBuf::from),
        })),
        "list-contracts" => Ok(CliCommand::Api(ApiCommand::ListContracts {
            consumer: cursor.option("--consumer")?,
            provider: cursor.option("--provider")?,
            contract_type: cursor.option("--type")?,
        })),
        "register-version" => Ok(CliCommand::Api(ApiCommand::RegisterVersion {
            service_name: cursor.required_option("--service-name")?,
            version: cursor.required_option("--version")?,
            deprecation_date: cursor.option("--deprecation-date")?,
            migration_guide: cursor.option("--migration-guide")?,
        })),
        "list-versions" => Ok(CliCommand::Api(ApiCommand::ListVersions {
            service_name: cursor.option("--service-name")?,
            status: cursor.option("--status")?,
        })),
        "grpc-contract" => Ok(CliCommand::Api(ApiCommand::GrpcContract {
            proto_file: PathBuf::from(cursor.required("proto file")?),
            consumer: cursor.required_option("--consumer")?,
            provider: cursor.required_option("--provider")?,
            output_dir: cursor
                .option("--output-dir")?
                .map_or_else(|| PathBuf::from("contracts"), PathBuf::from),
        })),
        "contract-docs" => Ok(CliCommand::Api(ApiCommand::ContractDocs {
            contracts_dir: cursor
                .option("--contracts-dir")?
                .map_or_else(|| PathBuf::from("contracts"), PathBuf::from),
            docs_dir: cursor
                .option("--docs-dir")?
                .map_or_else(|| PathBuf::from("docs/contracts"), PathBuf::from),
            format: cursor
                .option("--format")?
                .unwrap_or_else(|| "markdown".into()),
        })),
        "monitor" => Ok(CliCommand::Api(ApiCommand::Monitor {
            providers: cursor
                .option("--providers")?
                .unwrap_or_default()
                .split(',')
                .filter(|value| !value.is_empty())
                .map(str::to_owned)
                .collect(),
            interval_seconds: parse_u64(cursor.option("--interval")?, 60, "interval")?,
            webhook_url: cursor.option("--webhook-url")?,
            fail_fast: cursor.flag("--fail-fast"),
        })),
        operation => Err(CliError::NotFound(format!("API operation {operation}"))),
    }
}

fn parse_migrate(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    match cursor.required("migration operation")?.as_str() {
        "helm-to-kustomize" => Ok(CliCommand::Migrate(MigrationCommand::HelmToKustomize {
            chart_path: PathBuf::from(cursor.required_option("--chart-path")?),
            output_path: PathBuf::from(cursor.required_option("--output-path")?),
            service_name: cursor.required_option("--service-name")?,
            namespace: cursor
                .option("--namespace")?
                .unwrap_or_else(|| "default".into()),
            environment: cursor
                .option("--environment")?
                .unwrap_or_else(|| "development".into()),
            validate: !cursor.flag("--no-validate"),
        })),
        "generate-overlay" => Ok(CliCommand::Migrate(MigrationCommand::GenerateOverlay {
            base_path: cursor
                .option("--base-path")?
                .map_or_else(|| PathBuf::from("k8s/base"), PathBuf::from),
            output_path: cursor
                .option("--output-path")?
                .map_or_else(|| PathBuf::from("k8s"), PathBuf::from),
            environment: cursor.required_option("--environment")?,
            namespace: cursor
                .option("--namespace")?
                .unwrap_or_else(|| "default".into()),
            replicas: parse_u32(cursor.option("--replicas")?, 1, "replicas")?,
            image_tag: cursor.option("--image-tag")?,
            marty_services: cursor.flag("--marty-services"),
        })),
        "validate" => Ok(CliCommand::Migrate(MigrationCommand::Validate {
            helm_path: PathBuf::from(cursor.required_option("--helm-path")?),
            kustomize_path: PathBuf::from(cursor.required_option("--kustomize-path")?),
            strict: cursor.flag("--strict"),
        })),
        "check-compatibility" => Ok(CliCommand::Migrate(MigrationCommand::CheckCompatibility {
            service_name: cursor.required("service name")?,
            chart_path: cursor.option("--chart-path")?.map(PathBuf::from),
        })),
        operation => Err(CliError::NotFound(format!(
            "migration operation {operation}"
        ))),
    }
}

fn parse_mesh(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    let operation = cursor.required("service-mesh operation")?;
    let mesh_type = cursor
        .option("--type")?
        .map_or(Ok(MeshType::Istio), |value| parse_mesh_type(&value))?;
    let namespace = cursor
        .option("--namespace")?
        .unwrap_or_else(|| "mmf-system".into());
    match operation.as_str() {
        "install" => Ok(CliCommand::ServiceMesh(ServiceMeshCommand::Install {
            mesh_type,
            namespace,
            cluster_name: cursor
                .option("--cluster-name")?
                .unwrap_or_else(|| "default".into()),
            monitoring: !cursor.flag("--no-monitoring"),
        })),
        "apply-policies" => Ok(CliCommand::ServiceMesh(ServiceMeshCommand::ApplyPolicies {
            mesh_type,
            namespace,
            service_name: cursor.option("--service")?,
            strict_mtls: !cursor.flag("--permissive-mtls"),
            authorization: !cursor.flag("--no-authorization"),
            rate_limit: cursor.flag("--rate-limit"),
        })),
        "status" => Ok(CliCommand::ServiceMesh(ServiceMeshCommand::Status {
            mesh_type,
            namespace,
        })),
        "generate" => Ok(CliCommand::ServiceMesh(ServiceMeshCommand::Generate {
            project_name: cursor.required_option("--project-name")?,
            output_dir: cursor
                .option("--output-dir")?
                .map_or_else(|| PathBuf::from("k8s/service-mesh"), PathBuf::from),
            domain: cursor
                .option("--domain")?
                .unwrap_or_else(|| "framework.local".into()),
            mesh_type,
            namespace,
        })),
        _ => Err(CliError::NotFound(format!(
            "service-mesh operation {operation}"
        ))),
    }
}

fn parse_plugin(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    match cursor.required("plugin operation")?.as_str() {
        "init" => Ok(CliCommand::Plugin(PluginCommand::Init {
            name: cursor.required_option("--name")?,
            features: repeated_or_csv(cursor, "--features")?,
            template: cursor
                .option("--template")?
                .unwrap_or_else(|| "minimal".into()),
            interactive: !cursor.flag("--no-interactive"),
        })),
        "list" => Ok(CliCommand::Plugin(PluginCommand::List)),
        "status" => Ok(CliCommand::Plugin(PluginCommand::Status {
            name: cursor.required("plugin name")?,
        })),
        "service-add" => Ok(CliCommand::Plugin(PluginCommand::ServiceAdd {
            plugin: cursor.required_option("--plugin")?,
            name: cursor.required_option("--name")?,
            service_type: cursor
                .option("--type")?
                .unwrap_or_else(|| "business".into()),
            features: repeated_or_csv(cursor, "--features")?,
        })),
        "service-list" => Ok(CliCommand::Plugin(PluginCommand::ServiceList {
            plugin: cursor.option("--plugin")?,
        })),
        operation => Err(CliError::NotFound(format!("plugin operation {operation}"))),
    }
}

fn parse_service(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    match cursor.required("service operation")?.as_str() {
        "init" => Ok(CliCommand::Service(ServiceCommand::Init {
            service_type: ServiceTemplate::parse(&cursor.required("service type")?)?,
            name: cursor.required("service name")?,
            description: cursor.option("--description")?.unwrap_or_default(),
            author: cursor
                .option("--author")?
                .unwrap_or_else(|| "Marty Development Team".into()),
            grpc_port: parse_u16(cursor.option("--grpc-port")?, 50_051, "gRPC port")?,
            http_port: parse_u16(cursor.option("--http-port")?, 8_080, "HTTP port")?,
            mesh_type: cursor
                .option("--service-mesh-type")?
                .map(|value| parse_mesh_type(&value))
                .transpose()?,
            namespace: cursor
                .option("--namespace")?
                .unwrap_or_else(|| "microservice-framework".into()),
            domain: cursor
                .option("--domain")?
                .unwrap_or_else(|| "framework.local".into()),
        })),
        "list" => Ok(CliCommand::Service(ServiceCommand::List)),
        "status" => Ok(CliCommand::Service(ServiceCommand::Status {
            name: cursor.required("service name")?,
        })),
        operation => Err(CliError::NotFound(format!("service operation {operation}"))),
    }
}

fn parse_security(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    match cursor.required("security operation")?.as_str() {
        "scan" => Ok(CliCommand::Security(SecurityCommand::Scan {
            service_path: cursor
                .option("--service-path")?
                .map_or_else(|| PathBuf::from("."), PathBuf::from),
        })),
        "policy-test" => Ok(CliCommand::Security(SecurityCommand::PolicyTest {
            principal: cursor.required_option("--principal")?,
            resource: cursor.required_option("--resource")?,
            action: cursor.required_option("--action")?,
        })),
        operation => Err(CliError::NotFound(format!(
            "security operation {operation}"
        ))),
    }
}

fn parse_database(cursor: &mut Arguments) -> Result<CliCommand, CliError> {
    match cursor.required("database operation")?.as_str() {
        "seed" => Ok(CliCommand::Database(DatabaseCommand::Seed {
            service_path: cursor
                .option("--service-path")?
                .map_or_else(|| PathBuf::from("."), PathBuf::from),
            host: cursor
                .option("--db-host")?
                .unwrap_or_else(|| "localhost".into()),
            port: parse_u16(cursor.option("--db-port")?, 5_432, "database port")?,
            database: cursor
                .option("--db-name")?
                .unwrap_or_else(|| "postgres".into()),
            user: cursor
                .option("--db-user")?
                .unwrap_or_else(|| "postgres".into()),
            password_secret: cursor.required_option("--db-password-secret")?,
        })),
        operation => Err(CliError::NotFound(format!(
            "database operation {operation}"
        ))),
    }
}

#[must_use]
pub fn command_help() -> &'static str {
    "Marty Rust CLI\n\nCommands:\n  new TEMPLATE NAME       Create a Rust MMF service\n  templates               List service templates\n  build                    Build the current project\n  test                     Run behavioral tests\n  run                      Run the current service\n  deploy                   Deploy with Kubernetes\n  info                     Show project information\n  config                   Manage and validate configuration\n  api                      Generate docs and manage contracts/versions\n  migrate                  Convert/generate deployment configuration\n  service-mesh             Install, inspect, and generate mesh policy\n  plugin                   Create and inspect MMF plugins\n  service                  Create and inspect services\n  security                 Scan or test policy\n  db                       Run explicit database operations\n"
}

struct Arguments {
    values: Vec<String>,
}

impl Arguments {
    fn new(values: &[String]) -> Self {
        Self {
            values: values.to_vec(),
        }
    }

    fn required(&mut self, label: &str) -> Result<String, CliError> {
        self.positional()
            .ok_or_else(|| CliError::InvalidInput(format!("missing {label}")))
    }

    fn positional(&mut self) -> Option<String> {
        let index = self
            .values
            .iter()
            .position(|value| !value.starts_with('-'))?;
        Some(self.values.remove(index))
    }

    fn positionals_until_option(&mut self) -> Vec<String> {
        let mut values = Vec::new();
        while self
            .values
            .first()
            .is_some_and(|value| !value.starts_with('-'))
        {
            values.push(self.values.remove(0));
        }
        values
    }

    fn flag(&mut self, name: &str) -> bool {
        self.values
            .iter()
            .position(|value| value == name)
            .is_some_and(|index| {
                self.values.remove(index);
                true
            })
    }

    fn option(&mut self, name: &str) -> Result<Option<String>, CliError> {
        let Some(index) = self.values.iter().position(|value| value == name) else {
            return Ok(None);
        };
        self.values.remove(index);
        if index >= self.values.len() || self.values[index].starts_with('-') {
            return Err(CliError::InvalidInput(format!("missing value for {name}")));
        }
        Ok(Some(self.values.remove(index)))
    }

    fn required_option(&mut self, name: &str) -> Result<String, CliError> {
        self.option(name)?
            .ok_or_else(|| CliError::InvalidInput(format!("missing {name}")))
    }
}

fn repeated_or_csv(cursor: &mut Arguments, name: &str) -> Result<Vec<String>, CliError> {
    Ok(cursor
        .option(name)?
        .unwrap_or_default()
        .split(',')
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
        .collect())
}

fn process(program: &str, arguments: Vec<String>, root: &Path) -> ProcessInvocation {
    ProcessInvocation {
        program: program.into(),
        arguments,
        working_directory: Some(root.to_path_buf()),
        environment: BTreeMap::new(),
    }
}

fn artifact(path: impl Into<PathBuf>, media_type: &str, content: String) -> GeneratedArtifact {
    GeneratedArtifact {
        relative_path: path.into(),
        media_type: media_type.into(),
        content,
    }
}

fn parse_category(value: &str) -> Result<TemplateCategory, CliError> {
    match value {
        "service" => Ok(TemplateCategory::Service),
        "infrastructure" => Ok(TemplateCategory::Infrastructure),
        "workflow" => Ok(TemplateCategory::Workflow),
        "plugin" => Ok(TemplateCategory::Plugin),
        _ => Err(CliError::InvalidInput(format!(
            "unknown template category {value}"
        ))),
    }
}

fn parse_environment(value: &str) -> Result<EnvironmentType, CliError> {
    match value {
        "development" | "dev" => Ok(EnvironmentType::Development),
        "testing" | "test" => Ok(EnvironmentType::Testing),
        "staging" => Ok(EnvironmentType::Staging),
        "beta" => Ok(EnvironmentType::Beta),
        "production" | "prod" => Ok(EnvironmentType::Production),
        "sandbox" => Ok(EnvironmentType::Sandbox),
        _ => Err(CliError::InvalidInput(format!(
            "unknown environment {value}"
        ))),
    }
}

const fn environment_name(value: EnvironmentType) -> &'static str {
    match value {
        EnvironmentType::Development => "development",
        EnvironmentType::Testing => "testing",
        EnvironmentType::Staging => "staging",
        EnvironmentType::Beta => "beta",
        EnvironmentType::Production => "production",
        EnvironmentType::Sandbox => "sandbox",
    }
}

fn parse_theme(value: &str) -> Result<DocumentationTheme, CliError> {
    match value {
        "redoc" => Ok(DocumentationTheme::Redoc),
        "swagger-ui" => Ok(DocumentationTheme::SwaggerUi),
        "stoplight" => Ok(DocumentationTheme::Stoplight),
        _ => Err(CliError::InvalidInput(format!(
            "unknown documentation theme {value}"
        ))),
    }
}

fn parse_mesh_type(value: &str) -> Result<MeshType, CliError> {
    match value {
        "istio" => Ok(MeshType::Istio),
        "linkerd" => Ok(MeshType::Linkerd),
        "consul" | "consul-connect" => Ok(MeshType::Consul),
        "kuma" => Ok(MeshType::Kuma),
        "none" => Ok(MeshType::None),
        _ => Err(CliError::InvalidInput(format!(
            "unknown service mesh {value}"
        ))),
    }
}

fn parse_u16(value: Option<String>, default: u16, label: &str) -> Result<u16, CliError> {
    value.map_or(Ok(default), |value| {
        value
            .parse()
            .map_err(|_| CliError::InvalidInput(format!("invalid {label}")))
    })
}

fn parse_optional_u16(value: Option<String>, label: &str) -> Result<Option<u16>, CliError> {
    value
        .map(|value| {
            value
                .parse()
                .map_err(|_| CliError::InvalidInput(format!("invalid {label}")))
        })
        .transpose()
}

fn parse_u32(value: Option<String>, default: u32, label: &str) -> Result<u32, CliError> {
    value.map_or(Ok(default), |value| {
        value
            .parse()
            .map_err(|_| CliError::InvalidInput(format!("invalid {label}")))
    })
}

fn parse_u64(value: Option<String>, default: u64, label: &str) -> Result<u64, CliError> {
    value.map_or(Ok(default), |value| {
        value
            .parse()
            .map_err(|_| CliError::InvalidInput(format!("invalid {label}")))
    })
}
