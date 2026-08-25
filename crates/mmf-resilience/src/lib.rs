//! Shared retry, circuit-breaker, bulkhead, timeout, and fallback primitives.
//!
//! The crate owns resilience behavior for every MMF service. Consumers compose
//! these primitives instead of carrying service-local implementations.

#![forbid(unsafe_code)]

use std::collections::VecDeque;
use std::fmt::Debug;
use std::future::Future;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use async_trait::async_trait;
use mmf_core::{ErrorCode, MmfError};
use rand::RngExt;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use tokio::sync::{OwnedSemaphorePermit, Semaphore};

/// Deployment-oriented presets. Callers may still override every setting.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ResilienceStrategy {
    InternalService,
    ExternalService,
    Database,
    Cache,
    Custom,
}

/// Built-in retry delay algorithms.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RetryStrategy {
    Exponential,
    Linear,
    Constant,
    Custom,
}

/// Configurable retry policy. `max_attempts` includes the initial call.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct RetryConfig {
    pub max_attempts: u32,
    pub base_delay_ms: u64,
    pub max_delay_ms: u64,
    pub strategy: RetryStrategy,
    pub backoff_multiplier: f64,
    pub jitter: bool,
    pub jitter_factor: f64,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            base_delay_ms: 1_000,
            max_delay_ms: 60_000,
            strategy: RetryStrategy::Exponential,
            backoff_multiplier: 2.0,
            jitter: true,
            jitter_factor: 0.1,
        }
    }
}

impl RetryConfig {
    pub fn validate(&self) -> Result<(), MmfError> {
        if self.max_attempts == 0 {
            return Err(invalid_config(
                "retry.max_attempts must be greater than zero",
            ));
        }
        if self.max_delay_ms < self.base_delay_ms {
            return Err(invalid_config(
                "retry.max_delay_ms must be greater than or equal to base_delay_ms",
            ));
        }
        if !self.backoff_multiplier.is_finite() || self.backoff_multiplier < 1.0 {
            return Err(invalid_config(
                "retry.backoff_multiplier must be finite and at least 1.0",
            ));
        }
        if !self.jitter_factor.is_finite() || !(0.0..=1.0).contains(&self.jitter_factor) {
            return Err(invalid_config(
                "retry.jitter_factor must be finite and between 0.0 and 1.0",
            ));
        }
        Ok(())
    }
}

/// A delay policy allows services with special requirements to supply custom backoff.
pub trait BackoffPolicy: Send + Sync {
    fn delay(&self, attempt: u32) -> Duration;
}

/// Backoff generated directly from [`RetryConfig`].
#[derive(Clone, Debug)]
pub struct ConfiguredBackoff {
    config: RetryConfig,
}

impl ConfiguredBackoff {
    pub fn new(config: RetryConfig) -> Result<Self, MmfError> {
        config.validate()?;
        if config.strategy == RetryStrategy::Custom {
            return Err(invalid_config(
                "custom retry strategy requires a caller-provided BackoffPolicy",
            ));
        }
        Ok(Self { config })
    }

    /// Deterministic calculation used by cross-language behavior contracts.
    /// `jitter_sample` is clamped to `-1.0..=1.0`.
    #[must_use]
    #[allow(clippy::cast_precision_loss)]
    pub fn delay_with_sample(&self, attempt: u32, jitter_sample: f64) -> Duration {
        let attempt = attempt.max(1);
        let base = self.config.base_delay_ms as f64;
        let raw = match self.config.strategy {
            RetryStrategy::Constant | RetryStrategy::Custom => base,
            RetryStrategy::Linear => base * f64::from(attempt),
            RetryStrategy::Exponential => {
                let exponent = i32::try_from(attempt.saturating_sub(1)).unwrap_or(i32::MAX);
                base * self.config.backoff_multiplier.powi(exponent)
            }
        };
        let capped = raw.min(self.config.max_delay_ms as f64);
        let jittered = if self.config.jitter {
            let sample = if jitter_sample.is_finite() {
                jitter_sample.clamp(-1.0, 1.0)
            } else {
                0.0
            };
            capped * (1.0 + sample * self.config.jitter_factor)
        } else {
            capped
        };
        Duration::from_secs_f64((jittered.max(0.0)) / 1_000.0)
    }
}

