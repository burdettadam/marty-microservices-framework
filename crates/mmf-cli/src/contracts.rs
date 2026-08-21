use std::collections::BTreeMap;
use std::fmt::Write as _;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::{
    CliError, Contract, ContractInteraction, ContractMismatch, ContractRequest, ContractResponse,
    ContractType, GrpcMethod, VerificationLevel, parse_proto_source, validate_token,
    verify_response,
};

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct ContractRegistry {
    #[serde(default)]
    contracts: Vec<Contract>,
}

impl ContractRegistry {
    pub fn register(&mut self, contract: Contract) -> Result<(), CliError> {
        contract
            .validate()
            .map_err(|error| CliError::InvalidInput(error.to_string()))?;
        let key = contract_key(&contract);
        if self
            .contracts
            .iter()
            .any(|existing| contract_key(existing) == key)
        {
            return Err(CliError::Conflict(format!(
                "contract already registered: {key}"
            )));
        }
        self.contracts.push(contract);
        self.contracts.sort_by_key(contract_key);
        Ok(())
    }

    #[must_use]
    pub fn list(&self, query: &ContractQuery) -> Vec<&Contract> {
        self.contracts
            .iter()
            .filter(|contract| {
                query
                    .consumer
                    .as_ref()
                    .is_none_or(|consumer| &contract.consumer == consumer)
                    && query
                        .provider
                        .as_ref()
                        .is_none_or(|provider| &contract.provider == provider)
                    && query
                        .version
                        .as_ref()
                        .is_none_or(|version| &contract.version == version)
                    && query
                        .contract_type
                        .is_none_or(|kind| contract.contract_type == kind)
            })
            .collect()
    }

    pub fn remove(
        &mut self,
        consumer: &str,
        provider: &str,
        version: &str,
    ) -> Result<Contract, CliError> {
        let index = self
            .contracts
            .iter()
            .position(|contract| {
                contract.consumer == consumer
                    && contract.provider == provider
                    && contract.version == version
            })
            .ok_or_else(|| {
                CliError::NotFound(format!("contract {consumer}/{provider}/{version}"))
            })?;
        Ok(self.contracts.remove(index))
    }

    pub fn to_json(&self) -> Result<String, CliError> {
        serde_json::to_string_pretty(self).map_err(|error| CliError::Operation(error.to_string()))
    }

