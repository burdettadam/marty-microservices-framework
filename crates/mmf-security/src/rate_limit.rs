use std::collections::{BTreeMap, VecDeque};
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};

use crate::{DistributedRateLimiter, SecurityError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RateLimitStrategy {
    TokenBucket,
    SlidingWindow,
    FixedWindow,
    LeakyBucket,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RateLimitScope {
    Global,
    PerUser,
    PerIp,
    PerEndpoint,
    PerService,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RateLimitRule {
    pub name: String,
    pub scope: RateLimitScope,
    pub strategy: RateLimitStrategy,
    pub limit: u64,
    pub window_ms: u64,
    #[serde(default)]
    pub burst_size: u64,
    #[serde(default = "enabled")]
    pub enabled: bool,
}

const fn enabled() -> bool {
    true
}

impl RateLimitRule {
    pub fn validate(&self) -> Result<(), SecurityError> {
        if self.name.trim().is_empty() || self.limit == 0 || self.window_ms == 0 {
            return Err(SecurityError::InvalidRateLimitRule(self.name.clone()));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct RateLimitQuota {
    pub user_id: Option<String>,
    pub ip_address: Option<String>,
    pub endpoint: Option<String>,
    pub service: Option<String>,
    pub custom_key: Option<String>,
}

impl RateLimitQuota {
    #[must_use]
    pub fn cache_key(&self, rule: &RateLimitRule) -> String {
        let scope = match rule.scope {
            RateLimitScope::PerUser => self.user_id.as_ref().map(|value| format!("user:{value}")),
            RateLimitScope::PerIp => self.ip_address.as_ref().map(|value| format!("ip:{value}")),
            RateLimitScope::PerEndpoint => self
                .endpoint
                .as_ref()
                .map(|value| format!("endpoint:{value}")),
            RateLimitScope::PerService => self
                .service
                .as_ref()
                .map(|value| format!("service:{value}")),
            RateLimitScope::Global => Some("global".to_owned()),
        }
        .or_else(|| self.custom_key.clone())
        .unwrap_or_else(|| "unknown".to_owned());
        format!("rate_limit:{}:{scope}", rule.name)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RateLimitResult {
    pub allowed: bool,
    pub rule_name: String,
    pub current_count: u64,
    pub limit: u64,
    pub remaining: u64,
    pub reset_at_ms: u64,
    pub retry_after_ms: u64,
}

#[derive(Clone, Debug)]
enum WindowState {
    Fixed { started_at_ms: u64, count: u64 },
    Sliding { requests: VecDeque<u64> },
    Token { tokens: f64, updated_at_ms: u64 },
    Leaky { level: f64, updated_at_ms: u64 },
}

#[derive(Clone, Debug, Default)]
pub struct InMemoryRateLimiter {
    windows: Arc<Mutex<BTreeMap<String, WindowState>>>,
}

impl InMemoryRateLimiter {
    pub fn check(
        &self,
        rule: &RateLimitRule,
        quota: &RateLimitQuota,
        now_ms: u64,
    ) -> Result<RateLimitResult, SecurityError> {
        rule.validate()?;
        if !rule.enabled {
            return Ok(result(rule, true, 0, rule.limit, now_ms, 0));
        }
        let key = quota.cache_key(rule);
        let mut windows = self
            .windows
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let state = windows
            .entry(key)
            .or_insert_with(|| initial_state(rule, now_ms));
        Ok(match state {
            WindowState::Fixed {
                started_at_ms,
                count,
            } => check_fixed(rule, now_ms, started_at_ms, count),
            WindowState::Sliding { requests } => check_sliding(rule, now_ms, requests),
            WindowState::Token {
                tokens,
                updated_at_ms,
            } => check_token(rule, now_ms, tokens, updated_at_ms),
            WindowState::Leaky {
                level,
                updated_at_ms,
            } => check_leaky(rule, now_ms, level, updated_at_ms),
        })
    }
}

#[async_trait]
impl DistributedRateLimiter for InMemoryRateLimiter {
    async fn check(
        &self,
        rule: &RateLimitRule,
        quota: &RateLimitQuota,
        now_ms: u64,
    ) -> Result<RateLimitResult, SecurityError> {
        InMemoryRateLimiter::check(self, rule, quota, now_ms)
    }
}

#[allow(clippy::cast_precision_loss)]
fn initial_state(rule: &RateLimitRule, now_ms: u64) -> WindowState {
    match rule.strategy {
        RateLimitStrategy::FixedWindow => WindowState::Fixed {
            started_at_ms: now_ms,
            count: 0,
        },
        RateLimitStrategy::SlidingWindow => WindowState::Sliding {
            requests: VecDeque::new(),
        },
        RateLimitStrategy::TokenBucket => WindowState::Token {
            tokens: (rule.limit + rule.burst_size) as f64,
            updated_at_ms: now_ms,
        },
        RateLimitStrategy::LeakyBucket => WindowState::Leaky {
            level: 0.0,
            updated_at_ms: now_ms,
        },
    }
}

fn check_fixed(
    rule: &RateLimitRule,
    now_ms: u64,
    started_at_ms: &mut u64,
    count: &mut u64,
) -> RateLimitResult {
    if now_ms.saturating_sub(*started_at_ms) >= rule.window_ms {
        *started_at_ms = now_ms;
        *count = 0;
    }
    let capacity = rule.limit.saturating_add(rule.burst_size);
    let allowed = *count < capacity;
    if allowed {
        *count = count.saturating_add(1);
    }
    let reset = started_at_ms.saturating_add(rule.window_ms);
    result(
        rule,
        allowed,
        *count,
        capacity.saturating_sub(*count),
        reset,
        if allowed {
            0
        } else {
            reset.saturating_sub(now_ms)
        },
    )
}

fn check_sliding(
    rule: &RateLimitRule,
    now_ms: u64,
    requests: &mut VecDeque<u64>,
) -> RateLimitResult {
    while requests
        .front()
        .is_some_and(|time| now_ms.saturating_sub(*time) >= rule.window_ms)
    {
        requests.pop_front();
    }
    let capacity = rule.limit.saturating_add(rule.burst_size);
    let allowed = u64::try_from(requests.len()).unwrap_or(u64::MAX) < capacity;
    if allowed {
        requests.push_back(now_ms);
    }
    let count = u64::try_from(requests.len()).unwrap_or(u64::MAX);
    let reset = requests
        .front()
        .copied()
        .unwrap_or(now_ms)
        .saturating_add(rule.window_ms);
    result(
        rule,
        allowed,
        count,
        capacity.saturating_sub(count),
        reset,
        if allowed {
            0
        } else {
            reset.saturating_sub(now_ms)
        },
    )
}

#[allow(clippy::cast_precision_loss)]
fn check_token(
    rule: &RateLimitRule,
    now_ms: u64,
    tokens: &mut f64,
    updated_at_ms: &mut u64,
) -> RateLimitResult {
    let capacity_units = rule.limit.saturating_add(rule.burst_size);
    let capacity = capacity_units as f64;
    let elapsed = now_ms.saturating_sub(*updated_at_ms) as f64;
    *tokens = (*tokens + elapsed * rule.limit as f64 / rule.window_ms as f64).min(capacity);
    *updated_at_ms = now_ms;
    let allowed = *tokens >= 1.0;
    if allowed {
        *tokens -= 1.0;
    }
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    let remaining = tokens.floor().max(0.0) as u64;
    let retry_after = if allowed {
        0
    } else {
        rule.window_ms.div_ceil(rule.limit)
    };
    result(
        rule,
        allowed,
        capacity_units.saturating_sub(remaining),
        remaining,
        now_ms.saturating_add(retry_after),
        retry_after,
    )
}

#[allow(clippy::cast_precision_loss)]
fn check_leaky(
    rule: &RateLimitRule,
    now_ms: u64,
    level: &mut f64,
    updated_at_ms: &mut u64,
) -> RateLimitResult {
    let capacity_units = rule.limit.saturating_add(rule.burst_size);
    let capacity = capacity_units as f64;
    let elapsed = now_ms.saturating_sub(*updated_at_ms) as f64;
    *level = (*level - elapsed * rule.limit as f64 / rule.window_ms as f64).max(0.0);
    *updated_at_ms = now_ms;
    let allowed = *level + 1.0 <= capacity;
    if allowed {
        *level += 1.0;
    }
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    let current = level.ceil() as u64;
    let retry_after = if allowed {
        0
    } else {
        rule.window_ms.div_ceil(rule.limit)
    };
    result(
        rule,
        allowed,
        current,
        capacity_units.saturating_sub(current),
        now_ms.saturating_add(retry_after),
        retry_after,
    )
}

fn result(
    rule: &RateLimitRule,
    allowed: bool,
    current_count: u64,
    remaining: u64,
    reset_at_ms: u64,
    retry_after_ms: u64,
) -> RateLimitResult {
    RateLimitResult {
        allowed,
        rule_name: rule.name.clone(),
        current_count,
        limit: rule.limit,
        remaining,
        reset_at_ms,
        retry_after_ms,
    }
}