impl BackoffPolicy for ConfiguredBackoff {
    fn delay(&self, attempt: u32) -> Duration {
        let sample = if self.config.jitter {
            rand::rng().random_range(-1.0..=1.0)
        } else {
            0.0
        };
        self.delay_with_sample(attempt, sample)
    }
}

/// Circuit-breaker states exposed for health and metrics reporting.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CircuitState {
    Closed,
    Open,
    HalfOpen,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
pub struct CircuitBreakerConfig {
    pub failure_threshold: u32,
    pub success_threshold: u32,
    pub failure_window_ms: u64,
    pub open_timeout_ms: u64,
    pub use_failure_rate: bool,
    pub failure_rate_threshold: f64,
    pub minimum_requests: u32,
}

impl Default for CircuitBreakerConfig {
    fn default() -> Self {
        Self {
            failure_threshold: 5,
            success_threshold: 3,
            failure_window_ms: 60_000,
            open_timeout_ms: 60_000,
            use_failure_rate: false,
            failure_rate_threshold: 0.5,
            minimum_requests: 10,
        }
    }
}

impl CircuitBreakerConfig {
    pub fn validate(&self) -> Result<(), MmfError> {
        if self.failure_threshold == 0 || self.success_threshold == 0 {
            return Err(invalid_config(
                "circuit-breaker thresholds must be greater than zero",
            ));
        }
        if self.failure_window_ms == 0 || self.open_timeout_ms == 0 {
            return Err(invalid_config(
                "circuit-breaker windows must be greater than zero",
            ));
        }
        if !self.failure_rate_threshold.is_finite()
            || !(0.0..=1.0).contains(&self.failure_rate_threshold)
        {
            return Err(invalid_config(
                "circuit-breaker failure rate must be between 0.0 and 1.0",
            ));
        }
        if self.use_failure_rate && self.minimum_requests == 0 {
            return Err(invalid_config(
                "circuit-breaker minimum_requests must be greater than zero",
            ));
        }
        Ok(())
    }
}

#[derive(Debug)]
struct CircuitInner {
    state: CircuitState,
    consecutive_failures: u32,
    half_open_successes: u32,
    opened_at: Option<Instant>,
    outcomes: VecDeque<(Instant, bool)>,
}

/// Thread-safe circuit breaker with count-based and failure-rate modes.
#[derive(Clone, Debug)]
pub struct CircuitBreaker {
    name: Arc<str>,
    config: CircuitBreakerConfig,
    inner: Arc<Mutex<CircuitInner>>,
}

impl CircuitBreaker {
    pub fn new(name: impl Into<Arc<str>>, config: CircuitBreakerConfig) -> Result<Self, MmfError> {
        config.validate()?;
        Ok(Self {
            name: name.into(),
            config,
            inner: Arc::new(Mutex::new(CircuitInner {
                state: CircuitState::Closed,
                consecutive_failures: 0,
                half_open_successes: 0,
                opened_at: None,
                outcomes: VecDeque::new(),
            })),
        })
    }

    #[must_use]
    pub fn state(&self) -> CircuitState {
        self.lock_inner().state
    }

    /// Returns an error while open; after the timeout, atomically grants a
    /// half-open probe. Concurrent half-open probes are intentionally allowed,
    /// matching the former MMF behavior.
    pub fn allow_call_at(&self, now: Instant) -> Result<(), ResilienceError> {
        let mut inner = self.lock_inner();
        if inner.state == CircuitState::Open {
            let timed_out = inner.opened_at.is_some_and(|opened| {
                now.saturating_duration_since(opened)
                    >= Duration::from_millis(self.config.open_timeout_ms)
            });
            if timed_out {
                inner.state = CircuitState::HalfOpen;
                inner.half_open_successes = 0;
            } else {
                return Err(ResilienceError::CircuitOpen {
                    name: self.name.to_string(),
                    failure_count: inner.consecutive_failures,
                });
            }
        }
        Ok(())
    }

    pub fn record_success_at(&self, now: Instant) {
        let mut inner = self.lock_inner();
        Self::prune_outcomes(&mut inner, now, self.config.failure_window_ms);
        inner.outcomes.push_back((now, true));
        inner.consecutive_failures = 0;
        if inner.state == CircuitState::HalfOpen {
            inner.half_open_successes = inner.half_open_successes.saturating_add(1);
            if inner.half_open_successes >= self.config.success_threshold {
                inner.state = CircuitState::Closed;
                inner.opened_at = None;
                inner.half_open_successes = 0;
                inner.outcomes.clear();
            }
        }
    }

