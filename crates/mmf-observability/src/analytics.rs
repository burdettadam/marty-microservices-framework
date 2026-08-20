#![allow(
    clippy::cast_possible_truncation,
    clippy::cast_precision_loss,
    clippy::cast_sign_loss
)]

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::{MetricPoint, ObservabilityError};

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TrendDirection {
    Increasing,
    Decreasing,
    Stable,
    Volatile,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
pub struct DescriptiveStatistics {
    pub mean: f64,
    pub median: f64,
    pub standard_deviation: f64,
    pub minimum: f64,
    pub maximum: f64,
    pub p95: f64,
    pub p99: f64,
    pub coefficient_of_variation: f64,
}

impl DescriptiveStatistics {
    pub fn calculate(values: &[f64]) -> Result<Self, ObservabilityError> {
        if values.is_empty() || values.iter().any(|value| !value.is_finite()) {
            return Err(ObservabilityError::InvalidAnalyticsInput(
                "statistics require finite values".into(),
            ));
        }
        let mut sorted = values.to_vec();
        sorted.sort_by(f64::total_cmp);
        let mean = sorted.iter().sum::<f64>() / sorted.len() as f64;
        let median = if sorted.len().is_multiple_of(2) {
            f64::midpoint(sorted[sorted.len() / 2 - 1], sorted[sorted.len() / 2])
        } else {
            sorted[sorted.len() / 2]
        };
        let standard_deviation = sample_standard_deviation(&sorted, mean);
        Ok(Self {
            mean,
            median,
            standard_deviation,
            minimum: sorted[0],
            maximum: sorted[sorted.len() - 1],
            p95: nearest_percentile(&sorted, 0.95),
            p99: nearest_percentile(&sorted, 0.99),
            coefficient_of_variation: if mean > 0.0 {
                standard_deviation / mean
            } else {
                0.0
            },
        })
    }
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
pub struct TrendAnalysis {
    pub direction: TrendDirection,
    pub slope_per_second: f64,
    pub r_squared: f64,
    pub confidence: f64,
}

impl TrendAnalysis {
    pub fn calculate(points: &[MetricPoint]) -> Result<Self, ObservabilityError> {
        if points.len() < 2
            || points.iter().any(|point| !point.value.is_finite())
            || points
                .windows(2)
                .any(|pair| pair[0].timestamp_ms >= pair[1].timestamp_ms)
        {
            return Err(ObservabilityError::InvalidAnalyticsInput(
                "trend requires ordered finite points".into(),
            ));
        }
        let origin = points[0].timestamp_ms;
        let x = points
            .iter()
            .map(|point| point.timestamp_ms.saturating_sub(origin) as f64 / 1_000.0)
            .collect::<Vec<_>>();
        let y = points.iter().map(|point| point.value).collect::<Vec<_>>();
        let (slope, _, r_squared) = linear_regression(&x, &y)?;
        let statistics = DescriptiveStatistics::calculate(&y)?;
        let volatile = points.len() > 5 && statistics.coefficient_of_variation > 0.5;
        let scale = statistics.mean.abs().max(1.0);
        let stable_threshold = f64::EPSILON * scale;
        let direction = if volatile {
            TrendDirection::Volatile
        } else if slope.abs() <= stable_threshold {
            TrendDirection::Stable
        } else if slope > 0.0 {
            TrendDirection::Increasing
        } else {
            TrendDirection::Decreasing
        };
        Ok(Self {
            direction,
            slope_per_second: slope,
            r_squared,
            confidence: if volatile {
                r_squared.sqrt().min(0.5)
            } else {
                r_squared.sqrt()
            },
        })
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CapacityPrediction {
    pub metric_name: String,
    pub current_usage: f64,
    pub predicted_usage: f64,
    pub time_to_threshold_seconds: Option<f64>,
    pub confidence_interval: (f64, f64),
    pub recommended_action: String,
    pub prediction_horizon_seconds: u64,
    pub model_accuracy: f64,
}

#[derive(Clone, Debug)]
pub struct CapacityPlanner {
    thresholds: BTreeMap<String, f64>,
    minimum_points: usize,
}

impl Default for CapacityPlanner {
    fn default() -> Self {
        Self {
            thresholds: BTreeMap::from([
                ("cpu_usage".into(), 0.8),
                ("memory_usage".into(), 0.9),
                ("disk_usage".into(), 0.85),
                ("network_usage".into(), 0.8),
            ]),
            minimum_points: 10,
        }
    }
}

impl CapacityPlanner {
    pub fn set_threshold(
        &mut self,
        metric_name: impl Into<String>,
        threshold: f64,
    ) -> Result<(), ObservabilityError> {
        if !threshold.is_finite() || threshold <= 0.0 {
            return Err(ObservabilityError::InvalidAnalyticsInput(
                "capacity threshold must be positive".into(),
            ));
        }
        self.thresholds.insert(metric_name.into(), threshold);
        Ok(())
    }

    pub fn predict(
        &self,
        metric_name: &str,
        points: &[MetricPoint],
        horizon_seconds: u64,
    ) -> Result<CapacityPrediction, ObservabilityError> {
        if points.len() < self.minimum_points || horizon_seconds == 0 {
            return Ok(default_prediction(metric_name, horizon_seconds));
        }
        if points.iter().any(|point| !point.value.is_finite())
            || points
                .windows(2)
                .any(|pair| pair[0].timestamp_ms >= pair[1].timestamp_ms)
        {
            return Err(ObservabilityError::InvalidAnalyticsInput(
                "capacity input requires ordered finite points".into(),
            ));
        }
        let origin = points[0].timestamp_ms;
        let x = points
            .iter()
            .map(|point| point.timestamp_ms.saturating_sub(origin) as f64 / 1_000.0)
            .collect::<Vec<_>>();
        let y = points.iter().map(|point| point.value).collect::<Vec<_>>();
        let (slope, intercept, r_squared) = linear_regression(&x, &y)?;
        let target_x = x[x.len() - 1] + horizon_seconds as f64;
        let predicted = slope.mul_add(target_x, intercept).max(0.0);
        let current = y[y.len() - 1];
        let threshold = self.thresholds.get(metric_name).copied().unwrap_or(1.0);
        let time_to_threshold_seconds = if current >= threshold {
            Some(0.0)
        } else if slope > 0.0 {
            Some(((threshold - intercept) / slope - x[x.len() - 1]).max(0.0))
        } else {
            None
        };
        let margin = predicted * (1.0 - r_squared) * 0.5;
        let usage_percentage = predicted / threshold * 100.0;
        let recommended_action = if usage_percentage > 100.0 {
            format!("Immediate action required: {metric_name} will exceed capacity")
        } else if usage_percentage > 80.0 {
            format!("Plan capacity expansion: {metric_name} approaching limits")
        } else if usage_percentage > 60.0 {
            format!("Monitor closely: {metric_name} showing growth trend")
        } else {
            format!("Capacity adequate: {metric_name} within normal ranges")
        };
        Ok(CapacityPrediction {
            metric_name: metric_name.into(),
            current_usage: current,
            predicted_usage: predicted,
            time_to_threshold_seconds,
            confidence_interval: ((predicted - margin).max(0.0), predicted + margin),
            recommended_action,
            prediction_horizon_seconds: horizon_seconds,
            model_accuracy: r_squared.sqrt(),
        })
    }
}

pub fn pearson_correlation(left: &[f64], right: &[f64]) -> Result<f64, ObservabilityError> {
    if left.len() != right.len()
        || left.len() < 2
        || left.iter().chain(right).any(|value| !value.is_finite())
    {
        return Err(ObservabilityError::InvalidAnalyticsInput(
            "correlation requires equal finite series".into(),
        ));
    }
    let left_mean = left.iter().sum::<f64>() / left.len() as f64;
    let right_mean = right.iter().sum::<f64>() / right.len() as f64;
    let covariance = left
        .iter()
        .zip(right)
        .map(|(a, b)| (a - left_mean) * (b - right_mean))
        .sum::<f64>();
    let left_variance = left
        .iter()
        .map(|value| (value - left_mean).powi(2))
        .sum::<f64>();
    let right_variance = right
        .iter()
        .map(|value| (value - right_mean).powi(2))
        .sum::<f64>();
    let denominator = (left_variance * right_variance).sqrt();
    if denominator == 0.0 {
        return Err(ObservabilityError::InvalidAnalyticsInput(
            "correlation is undefined for a constant series".into(),
        ));
    }
    Ok(covariance / denominator)
}

fn linear_regression(x: &[f64], y: &[f64]) -> Result<(f64, f64, f64), ObservabilityError> {
    let x_mean = x.iter().sum::<f64>() / x.len() as f64;
    let y_mean = y.iter().sum::<f64>() / y.len() as f64;
    let covariance = x
        .iter()
        .zip(y)
        .map(|(left, right)| (left - x_mean) * (right - y_mean))
        .sum::<f64>();
    let x_variance = x.iter().map(|value| (value - x_mean).powi(2)).sum::<f64>();
    if x_variance == 0.0 {
        return Err(ObservabilityError::InvalidAnalyticsInput(
            "analytics timestamps must span time".into(),
        ));
    }
    let slope = covariance / x_variance;
    let intercept = slope.mul_add(-x_mean, y_mean);
    let total = y.iter().map(|value| (value - y_mean).powi(2)).sum::<f64>();
    let residual = x
        .iter()
        .zip(y)
        .map(|(x_value, y_value)| (y_value - slope.mul_add(*x_value, intercept)).powi(2))
        .sum::<f64>();
    let r_squared = if total == 0.0 {
        1.0
    } else {
        (1.0 - residual / total).clamp(0.0, 1.0)
    };
    Ok((slope, intercept, r_squared))
}

fn sample_standard_deviation(values: &[f64], mean: f64) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    (values
        .iter()
        .map(|value| (value - mean).powi(2))
        .sum::<f64>()
        / (values.len() - 1) as f64)
        .sqrt()
}

fn nearest_percentile(sorted: &[f64], percentile: f64) -> f64 {
    let index = (sorted.len() as f64 * percentile) as usize;
    sorted[index.min(sorted.len() - 1)]
}

fn default_prediction(metric_name: &str, horizon_seconds: u64) -> CapacityPrediction {
    CapacityPrediction {
        metric_name: metric_name.into(),
        current_usage: 0.0,
        predicted_usage: 0.0,
        time_to_threshold_seconds: Some(31_536_000.0),
        confidence_interval: (0.0, 0.0),
        recommended_action: "Insufficient data for prediction".into(),
        prediction_horizon_seconds: horizon_seconds,
        model_accuracy: 0.0,
    }
}
