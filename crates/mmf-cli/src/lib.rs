//! Canonical MMF documentation, contract, scaffolding, and developer CLI platform.

#![forbid(unsafe_code)]

mod command;
mod contracts;
mod documentation;
mod host;
mod model;
mod scaffold;
mod template;

pub use command::*;
pub use contracts::*;
pub use documentation::*;
pub use host::*;
pub use model::*;
pub use scaffold::*;
pub use template::*;

pub use mmf_platform::{EnvironmentType, InfrastructureAsCodeProvider, MeshType};
pub use mmf_plugins::PluginMetadata;
pub use mmf_testkit::{
    Contract, ContractInteraction, ContractMismatch, ContractRequest, ContractResponse,
    ContractType, VerificationLevel, verify_response,
};

use thiserror::Error;

#[derive(Clone, Debug, Eq, Error, PartialEq)]
pub enum CliError {
    #[error("invalid CLI input: {0}")]
    InvalidInput(String),
    #[error("unsupported CLI operation: {0}")]
    Unsupported(String),
    #[error("CLI conflict: {0}")]
    Conflict(String),
    #[error("CLI resource not found: {0}")]
    NotFound(String),
    #[error("CLI provider unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("CLI operation failed: {0}")]
    Operation(String),
}

#[cfg(test)]
mod tests;
