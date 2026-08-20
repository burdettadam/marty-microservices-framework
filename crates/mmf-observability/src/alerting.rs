#![allow(
    clippy::cast_possible_truncation,
    clippy::cast_precision_loss,
    clippy::cast_sign_loss
)]

use std::collections::{BTreeMap, BTreeSet, VecDeque};

use serde::{Deserialize, Serialize};

use crate::{AlertSeverity, ObservabilityError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MetricAggregation {
    Sum,
    Average,
    Min,
    Max,
    Count,
    P95,
    P99,
    Latest,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ThresholdOperator {
    GreaterThan,
    GreaterThanOrEqual,
    LessThan,
    LessThanOrEqual,
    Equals,
    NotEquals,
}

impl ThresholdOperator {
    #[must_use]
    pub fn evaluate(self, value: f64, threshold: f64) -> bool {
        const EPSILON: f64 = 0.000_1;
        match self {
            Self::GreaterThan => value > threshold,
            Self::GreaterThanOrEqual => value >= threshold,
            Self::LessThan => value < threshold,
            Self::LessThanOrEqual => value <= threshold,
            Self::Equals => (value - threshold).abs() < EPSILON,
            Self::NotEquals => (value - threshold).abs() >= EPSILON,
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
pub struct MetricPoint {
    pub timestamp_ms: u64,
    pub value: f64,
}

#[derive(Clone, Debug)]
pub struct MetricWindow {
    window_ms: u64,
    max_points: usize,
    points: VecDeque<MetricPoint>,
}

impl MetricWindow {
    pub fn new(window_ms: u64, max_points: usize) -> Result<Self, ObservabilityError> {
        if window_ms == 0 || max_points == 0 {
            return Err(ObservabilityError::InvalidMetricDefinition(
                "metric window requires positive limits".into(),
            ));
        }
        Ok(Self {
            window_ms,
            max_points,
            points: VecDeque::with_capacity(max_points),
        })
    }

    pub fn add(&mut self, point: MetricPoint, now_ms: u64) -> Result<(), ObservabilityError> {
        if !point.value.is_finite() || point.timestamp_ms > now_ms {
            return Err(ObservabilityError::InvalidMetricValue(
                "metric window point".into(),
            ));
        }
        while self.points.len() >= self.max_points {
            self.points.pop_front();
        }
        self.points.push_back(point);
        self.expire(now_ms);
        Ok(())
    }

    #[must_use]
    pub fn aggregate(&mut self, aggregation: MetricAggregation, now_ms: u64) -> Option<f64> {
        self.expire(now_ms);
        let mut values = self
            .points
            .iter()
            .map(|point| point.value)
            .collect::<Vec<_>>();
        if values.is_empty() {
            return None;
        }
        match aggregation {
            MetricAggregation::Sum => Some(values.iter().sum()),
            MetricAggregation::Average => Some(values.iter().sum::<f64>() / values.len() as f64),
            MetricAggregation::Min => values.into_iter().reduce(f64::min),
            MetricAggregation::Max => values.into_iter().reduce(f64::max),
            MetricAggregation::Count => Some(values.len() as f64),
            MetricAggregation::P95 => Some(percentile_or_max(&mut values, 0.95, 20)),
            MetricAggregation::P99 => Some(percentile_or_max(&mut values, 0.99, 100)),
            MetricAggregation::Latest => self.points.back().map(|point| point.value),
        }
    }

    fn expire(&mut self, now_ms: u64) {
        let cutoff = now_ms.saturating_sub(self.window_ms);
        while self
            .points
            .front()
            .is_some_and(|point| point.timestamp_ms < cutoff)
        {
            self.points.pop_front();
        }
    }
}

fn percentile_or_max(values: &mut [f64], percentile: f64, minimum: usize) -> f64 {
    values.sort_by(f64::total_cmp);
    if values.len() < minimum {
        return values[values.len() - 1];
    }
    let rank = percentile * (values.len() as f64 + 1.0);
    let lower = rank.floor().max(1.0) as usize - 1;
    let upper = rank.ceil().min(values.len() as f64) as usize - 1;
    if lower == upper {
        values[lower]
    } else {
        values[lower] + (rank.fract() * (values[upper] - values[lower]))
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MonitoringAlertRule {
    pub name: String,
    pub metric_name: String,
    pub operator: ThresholdOperator,
    pub threshold: f64,
    pub severity: AlertSeverity,
    pub description: String,
    pub aggregation: MetricAggregation,
    pub window_ms: u64,
    #[serde(default)]
    pub for_ms: u64,
    #[serde(default)]
    pub cooldown_ms: u64,
    #[serde(default)]
    pub dependencies: BTreeSet<String>,
    #[serde(default = "enabled")]
    pub enabled: bool,
}

const fn enabled() -> bool {
    true
}

impl MonitoringAlertRule {
    pub fn validate(&self) -> Result<(), ObservabilityError> {
        if self.name.trim().is_empty()
            || self.metric_name.trim().is_empty()
            || self.description.trim().is_empty()
            || !self.threshold.is_finite()
            || self.window_ms == 0
            || self.dependencies.contains(&self.name)
        {
            return Err(ObservabilityError::InvalidAlertRule(self.name.clone()));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct MonitoringAlert {
    pub rule_name: String,
    pub severity: AlertSeverity,
    pub message: String,
    pub metric_value: f64,
    pub threshold: f64,
    pub triggered_at_ms: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub resolved_at_ms: Option<u64>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum AlertTransition {
    Triggered(MonitoringAlert),
    Resolved(MonitoringAlert),
    NoChange,
    Suppressed,
}

#[derive(Default)]
pub struct AlertEngine {
    rules: BTreeMap<String, MonitoringAlertRule>,
    pending_since: BTreeMap<String, u64>,
    active: BTreeMap<String, MonitoringAlert>,
    cooldown_until: BTreeMap<String, u64>,
    history: Vec<MonitoringAlert>,
}

impl AlertEngine {
    pub fn add_rule(&mut self, rule: MonitoringAlertRule) -> Result<(), ObservabilityError> {
        rule.validate()?;
        self.rules.insert(rule.name.clone(), rule);
        Ok(())
    }

    pub fn evaluate(
        &mut self,
        rule_name: &str,
        metric_value: f64,
        now_ms: u64,
    ) -> Result<AlertTransition, ObservabilityError> {
        if !metric_value.is_finite() {
            return Err(ObservabilityError::InvalidMetricValue(rule_name.into()));
        }
        let rule = self
            .rules
            .get(rule_name)
            .ok_or_else(|| ObservabilityError::InvalidAlertRule(rule_name.into()))?
            .clone();
        if !rule.enabled {
            return Ok(AlertTransition::NoChange);
        }
        let condition_met = rule.operator.evaluate(metric_value, rule.threshold);
        if !condition_met {
            self.pending_since.remove(rule_name);
            if let Some(mut alert) = self.active.remove(rule_name) {
                alert.resolved_at_ms = Some(now_ms);
                self.cooldown_until
                    .insert(rule_name.into(), now_ms.saturating_add(rule.cooldown_ms));
                self.history.push(alert.clone());
                return Ok(AlertTransition::Resolved(alert));
            }
            return Ok(AlertTransition::NoChange);
        }
        if self.active.contains_key(rule_name) {
            return Ok(AlertTransition::NoChange);
        }
        if self
            .cooldown_until
            .get(rule_name)
            .is_some_and(|until| *until > now_ms)
            || rule
                .dependencies
                .iter()
                .any(|dependency| self.active.contains_key(dependency))
        {
            return Ok(AlertTransition::Suppressed);
        }
        let since = *self.pending_since.entry(rule_name.into()).or_insert(now_ms);
        if now_ms.saturating_sub(since) < rule.for_ms {
            return Ok(AlertTransition::NoChange);
        }
        self.pending_since.remove(rule_name);
        let alert = MonitoringAlert {
            rule_name: rule.name.clone(),
            severity: rule.severity,
            message: format!("{}: {metric_value}", rule.description),
            metric_value,
            threshold: rule.threshold,
            triggered_at_ms: now_ms,
            resolved_at_ms: None,
        };
        self.active.insert(rule.name, alert.clone());
        Ok(AlertTransition::Triggered(alert))
    }

    #[must_use]
    pub fn active_alerts(&self) -> Vec<MonitoringAlert> {
        self.active.values().cloned().collect()
    }

    #[must_use]
    pub fn history_since(&self, timestamp_ms: u64) -> Vec<MonitoringAlert> {
        self.history
            .iter()
            .filter(|alert| alert.triggered_at_ms >= timestamp_ms)
            .cloned()
            .collect()
    }
}

#[derive(Clone, Debug)]
pub struct AnomalyDetector {
    minimum_points: usize,
    max_points: usize,
    baselines: BTreeMap<String, VecDeque<f64>>,
}

impl AnomalyDetector {
    #[must_use]
    pub fn new(minimum_points: usize, max_points: usize) -> Self {
        Self {
            minimum_points,
            max_points: max_points.max(minimum_points),
            baselines: BTreeMap::new(),
        }
    }

    pub fn observe(
        &mut self,
        metric: impl Into<String>,
        value: f64,
    ) -> Result<(), ObservabilityError> {
        if !value.is_finite() {
            return Err(ObservabilityError::InvalidMetricValue(
                "anomaly baseline".into(),
            ));
        }
        let baseline = self.baselines.entry(metric.into()).or_default();
        while baseline.len() >= self.max_points {
            baseline.pop_front();
        }
        baseline.push_back(value);
        Ok(())
    }

    pub fn score(&self, metric: &str, value: f64) -> Result<Option<f64>, ObservabilityError> {
        if !value.is_finite() {
            return Err(ObservabilityError::InvalidMetricValue(metric.into()));
        }
        let Some(baseline) = self.baselines.get(metric) else {
            return Ok(None);
        };
        if baseline.len() < self.minimum_points {
            return Ok(None);
        }
        let values = baseline.iter().copied().collect::<Vec<_>>();
        let mean = values.iter().sum::<f64>() / values.len() as f64;
        let variance = values.iter().map(|item| (item - mean).powi(2)).sum::<f64>()
            / (values.len() - 1) as f64;
        let standard_deviation = variance.sqrt();
        if standard_deviation == 0.0 {
            return Ok(Some(0.0));
        }
        Ok(Some((value - mean).abs() / standard_deviation))
    }

    pub fn is_anomaly(
        &self,
        metric: &str,
        value: f64,
        sensitivity: f64,
    ) -> Result<bool, ObservabilityError> {
        if !sensitivity.is_finite() || !(0.0..=1.0).contains(&sensitivity) {
            return Err(ObservabilityError::InvalidAnalyticsInput(
                "anomaly sensitivity must be between zero and one".into(),
            ));
        }
        Ok(self
            .score(metric, value)?
            .is_some_and(|score| score > 3.0 * (1.0 - sensitivity)))
    }
}
