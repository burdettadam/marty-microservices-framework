//! Canonical, provider-neutral data infrastructure for MMF.
//!
//! Backend adapters implement these contracts for Redis, Memcached, SQL,
//! migrations, and cloud data services. Cache behavior, query semantics,
//! migration state, SQL safety, and normalized errors live here once.

#![forbid(unsafe_code)]

mod cache;
mod migration;
mod read_model;
mod sql;

pub use cache::*;
pub use migration::*;
pub use read_model::*;
pub use sql::*;

use mmf_core::{ErrorCode, MmfError};
use thiserror::Error;

#[derive(Clone, Debug, Error, PartialEq)]
pub enum DataError {
    #[error("invalid data configuration: {0}")]
    InvalidConfiguration(String),
    #[error("data provider unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("data record not found: {0}")]
    NotFound(String),
    #[error("data state conflict: {0}")]
    Conflict(String),
    #[error("serialization failed: {0}")]
    Serialization(String),
    #[error("invalid query: {0}")]
    InvalidQuery(String),
    #[error("migration failed: {0}")]
    Migration(String),
    #[error("data operation failed: {0}")]
    Operation(String),
}

impl From<DataError> for MmfError {
    fn from(error: DataError) -> Self {
        let code = match &error {
            DataError::InvalidConfiguration(_)
            | DataError::Serialization(_)
            | DataError::InvalidQuery(_) => ErrorCode::InvalidInput,
            DataError::ProviderUnavailable(_) => ErrorCode::DependencyUnavailable,
            DataError::NotFound(_) => ErrorCode::NotFound,
            DataError::Conflict(_) => ErrorCode::Conflict,
            DataError::Migration(_) | DataError::Operation(_) => ErrorCode::Internal,
        };
        MmfError::new(code, error.to_string())
    }
}
