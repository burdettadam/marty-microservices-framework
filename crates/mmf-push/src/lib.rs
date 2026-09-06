//! Canonical push delivery, lifecycle, and provider adapter platform for MMF.
//!
//! Transport-independent routing, payload construction, retries, endpoint
//! protection, subscriptions, lifecycle events, and test doubles live here.
//! Network and credential effects are explicit provider ports.

#![forbid(unsafe_code)]

mod adapter_state;
mod fcm;
mod lifecycle;
mod manager;
mod mock;
mod model;
mod ports;
mod sse;
mod webhook;

pub use fcm::*;
pub use lifecycle::*;
pub use manager::*;
pub use mock::*;
pub use model::*;
pub use ports::*;
pub use sse::*;
pub use webhook::*;

use mmf_core::{ErrorCode, MmfError};
use thiserror::Error;

#[derive(Clone, Debug, Eq, Error, PartialEq)]
pub enum PushError {
    #[error("invalid push configuration: {0}")]
    InvalidConfiguration(String),
    #[error("push provider is unavailable: {0}")]
    ProviderUnavailable(String),
    #[error("push delivery failed: {0}")]
    Delivery(String),
    #[error("push operation is invalid: {0}")]
    InvalidOperation(String),
    #[error("push serialization failed: {0}")]
    Serialization(String),
    #[error("push destination is unavailable: {0}")]
    DestinationUnavailable(String),
}

impl From<PushError> for MmfError {
    fn from(error: PushError) -> Self {
        let code = match &error {
            PushError::InvalidConfiguration(_) => ErrorCode::Configuration,
            PushError::ProviderUnavailable(_) | PushError::DestinationUnavailable(_) => {
                ErrorCode::DependencyUnavailable
            }
            PushError::Delivery(_) | PushError::InvalidOperation(_) => ErrorCode::InvalidState,
            PushError::Serialization(_) => ErrorCode::InvalidInput,
        };
        Self::new(code, error.to_string())
    }
}

#[cfg(test)]
mod tests;
