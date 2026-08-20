//! Canonical orchestration for MMF's built-in services.
//!
//! Domain security primitives are reused from `mmf-security`; event delivery
//! is reused from `mmf-messaging`. JWT, TOTP, certificate, password-hashing,
//! and other cryptographic kernels must be supplied by native crypto providers
//! (normally `marty-core`) and are never reimplemented here.

#![forbid(unsafe_code)]

pub mod audit;
pub mod identity;

use mmf_core::{ErrorCode, MmfError};
use thiserror::Error;

#[derive(Clone, Debug, Eq, Error, PartialEq)]
pub enum ServiceError {
    #[error("invalid built-in service configuration: {0}")]
    InvalidConfiguration(String),
    #[error("required native service provider is unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("built-in service operation is unauthorized: {0}")]
    Unauthorized(String),
    #[error("built-in service state conflict: {0}")]
    Conflict(String),
    #[error("built-in service record was not found: {0}")]
    NotFound(String),
    #[error("built-in service operation failed: {0}")]
    Operation(String),
}

impl From<ServiceError> for MmfError {
    fn from(error: ServiceError) -> Self {
        let code = match &error {
            ServiceError::InvalidConfiguration(_) => ErrorCode::Configuration,
            ServiceError::ProviderUnavailable(_) => ErrorCode::DependencyUnavailable,
            ServiceError::Unauthorized(_) => ErrorCode::Unauthorized,
            ServiceError::Conflict(_) => ErrorCode::Conflict,
            ServiceError::NotFound(_) => ErrorCode::NotFound,
            ServiceError::Operation(_) => ErrorCode::Internal,
        };
        MmfError::new(code, error.to_string())
    }
}