    pub fn from_json(value: &str) -> Result<Self, CliError> {
        let registry: Self = serde_json::from_str(value).map_err(|error| {
            CliError::InvalidInput(format!("invalid contract registry: {error}"))
        })?;
        for contract in &registry.contracts {
            contract
                .validate()
                .map_err(|error| CliError::InvalidInput(error.to_string()))?;
        }
        Ok(registry)
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ContractQuery {
    pub consumer: Option<String>,
    pub provider: Option<String>,
    pub version: Option<String>,
    pub contract_type: Option<ContractType>,
}

pub fn create_contract(
    consumer: &str,
    provider: &str,
    version: &str,
    contract_type: ContractType,
    interactions: Vec<ContractInteraction>,
    metadata: BTreeMap<String, String>,
) -> Result<Contract, CliError> {
    let contract = Contract {
        consumer: consumer.into(),
        provider: provider.into(),
        version: version.into(),
        contract_type,
        interactions,
        metadata,
    };
    contract
        .validate()
        .map_err(|error| CliError::InvalidInput(error.to_string()))?;
    Ok(contract)
}

pub fn grpc_contract_from_proto(
    proto: &str,
    consumer: &str,
    provider: &str,
    version: &str,
) -> Result<Contract, CliError> {
    validate_token("consumer", consumer)?;
    validate_token("provider", provider)?;
    validate_token("version", version)?;
    let interactions = parse_proto_source(proto)?
        .into_iter()
        .flat_map(|service| service.grpc_methods)
        .map(|method| grpc_interaction(&method))
        .collect::<Vec<_>>();
    if interactions.is_empty() {
        return Err(CliError::InvalidInput(
            "proto contains no gRPC methods".into(),
        ));
    }
    create_contract(
        consumer,
        provider,
        version,
        ContractType::Grpc,
        interactions,
        BTreeMap::from([("source".into(), "protobuf".into())]),
    )
}

fn grpc_interaction(method: &GrpcMethod) -> ContractInteraction {
    ContractInteraction {
        description: format!("{} contract", method.full_name),
        provider_state: None,
        request: ContractRequest {
            method: "RPC".into(),
            path: format!("/{}", method.full_name.replace('.', "/")),
            headers: BTreeMap::new(),
            body: json!({"type": method.input_type, "streaming": method.streaming}),
        },
        response: ContractResponse {
            status_code: 200,
            headers: BTreeMap::new(),
            body: json!({"type": method.output_type}),
        },
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct InteractionResult {
    pub description: String,
    pub passed: bool,
    #[serde(default)]
    pub mismatches: Vec<ContractMismatch>,
    pub error: Option<String>,
    pub duration_ms: u64,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ContractTestResult {
    pub consumer: String,
    pub provider: String,
    pub version: String,
    pub passed: bool,
    pub interactions: Vec<InteractionResult>,
}

#[async_trait]
pub trait ContractExecutor: Send + Sync {
    async fn execute(
        &self,
        contract: &Contract,
        interaction: &ContractInteraction,
    ) -> Result<ExecutedInteraction, CliError>;
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ExecutedInteraction {
    pub response: ContractResponse,
    pub duration_ms: u64,
}

pub async fn test_contract(
    contract: &Contract,
    level: VerificationLevel,
    executor: &dyn ContractExecutor,
) -> ContractTestResult {
    let mut interactions = Vec::with_capacity(contract.interactions.len());
    for interaction in &contract.interactions {
        let result = executor.execute(contract, interaction).await;
        interactions.push(match result {
            Ok(actual) => {
                let mismatches = verify_response(&interaction.response, &actual.response, level);
                InteractionResult {
                    description: interaction.description.clone(),
                    passed: mismatches.is_empty(),
                    mismatches,
                    error: None,
                    duration_ms: actual.duration_ms,
                }
            }
            Err(error) => InteractionResult {
                description: interaction.description.clone(),
                passed: false,
                mismatches: Vec::new(),
                error: Some(error.to_string()),
                duration_ms: 0,
            },
        });
    }
    ContractTestResult {
        consumer: contract.consumer.clone(),
        provider: contract.provider.clone(),
        version: contract.version.clone(),
        passed: !interactions.is_empty() && interactions.iter().all(|result| result.passed),
        interactions,
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ContractTestSummary {
    pub passed: bool,
    pub contracts: usize,
    pub interactions: usize,
    pub failed_interactions: usize,
    pub results: Vec<ContractTestResult>,
}

#[must_use]
pub fn summarize_contract_tests(results: Vec<ContractTestResult>) -> ContractTestSummary {
    let interactions = results.iter().map(|result| result.interactions.len()).sum();
    let failed_interactions = results
        .iter()
        .flat_map(|result| &result.interactions)
        .filter(|interaction| !interaction.passed)
        .count();
    ContractTestSummary {
        passed: !results.is_empty() && failed_interactions == 0,
        contracts: results.len(),
        interactions,
        failed_interactions,
        results,
    }
}

#[must_use]
pub fn junit_report(summary: &ContractTestSummary) -> String {
    let failures = summary.failed_interactions;
    let mut cases = String::new();
    for contract in &summary.results {
        for interaction in &contract.interactions {
            let name = xml_escape(&interaction.description);
            let class = xml_escape(&format!("{}.{}", contract.consumer, contract.provider));
            let seconds = interaction.duration_ms / 1_000;
            let milliseconds = interaction.duration_ms % 1_000;
            let _ = write!(
                cases,
                "  <testcase classname=\"{class}\" name=\"{name}\" time=\"{seconds}.{milliseconds:03}\">"
            );
            if !interaction.passed {
                let message = interaction.error.clone().unwrap_or_else(|| {
                    interaction
                        .mismatches
                        .iter()
                        .map(|mismatch| {
                            format!(
                                "{} expected {} actual {}",
                                mismatch.path, mismatch.expected, mismatch.actual
                            )
                        })
                        .collect::<Vec<_>>()
                        .join("; ")
                });
                let _ = write!(cases, "<failure message=\"{}\" />", xml_escape(&message));
            }
            cases.push_str("</testcase>\n");
        }
    }
    format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<testsuite name=\"mmf-contracts\" tests=\"{}\" failures=\"{failures}\">\n{cases}</testsuite>\n",
        summary.interactions
    )
}

#[must_use]
pub fn contract_documentation(contracts: &[&Contract]) -> String {
    let mut output = String::from("# API Contracts\n\n");
    for contract in contracts {
        let _ = write!(
            output,
            "## {} -> {} ({})\n\nType: `{:?}`\n\n",
            contract.consumer, contract.provider, contract.version, contract.contract_type
        );
        for interaction in &contract.interactions {
            let _ = writeln!(
                output,
                "- **{}** - `{}` `{}` -> `{}`",
                interaction.description,
                interaction.request.method,
                interaction.request.path,
                interaction.response.status_code
            );
        }
        output.push('\n');
    }
    output
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ContractMonitorConfig {
    pub providers: Vec<String>,
    pub interval_seconds: u64,
    pub webhook_url: Option<String>,
    pub fail_fast: bool,
    pub verification_level: VerificationLevel,
}

impl ContractMonitorConfig {
    pub fn validate(&self) -> Result<(), CliError> {
        if self.providers.is_empty() || self.interval_seconds == 0 {
            return Err(CliError::InvalidInput(
                "contract monitor requires providers and a positive interval".into(),
            ));
        }
        if self
            .webhook_url
            .as_ref()
            .is_some_and(|url| !url.starts_with("https://"))
        {
            return Err(CliError::InvalidInput(
                "contract monitor webhook must use HTTPS".into(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ContractMonitorEvent {
    pub provider: String,
    pub passed: bool,
    pub failed_interactions: usize,
    pub checked_at: String,
    pub notification_required: bool,
}

pub fn monitor_event(
    provider: &str,
    summary: &ContractTestSummary,
    checked_at: &str,
) -> Result<ContractMonitorEvent, CliError> {
    validate_token("provider", provider)?;
    validate_token("checked timestamp", checked_at)?;
    Ok(ContractMonitorEvent {
        provider: provider.into(),
        passed: summary.passed,
        failed_interactions: summary.failed_interactions,
        checked_at: checked_at.into(),
        notification_required: !summary.passed,
    })
}

fn contract_key(contract: &Contract) -> String {
    format!(
        "{}/{}/{}/{:?}",
        contract.consumer, contract.provider, contract.version, contract.contract_type
    )
}

fn xml_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

#[must_use]
pub fn example_http_interaction() -> ContractInteraction {
    ContractInteraction {
        description: "health endpoint".into(),
        provider_state: None,
        request: ContractRequest {
            method: "GET".into(),
            path: "/health".into(),
            headers: BTreeMap::new(),
            body: Value::Null,
        },
        response: ContractResponse {
            status_code: 200,
            headers: BTreeMap::from([("content-type".into(), "application/json".into())]),
            body: json!({"status": "healthy"}),
        },
    }
}