    pub fn record_failure_at(&self, now: Instant) {
        let mut inner = self.lock_inner();
        Self::prune_outcomes(&mut inner, now, self.config.failure_window_ms);
        inner.outcomes.push_back((now, false));
        inner.consecutive_failures = inner.consecutive_failures.saturating_add(1);

        let should_open = if inner.state == CircuitState::HalfOpen {
            true
        } else if self.config.use_failure_rate {
            let request_count = u32::try_from(inner.outcomes.len()).unwrap_or(u32::MAX);
            let failures = u32::try_from(
                inner
                    .outcomes
                    .iter()
                    .filter(|(_, success)| !success)
                    .count(),
            )
            .unwrap_or(u32::MAX);
            request_count >= self.config.minimum_requests
                && (f64::from(failures) / f64::from(request_count))
                    >= self.config.failure_rate_threshold
        } else {
            inner.consecutive_failures >= self.config.failure_threshold
        };

        if should_open {
            inner.state = CircuitState::Open;
            inner.opened_at = Some(now);
            inner.half_open_successes = 0;
        }
    }

    pub async fn call<T, E, F, Fut>(&self, operation: F) -> Result<T, ExecutionError<E>>
    where
        E: Debug,
        F: FnOnce() -> Fut,
        Fut: Future<Output = Result<T, E>>,
    {
        self.allow_call_at(Instant::now())
            .map_err(ExecutionError::Resilience)?;
        match operation().await {
            Ok(value) => {
                self.record_success_at(Instant::now());
                Ok(value)
            }
            Err(error) => {
                self.record_failure_at(Instant::now());
                Err(ExecutionError::Operation(error))
            }
        }
    }

    fn prune_outcomes(inner: &mut CircuitInner, now: Instant, window_ms: u64) {
        let window = Duration::from_millis(window_ms);
        while inner
            .outcomes
            .front()
            .is_some_and(|(time, _)| now.saturating_duration_since(*time) > window)
        {
            inner.outcomes.pop_front();
        }
    }

    fn lock_inner(&self) -> std::sync::MutexGuard<'_, CircuitInner> {
        self.inner
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct BulkheadConfig {
    pub max_concurrent: usize,
    pub acquisition_timeout_ms: u64,
    pub execution_timeout_ms: u64,
    pub reject_on_full: bool,
}

impl Default for BulkheadConfig {
    fn default() -> Self {
        Self {
            max_concurrent: 10,
            acquisition_timeout_ms: 30_000,
            execution_timeout_ms: 30_000,
            reject_on_full: false,
        }
    }
}

impl BulkheadConfig {
    pub fn validate(&self) -> Result<(), MmfError> {
        if self.max_concurrent == 0 {
            return Err(invalid_config(
                "bulkhead.max_concurrent must be greater than zero",
            ));
        }
        if self.execution_timeout_ms == 0 {
            return Err(invalid_config(
                "bulkhead.execution_timeout_ms must be greater than zero",
            ));
        }
        Ok(())
    }
}

#[derive(Default, Debug)]
struct BulkheadCounters {
    accepted: AtomicU64,
    completed: AtomicU64,
    failed: AtomicU64,
    rejected: AtomicU64,
    timed_out: AtomicU64,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct BulkheadMetrics {
    pub accepted: u64,
    pub completed: u64,
    pub failed: u64,
    pub rejected: u64,
    pub timed_out: u64,
    pub active: usize,
    pub capacity: usize,
}

/// Async semaphore bulkhead. Blocking work can be wrapped with
/// `tokio::task::spawn_blocking` by the service runtime before submission.
#[derive(Clone, Debug)]
pub struct Bulkhead {
    name: Arc<str>,
    config: BulkheadConfig,
    semaphore: Arc<Semaphore>,
    counters: Arc<BulkheadCounters>,
}

impl Bulkhead {
    pub fn new(name: impl Into<Arc<str>>, config: BulkheadConfig) -> Result<Self, MmfError> {
        config.validate()?;
        Ok(Self {
            name: name.into(),
            semaphore: Arc::new(Semaphore::new(config.max_concurrent)),
            counters: Arc::new(BulkheadCounters::default()),
            config,
        })
    }

