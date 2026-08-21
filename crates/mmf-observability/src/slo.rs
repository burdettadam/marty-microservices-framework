use serde::{Deserialize, Serialize};

use crate::ObservabilityError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SliType {
    Availability,
    Latency,
    ErrorRate,
    Throughput,
    Correctness,
    Freshness,
    Coverage,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SloPriority {
    Critical,
    High,
    Medium,
    Low,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SliSpecification {
    pub name: String,
    pub sli_type: SliType,
    pub description: String,
    pub query: String,
    #[serde(default)]
    pub unit: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub good_threshold: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub target_threshold: Option<f64>,
    pub window_seconds: u64,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SloTarget {
    /// Percentage in the inclusive range `0.0..=100.0`.
    pub target_percentage: f64,
    pub window_seconds: u64,
    pub priority: SloPriority,
}

impl SloTarget {
    pub fn validate(&self) -> Result<(), ObservabilityError> {
        if !self.target_percentage.is_finite()
            || !(0.0..=100.0).contains(&self.target_percentage)
            || self.window_seconds == 0
        {
            return Err(ObservabilityError::InvalidSloTarget);
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SloDefinition {
    pub name: String,
    pub service_name: String,
    pub sli: SliSpecification,
    pub target: SloTarget,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub tags: std::collections::BTreeMap<String, String>,
    #[serde(default = "enabled")]
    pub enabled: bool,
}

const fn enabled() -> bool {
    true
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
pub struct SliMeasurement {
    pub value: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub good_events: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub total_events: Option<u64>,
}

impl SliMeasurement {
    pub fn compliance_percentage(self) -> Result<f64, ObservabilityError> {
        if let (Some(good), Some(total)) = (self.good_events, self.total_events) {
            if good > total || total == 0 {
                return Err(ObservabilityError::InvalidSliMeasurement);
            }
            #[allow(clippy::cast_precision_loss)]
            return Ok((good as f64 / total as f64) * 100.0);
        }
        if self.value.is_finite() && (0.0..=100.0).contains(&self.value) {
            Ok(self.value)
        } else {
            Err(ObservabilityError::InvalidSliMeasurement)
        }
    }
}

/// Error-budget state using the percentage semantics exposed by Python MMF.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
pub struct ErrorBudget {
    pub target_percentage: f64,
    pub total_budget: f64,
    pub budget_consumed: f64,
    pub budget_remaining: f64,
    pub burn_rate_per_hour: f64,
}

impl ErrorBudget {
    pub fn new(target_percentage: f64) -> Result<Self, ObservabilityError> {
        SloTarget {
            target_percentage,
            window_seconds: 1,
            priority: SloPriority::Medium,
        }
        .validate()?;
        let total_budget = 100.0 - target_percentage;
        Ok(Self {
            target_percentage,
            total_budget,
            budget_consumed: 0.0,
            budget_remaining: total_budget,
            burn_rate_per_hour: 0.0,
        })
    }

    pub fn update(
        &mut self,
        compliance_percentage: f64,
        elapsed_seconds: f64,
    ) -> Result<(), ObservabilityError> {
        if !compliance_percentage.is_finite()
            || !(0.0..=100.0).contains(&compliance_percentage)
            || !elapsed_seconds.is_finite()
            || elapsed_seconds < 0.0
        {
            return Err(ObservabilityError::InvalidSliMeasurement);
        }
        let shortfall = (self.target_percentage - compliance_percentage).max(0.0);
        self.budget_consumed = (self.budget_consumed + shortfall).min(self.total_budget);
        self.budget_remaining = (self.total_budget - self.budget_consumed).max(0.0);
        self.burn_rate_per_hour = if elapsed_seconds > 0.0 {
            shortfall / (elapsed_seconds / 3_600.0)
        } else {
            0.0
        };
        Ok(())
    }

    pub fn from_compliance(
        target_percentage: f64,
        compliance_percentage: f64,
    ) -> Result<Self, ObservabilityError> {
        let mut budget = Self::new(target_percentage)?;
        budget.update(compliance_percentage, 0.0)?;
        Ok(budget)
    }

    #[must_use]
    pub fn consumption_percentage(self) -> f64 {
        if self.total_budget == 0.0 {
            if self.budget_consumed == 0.0 {
                0.0
            } else {
                100.0
            }
        } else {
            (self.budget_consumed / self.total_budget) * 100.0
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AlertSeverity {
    Info,
    Warning,
    Critical,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum SloAlertCondition {
    BurnRate { threshold_per_hour: f64 },
    BudgetConsumption { threshold_percentage: f64 },
    TargetBreach,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SloAlertRule {
    pub name: String,
    pub slo_name: String,
    pub condition: SloAlertCondition,
    pub window_seconds: u64,
    pub severity: AlertSeverity,
    #[serde(default = "enabled")]
    pub enabled: bool,
}

impl SloAlertRule {
    #[must_use]
    pub fn triggered(&self, budget: ErrorBudget, compliance_percentage: f64) -> bool {
        if !self.enabled {
            return false;
        }
        match self.condition {
            SloAlertCondition::BurnRate { threshold_per_hour } => {
                budget.burn_rate_per_hour >= threshold_per_hour
            }
            SloAlertCondition::BudgetConsumption {
                threshold_percentage,
            } => budget.consumption_percentage() >= threshold_percentage,
            SloAlertCondition::TargetBreach => compliance_percentage < budget.target_percentage,
        }
    }
}
