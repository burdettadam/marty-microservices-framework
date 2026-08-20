use std::collections::BTreeMap;
use std::env;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::time::{SystemTime, UNIX_EPOCH};

use mmf_cli::{
    ApiCommand, CliCommand, CliError, ContractType, GeneratedArtifact, HostEffects,
    MigrationCommand, NativeHost, PluginCommand, ProjectConfig, ScaffoldGenerator, ServiceCommand,
    ServiceMeshCommand, builtin_templates, command_help, create_contract, discover_apis,
    example_http_interaction, generate_documentation, grpc_contract_from_proto, parse_cli,
    plan_command, plugin_scaffold,
};

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("marty: {error}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), CliError> {
    let mut arguments = env::args().skip(1).collect::<Vec<_>>();
    if arguments.is_empty()
        || arguments
            .iter()
            .any(|value| matches!(value.as_str(), "--help" | "-h"))
    {
        print!("{}", command_help());
        return Ok(());
    }
    if arguments
        .iter()
        .any(|value| matches!(value.as_str(), "--version" | "-V"))
    {
        println!("marty {}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    let plan_only = remove_flag(&mut arguments, "--plan");
    let command = parse_cli(&arguments)?;
    let current = env::current_dir()
        .map_err(|error| CliError::Operation(format!("current directory: {error}")))?;
    let host = NativeHost::new(&current)?;
    if plan_only {
        let plan = plan_command(&command, &current)?;
        println!(
            "{}",
            serde_json::to_string_pretty(&plan)
                .map_err(|error| CliError::Operation(error.to_string()))?
        );
        return Ok(());
    }
    execute(command, &host, &current)
}

#[allow(clippy::too_many_lines)]
fn execute(command: CliCommand, host: &NativeHost, current: &Path) -> Result<(), CliError> {
    match command {
        CliCommand::New(config) => create_project(&config, host),
        CliCommand::Templates(query) => {
            let templates = builtin_templates()
                .into_iter()
                .filter(|template| {
                    query
                        .name
                        .as_ref()
                        .is_none_or(|name| &template.name == name)
                })
                .filter(|template| {
                    query
                        .category
                        .is_none_or(|category| template.category == category)
                })
                .collect::<Vec<_>>();
            println!(
                "{}",
                serde_json::to_string_pretty(&templates)
                    .map_err(|error| CliError::Operation(error.to_string()))?
            );
            Ok(())
        }
        CliCommand::Api(ApiCommand::Docs {
            source_paths,
            config,
            overwrite,
        }) => {
            let sources = host.read_sources(&source_paths)?;
            let services = discover_apis(&sources)?;
            let bundle = generate_documentation(&services, &config, &timestamp())?;
            let files = host.write_documentation(&config.output_dir, &bundle, overwrite)?;
            println!(
                "generated {} artifacts for {} services",
                files.len(),
                services.len()
            );
            Ok(())
        }
        CliCommand::Api(ApiCommand::CreateContract {
            consumer,
            provider,
            version,
            contract_type,
            ..
        }) => {
            let kind = parse_contract_type(&contract_type)?;
            let contract = create_contract(
                &consumer,
                &provider,
                &version,
                kind,
                vec![example_http_interaction()],
                BTreeMap::new(),
            )?;
            let filename = format!(
                "{}-{}-{}.json",
                safe_name(&consumer),
                safe_name(&provider),
                safe_name(&version)
            );
            write_json(host, Path::new("contracts"), &filename, &contract, false)
        }
        CliCommand::Api(ApiCommand::GrpcContract {
            proto_file,
            consumer,
            provider,
            output_dir,
        }) => {
            let sources = host.read_sources(std::slice::from_ref(&proto_file))?;
            let source = sources.first().ok_or_else(|| {
                CliError::NotFound(format!("proto file {}", proto_file.display()))
            })?;
            let contract =
                grpc_contract_from_proto(&source.content, &consumer, &provider, "1.0.0")?;
            let filename = format!(
                "{}-{}-grpc.json",
                safe_name(&consumer),
                safe_name(&provider)
            );
            write_json(host, &output_dir, &filename, &contract, false)
        }
        CliCommand::Migrate(MigrationCommand::GenerateOverlay {
            output_path,
            environment,
            namespace,
            replicas,
            image_tag,
            ..
        }) => {
            let artifacts = mmf_cli::generate_kustomize_overlay(
                &environment,
                &namespace,
                replicas,
                image_tag.as_deref(),
            )?;
            let files = host.write_artifacts(&output_path, &artifacts, false)?;
            println!("generated {} migration artifacts", files.len());
            Ok(())
        }
        CliCommand::ServiceMesh(ServiceMeshCommand::Generate {
            output_dir,
            project_name,
            domain,
            mesh_type,
            namespace,
        }) => {
            let artifacts =
                mmf_cli::generate_mesh_artifacts(&project_name, &domain, mesh_type, &namespace)?;
            let files = host.write_artifacts(&output_dir, &artifacts, false)?;
            println!("generated {} service-mesh artifacts", files.len());
            Ok(())
        }
        CliCommand::Plugin(PluginCommand::Init { name, features, .. }) => {
            let artifacts =
                plugin_scaffold(&name, "MMF plugin", "Marty Development Team", &features)?;
            let files =
                host.write_artifacts(&PathBuf::from("plugins").join(&name), &artifacts, false)?;
            println!("generated {} plugin files", files.len());
            Ok(())
        }
        CliCommand::Service(ServiceCommand::Init {
            service_type,
            name,
            description,
            author,
            grpc_port,
            http_port,
            ..
        }) => create_project(
            &ProjectConfig {
                name,
                template: service_type,
                output_path: PathBuf::from("services"),
                author,
                description,
                http_port,
                grpc_port,
                email: String::new(),
                license: "AGPL-3.0-only".into(),
                git_repository: String::new(),
                docker_enabled: true,
                kubernetes_enabled: true,
                monitoring_enabled: true,
                testing_enabled: true,
                ci_cd_enabled: true,
                environment: "development".into(),
                variables: BTreeMap::new(),
            },
            host,
        ),
        CliCommand::Build(_) | CliCommand::Test(_) | CliCommand::Run(_) | CliCommand::Deploy(_) => {
            execute_process_plan(&command, host, current)
        }
        unsupported => Err(CliError::ProviderUnavailable(format!(
            "{} requires a configured repository/provider adapter; use --plan to inspect the typed operation",
            unsupported.name()
        ))),
    }
}

fn create_project(config: &ProjectConfig, host: &NativeHost) -> Result<(), CliError> {
    let project = ScaffoldGenerator::generate(config)?;
    let files = host.write_project(&project, false)?;
    for invocation in &project.post_generation {
        let output = host.run(invocation)?;
        if output.status != 0 {
            return Err(CliError::Operation(format!(
                "post-generation command failed: {}",
                output.stderr
            )));
        }
    }
    println!(
        "created {} with {} files",
        project.root.display(),
        files.len()
    );
    Ok(())
}

fn execute_process_plan(
    command: &CliCommand,
    host: &NativeHost,
    current: &Path,
) -> Result<(), CliError> {
    let plan = plan_command(command, current)?;
    for process in &plan.processes {
        let output = host.run(process)?;
        print!("{}", output.stdout);
        eprint!("{}", output.stderr);
        if output.status != 0 {
            return Err(CliError::Operation(format!(
                "{} exited with status {}",
                process.program, output.status
            )));
        }
    }
    Ok(())
}

fn write_json<T: serde::Serialize>(
    host: &NativeHost,
    root: &Path,
    filename: &str,
    value: &T,
    overwrite: bool,
) -> Result<(), CliError> {
    let content = serde_json::to_string_pretty(value)
        .map_err(|error| CliError::Operation(error.to_string()))?;
    let artifact = GeneratedArtifact {
        relative_path: PathBuf::from(filename),
        media_type: "application/json".into(),
        content,
    };
    host.write_artifacts(root, &[artifact], overwrite)?;
    println!("wrote {}", root.join(filename).display());
    Ok(())
}

fn parse_contract_type(value: &str) -> Result<ContractType, CliError> {
    match value {
        "http" | "rest" => Ok(ContractType::Http),
        "grpc" => Ok(ContractType::Grpc),
        "event" => Ok(ContractType::Event),
        "message_queue" | "message-queue" => Ok(ContractType::MessageQueue),
        "graphql" => Ok(ContractType::Graphql),
        "websocket" => Ok(ContractType::Websocket),
        "database" => Ok(ContractType::Database),
        _ => Err(CliError::InvalidInput(format!(
            "unknown contract type {value}"
        ))),
    }
}

fn timestamp() -> String {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or_else(|_| "0".into(), |duration| duration.as_secs().to_string())
}

fn safe_name(value: &str) -> String {
    value
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || matches!(character, '-' | '_') {
                character
            } else {
                '-'
            }
        })
        .collect()
}

fn remove_flag(arguments: &mut Vec<String>, flag: &str) -> bool {
    arguments
        .iter()
        .position(|value| value == flag)
        .is_some_and(|index| {
            arguments.remove(index);
            true
        })
}
