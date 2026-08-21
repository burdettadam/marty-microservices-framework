//! Canonical MMF plugin platform.

#![forbid(unsafe_code)]

mod config;
mod manager;
mod model;
mod ports;
mod registry;

pub use config::*;
pub use manager::*;
pub use model::*;
pub use ports::*;
pub use registry::*;

use thiserror::Error;

#[derive(Clone, Debug, Eq, Error, PartialEq)]
pub enum PluginError {
    #[error("invalid plugin input: {0}")]
    InvalidInput(String),
    #[error("plugin not found: {0}")]
    NotFound(String),
    #[error("plugin conflict: {0}")]
    Conflict(String),
    #[error("plugin dependency error: {0}")]
    Dependency(String),
    #[error("invalid plugin lifecycle transition: {0}")]
    InvalidTransition(String),
    #[error("plugin provider unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("plugin operation failed: {0}")]
    Operation(String),
}

#[cfg(test)]
mod tests;
