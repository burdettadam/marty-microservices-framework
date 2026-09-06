use crate::{PushAdapterHealth, PushChannel, PushError, PushHealthStatus};
use mmf_resilience::{ConfiguredBackoff, RetryConfig, RetryStrategy};
use std::{future::Future, sync::RwLock};

#[derive(Default)]
pub(crate) struct AdapterState(RwLock<bool>);

impl AdapterState {
    pub(crate) fn set_running(&self, running: bool) {
        *self
            .0
            .write()
            .unwrap_or_else(std::sync::PoisonError::into_inner) = running;
    }

    pub(crate) async fn health<F: Future<Output = Result<(), PushError>>>(
        &self,
        channel: PushChannel,
        now_ms: u64,
        check: impl FnOnce() -> F,
    ) -> PushAdapterHealth {
        let running = *self
            .0
            .read()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let (status, detail) = if running {
            match check().await {
                Ok(()) => (PushHealthStatus::Healthy, None),
                Err(error) => (PushHealthStatus::Unavailable, Some(error.to_string())),
            }
        } else {
            (PushHealthStatus::Stopped, None)
        };
        PushAdapterHealth {
            channel,
            status,
            detail,
            checked_at_ms: now_ms,
        }
    }
}

pub(crate) fn adapter_backoff(
    max_attempts: u32,
    base_delay_ms: u64,
    max_delay_ms: u64,
) -> Result<ConfiguredBackoff, PushError> {
    ConfiguredBackoff::new(RetryConfig {
        max_attempts,
        base_delay_ms,
        max_delay_ms,
        strategy: RetryStrategy::Exponential,
        backoff_multiplier: 2.0,
        jitter: false,
        jitter_factor: 0.0,
    })
    .map_err(|error| PushError::InvalidConfiguration(error.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use mmf_resilience::BackoffPolicy;

    #[tokio::test]
    async fn stopped_state_does_not_invoke_health_factory() {
        let state = AdapterState::default();
        let called = std::cell::Cell::new(false);
        let health = state
            .health(PushChannel::Fcm, 1, || {
                called.set(true);
                async { Ok(()) }
            })
            .await;
        assert_eq!(health.status, PushHealthStatus::Stopped);
        assert!(!called.get());
    }

    #[test]
    fn retry_conversion_preserves_exponential_delay_and_cap() {
        let backoff = adapter_backoff(4, 10, 25).unwrap();
        assert_eq!(backoff.delay(1).as_millis(), 10);
        assert_eq!(backoff.delay(2).as_millis(), 20);
        assert_eq!(backoff.delay(3).as_millis(), 25);
        assert!(matches!(
            adapter_backoff(0, 10, 25),
            Err(PushError::InvalidConfiguration(_))
        ));
    }
}
