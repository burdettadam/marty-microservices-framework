use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};

use crate::{
    ApiEndpoint, ApiService, CliError, DocumentationConfig, DocumentationTheme, GrpcMethod,
    StreamingMode,
};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SourceDocument {
    pub path: PathBuf,
    pub content: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct GeneratedArtifact {
    pub relative_path: PathBuf,
    pub media_type: String,
    pub content: String,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct DocumentationBundle {
    pub services: Vec<ApiService>,
    pub artifacts: Vec<GeneratedArtifact>,
}

impl DocumentationBundle {
    pub fn validate(&self) -> Result<(), CliError> {
        for artifact in &self.artifacts {
            validate_relative_path(&artifact.relative_path)?;
        }
        Ok(())
    }

    #[must_use]
    pub fn artifact(&self, path: &str) -> Option<&GeneratedArtifact> {
        self.artifacts
            .iter()
            .find(|artifact| artifact.relative_path == Path::new(path))
    }
}

pub fn discover_apis(sources: &[SourceDocument]) -> Result<Vec<ApiService>, CliError> {
    let mut services = BTreeMap::<String, ApiService>::new();
    for source in sources {
        match source
            .path
            .extension()
            .and_then(|extension| extension.to_str())
        {
            Some("py") => {
                if let Some(service) = parse_fastapi_source(&source.path, &source.content)? {
                    merge_service(&mut services, service);
                }
            }
            Some("proto") => {
                for service in parse_proto_source(&source.content)? {
                    merge_service(&mut services, service);
                }
            }
            _ => {}
        }
    }
    Ok(services.into_values().collect())
}

fn merge_service(services: &mut BTreeMap<String, ApiService>, incoming: ApiService) {
    if let Some(existing) = services.get_mut(&incoming.name) {
        existing.endpoints.extend(incoming.endpoints);
        existing.grpc_methods.extend(incoming.grpc_methods);
        existing.schemas.extend(incoming.schemas);
        if existing.base_url.is_empty() {
            existing.base_url = incoming.base_url;
        }
    } else {
        services.insert(incoming.name.clone(), incoming);
    }
}

pub fn parse_fastapi_source(path: &Path, content: &str) -> Result<Option<ApiService>, CliError> {
    if !content.contains("FastAPI") {
        return Ok(None);
    }
    let constructor = Regex::new(r"(?s)(?:\w+\s*=\s*)?FastAPI\s*\((.*?)\)")
        .map_err(|error| CliError::Operation(error.to_string()))?;
    let Some(arguments) = constructor
        .captures(content)
        .and_then(|captures| captures.get(1))
        .map(|capture| capture.as_str())
    else {
        return Ok(None);
    };
    let fallback = path
        .parent()
        .and_then(Path::file_name)
        .and_then(|name| name.to_str())
        .unwrap_or("service");
    let name = quoted_argument(arguments, "title").unwrap_or_else(|| fallback.into());
    let version = quoted_argument(arguments, "version").unwrap_or_else(|| "1.0.0".into());
    let description =
        quoted_argument(arguments, "description").unwrap_or_else(|| "FastAPI Service".into());
    let route = Regex::new(
        r#"(?m)^\s*@(?:app|router)\.(get|post|put|delete|patch|head|options)\(\s*['\"]([^'\"]+)['\"]([^)]*)\)\s*(?:\r?\n)\s*(?:async\s+)?def\s+(\w+)"#,
    )
    .map_err(|error| CliError::Operation(error.to_string()))?;
    let endpoints = route
        .captures_iter(content)
        .map(|captures| {
            let method = captures[1].to_uppercase();
            let path = captures[2].to_owned();
            let options = captures.get(3).map_or("", |capture| capture.as_str());
            let function = captures[4].replace('_', " ");
            ApiEndpoint {
                path,
                method,
                summary: quoted_argument(options, "summary")
                    .unwrap_or_else(|| title_case(&function)),
                description: quoted_argument(options, "description").unwrap_or_default(),
                tags: list_argument(options, "tags"),
                deprecated: bool_argument(options, "deprecated"),
                version: version.clone(),
                ..ApiEndpoint::default()
            }
        })
        .collect();
    let service = ApiService {
        name,
        version,
        description,
        base_url: "http://localhost:8000".into(),
        endpoints,
        ..ApiService::default()
    };
    service.validate()?;
    Ok(Some(service))
}

fn quoted_argument(arguments: &str, key: &str) -> Option<String> {
    let expression = Regex::new(&format!(r#"{key}\s*=\s*['\"]([^'\"]*)['\"]"#)).ok()?;
    expression
        .captures(arguments)
        .and_then(|captures| captures.get(1))
        .map(|capture| capture.as_str().to_owned())
}

fn bool_argument(arguments: &str, key: &str) -> bool {
    Regex::new(&format!(r"(?i){key}\s*=\s*true"))
        .is_ok_and(|expression| expression.is_match(arguments))
}

fn list_argument(arguments: &str, key: &str) -> Vec<String> {
    let Ok(expression) = Regex::new(&format!(r"{key}\s*=\s*\[([^]]*)\]")) else {
        return Vec::new();
    };
    expression
        .captures(arguments)
        .and_then(|captures| captures.get(1))
        .map_or_else(Vec::new, |capture| {
            capture
                .as_str()
                .split(',')
                .map(|value| value.trim().trim_matches(['\'', '"']).to_owned())
                .filter(|value| !value.is_empty())
                .collect()
        })
}

pub fn parse_proto_source(content: &str) -> Result<Vec<ApiService>, CliError> {
    let package = Regex::new(r"package\s+([^;\s]+)\s*;")
        .map_err(|error| CliError::Operation(error.to_string()))?
        .captures(content)
        .and_then(|captures| captures.get(1))
        .map_or("unknown", |capture| capture.as_str());
    let service_expression = Regex::new(r"(?s)service\s+(\w+)\s*\{(.*?)\}")
        .map_err(|error| CliError::Operation(error.to_string()))?;
    let method_expression = Regex::new(
        r"rpc\s+(\w+)\s*\(\s*(stream\s+)?([\w.]+)\s*\)\s*returns\s*\(\s*(stream\s+)?([\w.]+)\s*\)",
    )
    .map_err(|error| CliError::Operation(error.to_string()))?;
    let services = service_expression
        .captures_iter(content)
        .map(|service_capture| {
            let service_name = service_capture[1].to_owned();
            let body = &service_capture[2];
            let grpc_methods = method_expression
                .captures_iter(body)
                .map(|method_capture| {
                    let client_streaming = method_capture.get(2).is_some();
                    let server_streaming = method_capture.get(4).is_some();
                    let streaming = match (client_streaming, server_streaming) {
                        (true, true) => StreamingMode::Bidirectional,
                        (true, false) => StreamingMode::ClientStreaming,
                        (false, true) => StreamingMode::ServerStreaming,
                        (false, false) => StreamingMode::Unary,
                    };
                    let method_name = method_capture[1].to_owned();
                    GrpcMethod {
                        name: method_name.clone(),
                        full_name: format!("{package}.{service_name}.{method_name}"),
                        input_type: method_capture[3].to_owned(),
                        output_type: method_capture[5].to_owned(),
                        description: format!("gRPC method {method_name}"),
                        streaming,
                        version: "1.0.0".into(),
                        ..GrpcMethod::default()
                    }
                })
                .collect();
            ApiService {
                name: service_name.clone(),
                version: "1.0.0".into(),
                description: format!("gRPC service {service_name}"),
                grpc_methods,
                ..ApiService::default()
            }
        })
        .collect::<Vec<_>>();
    for service in &services {
        service.validate()?;
    }
    Ok(services)
}

pub fn generate_documentation(
    services: &[ApiService],
    config: &DocumentationConfig,
    generated_at: &str,
) -> Result<DocumentationBundle, CliError> {
    if generated_at.trim().is_empty() {
        return Err(CliError::InvalidInput(
            "documentation timestamp is required".into(),
        ));
    }
    let mut bundle = DocumentationBundle {
        services: services.to_vec(),
        artifacts: Vec::new(),
    };
    for service in services {
        service.validate()?;
        let slug = safe_slug(&service.name)?;
        if !service.endpoints.is_empty() {
            let spec = openapi_spec(service, config.include_schemas)?;
            push_json(&mut bundle, format!("{slug}-openapi.json"), &spec)?;
            if config.generate_openapi {
                push_text(
                    &mut bundle,
                    format!("{slug}-docs.html"),
                    "text/html",
                    &render_openapi_html(service, &spec, config, generated_at),
                );
            }
            if config.generate_postman {
                push_json(
                    &mut bundle,
                    format!("{slug}-postman.json"),
                    &postman_collection(service),
                )?;
            }
        }
        if !service.grpc_methods.is_empty() && config.generate_grpc_docs {
            push_text(
                &mut bundle,
                format!("{slug}-grpc-docs.html"),
                "text/html",
                &render_grpc_html(service, generated_at),
            );
            if config.include_examples {
                push_text(
                    &mut bundle,
                    format!("{slug}-grpc-clients.md"),
                    "text/markdown",
                    &render_grpc_clients(service),
                );
            }
        }
        if config.generate_unified_docs {
            push_text(
                &mut bundle,
                format!("{slug}-unified-docs.html"),
                "text/html",
                &render_unified_html(service, generated_at),
            );
        }
        if !service.endpoints.is_empty() && !service.grpc_methods.is_empty() {
            push_text(
                &mut bundle,
                format!("{slug}-gateway.yaml"),
                "application/yaml",
                &grpc_gateway_yaml(service),
            );
        }
    }
    push_text(
        &mut bundle,
        "index.html".into(),
        "text/html",
        &render_index(services, generated_at),
    );
    bundle.validate()?;
    Ok(bundle)
}

pub fn openapi_spec(service: &ApiService, include_schemas: bool) -> Result<Value, CliError> {
    service.validate()?;
    let mut info = Map::from_iter([
        ("title".into(), json!(service.name)),
        ("version".into(), json!(service.version)),
        ("description".into(), json!(service.description)),
    ]);
    if let Some(contact) = &service.contact {
        info.insert("contact".into(), json!(contact));
    }
    if let Some(license) = &service.license {
        info.insert("license".into(), json!(license));
    }
    let servers = if service.servers.is_empty() {
        json!([{ "url": service.base_url }])
    } else {
        json!(service.servers)
    };
    let mut paths = Map::new();
    for endpoint in &service.endpoints {
        let mut operation = Map::from_iter([
            ("summary".into(), json!(endpoint.summary)),
            ("description".into(), json!(endpoint.description)),
            ("tags".into(), json!(endpoint.tags)),
            ("parameters".into(), json!(endpoint.parameters)),
            ("responses".into(), json!(endpoint.response_schemas)),
        ]);
        if let Some(schema) = &endpoint.request_schema {
            operation.insert(
                "requestBody".into(),
                json!({"content": {"application/json": {"schema": schema}}}),
            );
        }
        if endpoint.deprecated {
            operation.insert("deprecated".into(), json!(true));
            if let Some(date) = &endpoint.deprecation_date {
                operation.insert("x-deprecation-date".into(), json!(date));
            }
            if let Some(guide) = &endpoint.migration_guide {
                operation.insert("x-migration-guide".into(), json!(guide));
            }
        }
        let path = paths
            .entry(endpoint.path.clone())
            .or_insert_with(|| Value::Object(Map::new()));
        let Some(path) = path.as_object_mut() else {
            return Err(CliError::Operation("OpenAPI path was not an object".into()));
        };
        path.insert(endpoint.method.to_lowercase(), Value::Object(operation));
    }
    Ok(json!({
        "openapi": "3.0.3",
        "info": info,
        "servers": servers,
        "paths": paths,
        "components": {"schemas": if include_schemas { json!(service.schemas) } else { json!({}) }}
    }))
}

#[must_use]
pub fn postman_collection(service: &ApiService) -> Value {
    let items = service
        .endpoints
        .iter()
        .map(|endpoint| {
            let host = service
                .base_url
                .trim_start_matches("https://")
                .trim_start_matches("http://");
            let mut request = json!({
                "method": endpoint.method.to_uppercase(),
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "url": {
                    "raw": format!("{}{}", service.base_url, endpoint.path),
                    "host": [host],
                    "path": endpoint.path.trim_matches('/').split('/').filter(|part| !part.is_empty()).collect::<Vec<_>>()
                }
            });
            if endpoint.request_schema.is_some() {
                request["body"] = json!({
                    "mode": "raw",
                    "raw": "{\n  \"example\": \"Add your request data here\"\n}"
                });
            }
            json!({"name": endpoint.summary, "request": request})
        })
        .collect::<Vec<_>>();
    json!({
        "info": {
            "name": service.name,
            "description": service.description,
            "version": service.version,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": items
    })
}

#[must_use]
pub fn grpc_gateway_yaml(service: &ApiService) -> String {
    let mut output = format!(
        "type: google.api.Service\nconfig_version: 3\nname: {}.api\ntitle: {:?}\ndescription: {:?}\napis:\n  - name: {:?}\n    version: {:?}\nhttp:\n  rules:\n",
        safe_identifier(&service.name),
        format!("{} API", service.name),
        service.description,
        service.name,
        service.version
    );
    for method in &service.grpc_methods {
        let _ = write!(
            output,
            "    - selector: {:?}\n      post: /api/v1/{}\n      body: \"*\"\n",
            method.full_name,
            method.name.to_lowercase()
        );
    }
    output
}

fn render_openapi_html(
    service: &ApiService,
    spec: &Value,
    config: &DocumentationConfig,
    generated_at: &str,
) -> String {
    let theme = match config.theme {
        DocumentationTheme::Redoc => "redoc",
        DocumentationTheme::SwaggerUi => "swagger-ui",
        DocumentationTheme::Stoplight => "stoplight",
    };
    format!(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>{name} API</title></head><body data-theme=\"{theme}\"><h1>{name}</h1><p>Version: {version}</p><pre id=\"openapi\">{spec}</pre><footer>Generated {generated}</footer></body></html>",
        name = escape_html(&service.name),
        version = escape_html(&service.version),
        spec = escape_html(&serde_json::to_string_pretty(spec).unwrap_or_default()),
        generated = escape_html(generated_at)
    )
}

fn render_grpc_html(service: &ApiService, generated_at: &str) -> String {
    let methods = service
        .grpc_methods
        .iter()
        .fold(String::new(), |mut output, method| {
            let _ = write!(
                output,
                "<article><h2>{}</h2><code>{}({}) returns ({})</code><p>{:?}</p></article>",
                escape_html(&method.name),
                escape_html(&method.full_name),
                escape_html(&method.input_type),
                escape_html(&method.output_type),
                method.streaming
            );
            output
        });
    format!(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>{0} gRPC Documentation</title></head><body><h1>{0} gRPC API</h1><p>Version: {1}</p>{methods}<footer>Generated {2}</footer></body></html>",
        escape_html(&service.name),
        escape_html(&service.version),
        escape_html(generated_at)
    )
}

fn render_grpc_clients(service: &ApiService) -> String {
    let methods = service
        .grpc_methods
        .iter()
        .fold(String::new(), |mut output, method| {
            let _ = writeln!(
                output,
                "- `{}`: `{} -> {}`",
                method.name, method.input_type, method.output_type
            );
            output
        });
    format!(
        "# {} gRPC Client Examples\n\nVersion: {}\n\n## Methods\n\n{}\n## Python\n\n```python\nchannel = grpc.secure_channel('your-service:443', credentials)\nstub = {}Stub(channel)\n```\n\n## JavaScript\n\n```javascript\nconst client = new proto.{}('your-service:443', credentials);\n```\n\n## Go\n\n```go\nclient := pb.New{}Client(conn)\n```\n\n## Java\n\n```java\n{}Grpc.newBlockingStub(channel);\n```\n",
        service.name,
        service.version,
        methods,
        service.name,
        service.name,
        service.name,
        service.name
    )
}

fn render_unified_html(service: &ApiService, generated_at: &str) -> String {
    format!(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>{0} unified API</title></head><body><h1>{0}</h1><p>Version: {1}</p><section data-rest=\"{2}\">REST endpoints: {3}</section><section data-grpc=\"{4}\">gRPC methods: {5}</section><footer>Generated {6}</footer></body></html>",
        escape_html(&service.name),
        escape_html(&service.version),
        !service.endpoints.is_empty(),
        service.endpoints.len(),
        !service.grpc_methods.is_empty(),
        service.grpc_methods.len(),
        escape_html(generated_at)
    )
}

fn render_index(services: &[ApiService], generated_at: &str) -> String {
    let cards = services.iter().fold(String::new(), |mut output, service| {
        let slug = safe_identifier(&service.name);
        let _ = write!(
            output,
            "<li><a href=\"{slug}-unified-docs.html\">{}</a> v{} — {} REST / {} gRPC</li>",
            escape_html(&service.name),
            escape_html(&service.version),
            service.endpoints.len(),
            service.grpc_methods.len()
        );
        output
    });
    format!(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>MMF API Documentation</title></head><body><h1>API Documentation</h1><ul>{cards}</ul><footer>Generated {}</footer></body></html>",
        escape_html(generated_at)
    )
}

fn push_json(
    bundle: &mut DocumentationBundle,
    path: String,
    value: &Value,
) -> Result<(), CliError> {
    let content = serde_json::to_string_pretty(value)
        .map_err(|error| CliError::Operation(error.to_string()))?;
    push_text(bundle, path, "application/json", &content);
    Ok(())
}

fn push_text(bundle: &mut DocumentationBundle, path: String, media_type: &str, content: &str) {
    bundle.artifacts.push(GeneratedArtifact {
        relative_path: PathBuf::from(path),
        media_type: media_type.into(),
        content: content.into(),
    });
}

fn validate_relative_path(path: &Path) -> Result<(), CliError> {
    if path.is_absolute()
        || path
            .components()
            .any(|component| matches!(component, std::path::Component::ParentDir))
    {
        Err(CliError::InvalidInput(format!(
            "generated path escapes output directory: {}",
            path.display()
        )))
    } else {
        Ok(())
    }
}

fn safe_slug(name: &str) -> Result<String, CliError> {
    let slug = safe_identifier(name);
    if slug.is_empty() {
        Err(CliError::InvalidInput(
            "service name has no safe characters".into(),
        ))
    } else {
        Ok(slug)
    }
}

fn safe_identifier(value: &str) -> String {
    value
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || character == '-' || character == '_' {
                character.to_ascii_lowercase()
            } else {
                '-'
            }
        })
        .collect::<String>()
        .trim_matches('-')
        .to_owned()
}

fn escape_html(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

fn title_case(value: &str) -> String {
    value
        .split_whitespace()
        .map(|word| {
            let mut characters = word.chars();
            characters.next().map_or_else(String::new, |first| {
                format!("{}{}", first.to_ascii_uppercase(), characters.as_str())
            })
        })
        .collect::<Vec<_>>()
        .join(" ")
}