    pub async fn execute<T, E, F>(&self, operation: F) -> Result<T, ExecutionError<E>>
    where
        E: Debug,
        F: Future<Output = Result<T, E>>,
    {
        let permit = self.acquire().await.map_err(ExecutionError::Resilience)?;
        self.counters.accepted.fetch_add(1, Ordering::Relaxed);
        let result = tokio::time::timeout(
            Duration::from_millis(self.config.execution_timeout_ms),
            operation,
        )
        .await;
        drop(permit);

        match result {
            Ok(Ok(value)) => {
                self.counters.completed.fetch_add(1, Ordering::Relaxed);
                Ok(value)
            }
            Ok(Err(error)) => {
                self.counters.failed.fetch_add(1, Ordering::Relaxed);
                Err(ExecutionError::Operation(error))
            }
            Err(_) => {
                self.counters.timed_out.fetch_add(1, Ordering::Relaxed);
                Err(ExecutionError::Resilience(ResilienceError::Timeout {
                    operation: self.name.to_string(),
                    timeout_ms: self.config.execution_timeout_ms,
                }))
            }
        }
    }

    #[must_use]
    pub fn metrics(&self) -> BulkheadMetrics {
        BulkheadMetrics {
            accepted: self.counters.accepted.load(Ordering::Relaxed),
            completed: self.counters.completed.load(Ordering::Relaxed),
            failed: self.counters.failed.load(Ordering::Relaxed),
            rejected: self.counters.rejected.load(Ordering::Relaxed),
            timed_out: self.counters.timed_out.load(Ordering::Relaxed),
            active: self
                .config
                .max_concurrent
                .saturating_sub(self.semaphore.available_permits()),
            capacity: self.config.max_concurrent,
        }
    }

    async fn acquire(&self) -> Result<OwnedSemaphorePermit, ResilienceError> {
        let result = if self.config.reject_on_full {
            self.semaphore.clone().try_acquire_owned().map_err(|_| ())
        } else {
            match tokio::time::timeout(
                Duration::from_millis(self.config.acquisition_timeout_ms),
                self.semaphore.clone().acquire_owned(),
            )
            .await
            {
                Ok(permit) => permit.map_err(|_| ()),
                Err(_) => Err(()),
            }
        };

        result.map_err(|()| {
            self.counters.rejected.fetch_add(1, Ordering::Relaxed);
            ResilienceError::BulkheadRejected {
                name: self.name.to_string(),
                capacity: self.config.max_concurrent,
            }
        })
    }
}

/// A fallback strategy is independent of the primary operation's error type.
#[async_trait]
pub trait Fallback<T, E>: Send + Sync {
    fn name(&self) -> &str;
    async fn execute(&self, original_error: &E) -> Result<T, String>;
}

#[derive(Clone, Debug)]
pub struct StaticFallback<T> {
    name: String,
    value: T,
}

impl<T> StaticFallback<T> {
    #[must_use]
    pub fn new(name: impl Into<String>, value: T) -> Self {
        Self {
            name: name.into(),
            value,
        }
    }
}

#[async_trait]
impl<T, E> Fallback<T, E> for StaticFallback<T>
where
    T: Clone + Send + Sync,
    E: Sync,
{
    fn name(&self) -> &str {
        &self.name
    }

    async fn execute(&self, _original_error: &E) -> Result<T, String> {
        Ok(self.value.clone())
    }
}

pub struct FunctionFallback<F> {
    name: String,
    function: F,
}

impl<F> FunctionFallback<F> {
    pub fn new(name: impl Into<String>, function: F) -> Self {
        Self {
            name: name.into(),
            function,
        }
    }
}

#[async_trait]
impl<T, E, F, Fut> Fallback<T, E> for FunctionFallback<F>
where
    T: Send,
    E: Sync,
    F: Fn() -> Fut + Send + Sync,
    Fut: Future<Output = Result<T, String>> + Send,
{
    fn name(&self) -> &str {
        &self.name
    }

    async fn execute(&self, _original_error: &E) -> Result<T, String> {
        (self.function)().await
    }
}

pub struct CacheFallback<F> {
    name: String,
    lookup: F,
}

impl<F> CacheFallback<F> {
    pub fn new(name: impl Into<String>, lookup: F) -> Self {
        Self {
            name: name.into(),
            lookup,
        }
    }
}

#[async_trait]
impl<T, E, F, Fut> Fallback<T, E> for CacheFallback<F>
where
    T: Send,
    E: Sync,
    F: Fn() -> Fut + Send + Sync,
    Fut: Future<Output = Result<Option<T>, String>> + Send,
{
    fn name(&self) -> &str {
        &self.name
    }

    async fn execute(&self, _original_error: &E) -> Result<T, String> {
        (self.lookup)()
            .await?
            .ok_or_else(|| format!("cache fallback '{}' missed", self.name))
    }
}

/// Ordered cache/function/static fallback chains use the same trait and stop
/// at the first successful strategy.
pub struct FallbackChain<T, E> {
    name: String,
    max_attempts: usize,
    strategies: Vec<Arc<dyn Fallback<T, E>>>,
}

impl<T, E> FallbackChain<T, E> {
    #[must_use]
    pub fn new(name: impl Into<String>, max_attempts: usize) -> Self {
        Self {
            name: name.into(),
            max_attempts,
            strategies: Vec::new(),
        }
    }

