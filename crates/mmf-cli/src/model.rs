use std::collections::BTreeMap;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::CliError;

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ApiEndpoint {
    pub path: String,
    pub method: String,
    pub summary: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub parameters: Vec<Value>,
    pub request_schema: Option<Value>,
    #[serde(default)]
    pub response_schemas: BTreeMap<String, Value>,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub deprecated: bool,
    pub deprecation_date: Option<String>,
    pub migration_guide: Option<String>,
    #[serde(default = "default_version")]
    pub version: String,
}

impl ApiEndpoint {
    pub fn validate(&self) -> Result<(), CliError> {
        if !self.path.starts_with('/')
            || self.method.trim().is_empty()
            || self.summary.trim().is_empty()
        {
            return Err(CliError::InvalidInput(
                "endpoint path, method, and summary are required".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StreamingMode {
    #[default]
    Unary,
    ClientStreaming,
    ServerStreaming,
    Bidirectional,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct GrpcMethod {
    pub name: String,
    pub full_name: String,
    pub input_type: String,
    pub output_type: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub streaming: StreamingMode,
    #[serde(default)]
    pub deprecated: bool,
    pub deprecation_date: Option<String>,
    pub migration_guide: Option<String>,
    #[serde(default = "default_version")]
    pub version: String,
}

impl GrpcMethod {
    pub fn validate(&self) -> Result<(), CliError> {
        if self.name.trim().is_empty()
            || self.full_name.trim().is_empty()
            || self.input_type.trim().is_empty()
            || self.output_type.trim().is_empty()
        {
            return Err(CliError::InvalidInput(
                "gRPC method name, full name, input, and output are required".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ApiService {
    pub name: String,
    pub version: String,
    pub description: String,
    #[serde(default)]
    pub base_url: String,
    #[serde(default)]
    pub endpoints: Vec<ApiEndpoint>,
    #[serde(default)]
    pub grpc_methods: Vec<GrpcMethod>,
    #[serde(default)]
    pub schemas: BTreeMap<String, Value>,
    pub contact: Option<BTreeMap<String, String>>,
    pub license: Option<BTreeMap<String, String>>,
    #[serde(default)]
    pub servers: Vec<BTreeMap<String, String>>,
    #[serde(default)]
    pub deprecated_versions: Vec<String>,
}

impl ApiService {
    pub fn validate(&self) -> Result<(), CliError> {
        if self.name.trim().is_empty()
            || self.version.trim().is_empty()
            || self.description.trim().is_empty()
        {
            return Err(CliError::InvalidInput(
                "service name, version, and description are required".into(),
            ));
        }
        self.endpoints.iter().try_for_each(ApiEndpoint::validate)?;
        self.grpc_methods.iter().try_for_each(GrpcMethod::validate)
    }
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum DocumentationTheme {
    #[default]
    Redoc,
    SwaggerUi,
    Stoplight,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct DocumentationConfig {
    pub output_dir: PathBuf,
    pub template_dir: Option<PathBuf>,
    pub include_examples: bool,
    pub include_schemas: bool,
    pub generate_postman: bool,
    pub generate_openapi: bool,
    pub generate_grpc_docs: bool,
    pub generate_unified_docs: bool,
    pub theme: DocumentationTheme,
    pub custom_css: Option<PathBuf>,
    pub custom_js: Option<PathBuf>,
}

impl Default for DocumentationConfig {
    fn default() -> Self {
        Self {
            output_dir: PathBuf::from("docs/api"),
            template_dir: None,
            include_examples: true,
            include_schemas: true,
            generate_postman: true,
            generate_openapi: true,
            generate_grpc_docs: true,
            generate_unified_docs: true,
            theme: DocumentationTheme::Redoc,
            custom_css: None,
            custom_js: None,
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct VersionRecord {
    pub created_at: String,
    pub status: VersionStatus,
    pub deprecation_date: Option<String>,
    pub migration_guide: Option<String>,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum VersionStatus {
    #[default]
    Active,
    Deprecated,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct VersionRegistry {
    #[serde(default)]
    pub services: BTreeMap<String, BTreeMap<String, VersionRecord>>,
}

impl VersionRegistry {
    pub fn register(
        &mut self,
        service: &str,
        version: &str,
        created_at: &str,
        deprecation_date: Option<String>,
        migration_guide: Option<String>,
    ) -> Result<(), CliError> {
        validate_token("service", service)?;
        validate_token("version", version)?;
        validate_token("created timestamp", created_at)?;
        self.services.entry(service.into()).or_default().insert(
            version.into(),
            VersionRecord {
                created_at: created_at.into(),
                status: VersionStatus::Active,
                deprecation_date,
                migration_guide,
            },
        );
        Ok(())
    }

    pub fn deprecate(
        &mut self,
        service: &str,
        version: &str,
        deprecation_date: &str,
        migration_guide: &str,
    ) -> Result<(), CliError> {
        validate_token("deprecation date", deprecation_date)?;
        validate_token("migration guide", migration_guide)?;
        let record = self
            .services
            .get_mut(service)
            .and_then(|versions| versions.get_mut(version))
            .ok_or_else(|| CliError::NotFound(format!("API version {service}/{version}")))?;
        record.status = VersionStatus::Deprecated;
        record.deprecation_date = Some(deprecation_date.into());
        record.migration_guide = Some(migration_guide.into());
        Ok(())
    }

    #[must_use]
    pub fn active_versions(&self, service: &str) -> Vec<String> {
        self.versions_by_status(service, VersionStatus::Active)
    }

    #[must_use]
    pub fn deprecated_versions(&self, service: &str) -> Vec<String> {
        self.versions_by_status(service, VersionStatus::Deprecated)
    }

    fn versions_by_status(&self, service: &str, status: VersionStatus) -> Vec<String> {
        self.services
            .get(service)
            .into_iter()
            .flat_map(|versions| versions.iter())
            .filter(|(_, record)| record.status == status)
            .map(|(version, _)| version.clone())
            .collect()
    }
}

pub(crate) fn validate_token(label: &str, value: &str) -> Result<(), CliError> {
    if value.trim().is_empty() || value.contains(['\0', '\n', '\r']) {
        Err(CliError::InvalidInput(format!("{label} is invalid")))
    } else {
        Ok(())
    }
}

fn default_version() -> String {
    "1.0.0".into()
}