    pub fn push(&mut self, fallback: Arc<dyn Fallback<T, E>>) {
        self.strategies.push(fallback);
    }
}

impl<T, E> FallbackChain<T, E>
where
    T: Send,
    E: Sync,
{
    pub async fn execute(&self, original_error: &E) -> Result<T, ResilienceError> {
        let mut failures = Vec::new();
        let limit = self.max_attempts.min(self.strategies.len());
        for strategy in self.strategies.iter().take(limit) {
            match strategy.execute(original_error).await {
                Ok(value) => return Ok(value),
                Err(error) => failures.push(format!("{}: {error}", strategy.name())),
            }
        }
        Err(ResilienceError::FallbackExhausted {
            name: self.name.clone(),
            attempts: limit,
            failures,
        })
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(default)]
#[allow(clippy::struct_excessive_bools)]
pub struct ResilienceConfig {
    pub strategy: ResilienceStrategy,
    pub retry: RetryConfig,
    pub circuit_breaker: CircuitBreakerConfig,
    pub bulkhead: BulkheadConfig,
    pub retry_enabled: bool,
    pub circuit_breaker_enabled: bool,
    pub bulkhead_enabled: bool,
    pub timeout_enabled: bool,
    pub timeout_ms: u64,
}

impl Default for ResilienceConfig {
    fn default() -> Self {
        Self {
            strategy: ResilienceStrategy::InternalService,
            retry: RetryConfig::default(),
            circuit_breaker: CircuitBreakerConfig::default(),
            bulkhead: BulkheadConfig::default(),
            retry_enabled: true,
            circuit_breaker_enabled: true,
            bulkhead_enabled: false,
            timeout_enabled: true,
            timeout_ms: 30_000,
        }
    }
}

impl ResilienceConfig {
    pub fn validate(&self) -> Result<(), MmfError> {
        self.retry.validate()?;
        self.circuit_breaker.validate()?;
        self.bulkhead.validate()?;
        if self.timeout_enabled && self.timeout_ms == 0 {
            return Err(invalid_config("timeout_ms must be greater than zero"));
        }
        Ok(())
    }
}

#[derive(Default, Debug)]
struct ManagerCounters {
    total_calls: AtomicU64,
    successful_calls: AtomicU64,
    failed_calls: AtomicU64,
    retry_count: AtomicU64,
    circuit_open_count: AtomicU64,
    timeout_count: AtomicU64,
    bulkhead_rejected_count: AtomicU64,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ResilienceMetrics {
    pub total_calls: u64,
    pub successful_calls: u64,
    pub failed_calls: u64,
    pub retry_count: u64,
    pub circuit_open_count: u64,
    pub timeout_count: u64,
    pub bulkhead_rejected_count: u64,
}

/// Canonical composition order: outer timeout, then retry, circuit breaker,
/// bulkhead, and finally the protected operation.
#[derive(Clone, Debug)]
pub struct ResilienceManager {
    name: Arc<str>,
    config: ResilienceConfig,
    backoff: ConfiguredBackoff,
    circuit_breaker: Option<CircuitBreaker>,
    bulkhead: Option<Bulkhead>,
    counters: Arc<ManagerCounters>,
}

impl ResilienceManager {
    pub fn new(name: impl Into<Arc<str>>, config: ResilienceConfig) -> Result<Self, MmfError> {
        config.validate()?;
        let name = name.into();
        let backoff = ConfiguredBackoff::new(config.retry.clone())?;
        let circuit_breaker = config
            .circuit_breaker_enabled
            .then(|| CircuitBreaker::new(name.clone(), config.circuit_breaker.clone()))
            .transpose()?;
        let bulkhead = config
            .bulkhead_enabled
            .then(|| Bulkhead::new(name.clone(), config.bulkhead.clone()))
            .transpose()?;
        Ok(Self {
            name,
            config,
            backoff,
            circuit_breaker,
            bulkhead,
            counters: Arc::new(ManagerCounters::default()),
        })
    }

    pub async fn execute<T, E, F, Fut, P>(
        &self,
        mut operation: F,
        retryable: P,
    ) -> Result<T, ExecutionError<E>>
    where
        E: Debug,
        F: FnMut() -> Fut,
        Fut: Future<Output = Result<T, E>>,
        P: Fn(&E) -> bool,
    {
        self.counters.total_calls.fetch_add(1, Ordering::Relaxed);
        let execution = async {
            let attempts = if self.config.retry_enabled {
                self.config.retry.max_attempts
            } else {
                1
            };

            for attempt in 1..=attempts {
                let result = self.execute_attempt(operation()).await;
                match result {
                    Ok(value) => return Ok(value),
                    Err(ExecutionError::Operation(error)) => {
                        if attempt == attempts || !retryable(&error) {
                            return Err(ExecutionError::RetryExhausted {
                                attempts: attempt,
                                last_error: error,
                            });
                        }
                        self.counters.retry_count.fetch_add(1, Ordering::Relaxed);
                        tokio::time::sleep(self.backoff.delay(attempt)).await;
                    }
                    Err(error) => return Err(error),
                }
            }
            unreachable!("validated retry attempts are non-zero")
        };

        let result = if self.config.timeout_enabled {
            if let Ok(result) =
                tokio::time::timeout(Duration::from_millis(self.config.timeout_ms), execution).await
            {
                result
            } else {
                self.counters.timeout_count.fetch_add(1, Ordering::Relaxed);
                Err(ExecutionError::Resilience(ResilienceError::Timeout {
                    operation: self.name.to_string(),
                    timeout_ms: self.config.timeout_ms,
                }))
            }
        } else {
            execution.await
        };

        if result.is_ok() {
            self.counters
                .successful_calls
                .fetch_add(1, Ordering::Relaxed);
        } else {
            self.counters.failed_calls.fetch_add(1, Ordering::Relaxed);
            match &result {
                Err(ExecutionError::Resilience(ResilienceError::CircuitOpen { .. })) => {
                    self.counters
                        .circuit_open_count
                        .fetch_add(1, Ordering::Relaxed);
                }
                Err(ExecutionError::Resilience(ResilienceError::BulkheadRejected { .. })) => {
                    self.counters
                        .bulkhead_rejected_count
                        .fetch_add(1, Ordering::Relaxed);
                }
                _ => {}
            }
        }
        result
    }

    #[must_use]
    pub fn metrics(&self) -> ResilienceMetrics {
        ResilienceMetrics {
            total_calls: self.counters.total_calls.load(Ordering::Relaxed),
            successful_calls: self.counters.successful_calls.load(Ordering::Relaxed),
            failed_calls: self.counters.failed_calls.load(Ordering::Relaxed),
            retry_count: self.counters.retry_count.load(Ordering::Relaxed),
            circuit_open_count: self.counters.circuit_open_count.load(Ordering::Relaxed),
            timeout_count: self.counters.timeout_count.load(Ordering::Relaxed),
            bulkhead_rejected_count: self
                .counters
                .bulkhead_rejected_count
                .load(Ordering::Relaxed),
        }
    }

    async fn execute_attempt<T, E, Fut>(&self, operation: Fut) -> Result<T, ExecutionError<E>>
    where
        E: Debug,
        Fut: Future<Output = Result<T, E>>,
    {
        if let Some(circuit) = &self.circuit_breaker {
            circuit
                .allow_call_at(Instant::now())
                .map_err(ExecutionError::Resilience)?;
        }

        let result = if let Some(bulkhead) = &self.bulkhead {
            bulkhead.execute(operation).await
        } else {
            operation.await.map_err(ExecutionError::Operation)
        };

        if let Some(circuit) = &self.circuit_breaker {
            match &result {
                Ok(_) => circuit.record_success_at(Instant::now()),
                Err(ExecutionError::Operation(_)) => circuit.record_failure_at(Instant::now()),
                _ => {}
            }
        }
        result
    }
}

#[derive(Debug, Error)]
pub enum ResilienceError {
    #[error("circuit breaker '{name}' is open after {failure_count} failures")]
    CircuitOpen { name: String, failure_count: u32 },
    #[error("bulkhead '{name}' rejected work at capacity {capacity}")]
    BulkheadRejected { name: String, capacity: usize },
    #[error("operation '{operation}' timed out after {timeout_ms}ms")]
    Timeout { operation: String, timeout_ms: u64 },
    #[error("fallback chain '{name}' exhausted {attempts} attempts: {failures:?}")]
    FallbackExhausted {
        name: String,
        attempts: usize,
        failures: Vec<String>,
    },
}

impl From<ResilienceError> for MmfError {
    fn from(error: ResilienceError) -> Self {
        MmfError::new(ErrorCode::DependencyUnavailable, error.to_string())
    }
}

#[derive(Debug, Error)]
pub enum ExecutionError<E: Debug> {
    #[error("operation failed: {0:?}")]
    Operation(E),
    #[error("operation exhausted {attempts} attempts; last error: {last_error:?}")]
    RetryExhausted { attempts: u32, last_error: E },
    #[error(transparent)]
    Resilience(#[from] ResilienceError),
}

fn invalid_config(message: &str) -> MmfError {
    MmfError::new(ErrorCode::Configuration, message)
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicU32, Ordering};

    use super::*;

    #[derive(Deserialize)]
    struct BehaviorFixture {
        backoff_cases: Vec<BackoffCase>,
        circuit_breaker: CircuitFixture,
        retry: RetryFixture,
        bulkhead: BulkheadFixture,
        fallback_order: Vec<String>,
    }

    #[derive(Deserialize)]
    struct BackoffCase {
        strategy: RetryStrategy,
        base_ms: u64,
        max_ms: u64,
        multiplier: f64,
        attempt: u32,
        expected_ms: u64,
    }

    #[derive(Deserialize)]
    struct CircuitFixture {
        failure_threshold: u32,
        success_threshold: u32,
        open_after_failures: u32,
        half_open_after_timeout: bool,
        close_after_half_open_successes: u32,
        reject_while_open: bool,
    }

    #[derive(Deserialize)]
    struct RetryFixture {
        max_attempts: u32,
        failures_before_success: u32,
        expected_attempts: u32,
        non_retryable_expected_attempts: u32,
    }

    #[derive(Deserialize)]
    struct BulkheadFixture {
        max_concurrent: usize,
        reject_on_full: bool,
        expected_rejections: u64,
    }

    fn fixture() -> BehaviorFixture {
        serde_json::from_str(include_str!("../../../contracts/resilience-behavior.json"))
            .expect("valid resilience fixture")
    }

    #[test]
    fn language_neutral_backoff_contract() {
        for case in fixture().backoff_cases {
            let config = RetryConfig {
                base_delay_ms: case.base_ms,
                max_delay_ms: case.max_ms,
                strategy: case.strategy,
                backoff_multiplier: case.multiplier,
                jitter: false,
                ..RetryConfig::default()
            };
            let backoff = ConfiguredBackoff::new(config).expect("valid backoff");
            let actual = u64::try_from(backoff.delay_with_sample(case.attempt, 0.0).as_millis())
                .expect("milliseconds fit u64");
            assert_eq!(actual, case.expected_ms);
        }
    }

    #[test]
    fn language_neutral_circuit_breaker_contract() {
        let fixture = fixture().circuit_breaker;
        let timeout_ms = 10;
        let circuit = CircuitBreaker::new(
            "contract",
            CircuitBreakerConfig {
                failure_threshold: fixture.failure_threshold,
                success_threshold: fixture.success_threshold,
                open_timeout_ms: timeout_ms,
                ..CircuitBreakerConfig::default()
            },
        )
        .expect("valid circuit");
        let started = Instant::now();
        for _ in 0..fixture.open_after_failures {
            circuit.record_failure_at(started);
        }
        assert_eq!(circuit.state(), CircuitState::Open);
        assert_eq!(
            circuit.allow_call_at(started).is_err(),
            fixture.reject_while_open
        );

        circuit
            .allow_call_at(started + Duration::from_millis(timeout_ms))
            .expect("half-open probe");
        assert_eq!(
            circuit.state() == CircuitState::HalfOpen,
            fixture.half_open_after_timeout
        );
        for offset in 0..fixture.close_after_half_open_successes {
            circuit
                .record_success_at(started + Duration::from_millis(timeout_ms + u64::from(offset)));
        }
        assert_eq!(circuit.state(), CircuitState::Closed);
    }

    #[tokio::test]
    async fn language_neutral_retry_contract() {
        let fixture = fixture().retry;
        let manager = ResilienceManager::new(
            "retry-contract",
            ResilienceConfig {
                retry: RetryConfig {
                    max_attempts: fixture.max_attempts,
                    base_delay_ms: 0,
                    max_delay_ms: 0,
                    jitter: false,
                    ..RetryConfig::default()
                },
                circuit_breaker_enabled: false,
                timeout_enabled: false,
                ..ResilienceConfig::default()
            },
        )
        .expect("valid manager");
        let calls = AtomicU32::new(0);
        let value = manager
            .execute(
                || {
                    let call = calls.fetch_add(1, Ordering::SeqCst) + 1;
                    async move {
                        if call <= fixture.failures_before_success {
                            Err("retryable")
                        } else {
                            Ok("ok")
                        }
                    }
                },
                |_| true,
            )
            .await
            .expect("eventual success");
        assert_eq!(value, "ok");
        assert_eq!(calls.load(Ordering::SeqCst), fixture.expected_attempts);

        let calls = AtomicU32::new(0);
        let result = manager
            .execute(
                || {
                    calls.fetch_add(1, Ordering::SeqCst);
                    async { Err::<(), _>("fatal") }
                },
                |_| false,
            )
            .await;
        assert!(matches!(
            result,
            Err(ExecutionError::RetryExhausted { attempts: 1, .. })
        ));
        assert_eq!(
            calls.load(Ordering::SeqCst),
            fixture.non_retryable_expected_attempts
        );
    }

    #[tokio::test]
    async fn language_neutral_bulkhead_contract() {
        let fixture = fixture().bulkhead;
        let bulkhead = Bulkhead::new(
            "contract",
            BulkheadConfig {
                max_concurrent: fixture.max_concurrent,
                reject_on_full: fixture.reject_on_full,
                execution_timeout_ms: 1_000,
                ..BulkheadConfig::default()
            },
        )
        .expect("valid bulkhead");
        let (release_tx, release_rx) = tokio::sync::oneshot::channel::<()>();
        let active = {
            let bulkhead = bulkhead.clone();
            tokio::spawn(async move {
                bulkhead
                    .execute(async move {
                        let _ = release_rx.await;
                        Ok::<_, ()>(())
                    })
                    .await
            })
        };
        tokio::task::yield_now().await;
        let rejected = bulkhead.execute(async { Ok::<_, ()>(()) }).await;
        assert!(matches!(
            rejected,
            Err(ExecutionError::Resilience(
                ResilienceError::BulkheadRejected { .. }
            ))
        ));
        release_tx.send(()).expect("release active operation");
        active
            .await
            .expect("task joined")
            .expect("active completed");
        assert_eq!(bulkhead.metrics().rejected, fixture.expected_rejections);
    }

    #[tokio::test]
    async fn language_neutral_fallback_order_contract() {
        let expected = fixture().fallback_order;
        let observed = Arc::new(Mutex::new(Vec::new()));
        let mut chain: FallbackChain<&'static str, &'static str> = FallbackChain::new("chain", 3);

        for name in &expected {
            let name_for_log = name.clone();
            let observed = observed.clone();
            let succeeds = name == "static";
            chain.push(Arc::new(FunctionFallback::new(name.clone(), move || {
                let observed = observed.clone();
                let name = name_for_log.clone();
                async move {
                    observed
                        .lock()
                        .unwrap_or_else(std::sync::PoisonError::into_inner)
                        .push(name);
                    if succeeds {
                        Ok("fallback")
                    } else {
                        Err("unavailable".to_owned())
                    }
                }
            })));
        }

        assert_eq!(
            chain.execute(&"primary").await.expect("fallback"),
            "fallback"
        );
        assert_eq!(
            *observed
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner),
            expected
        );
    }
}
