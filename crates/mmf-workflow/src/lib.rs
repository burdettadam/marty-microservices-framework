//! Canonical durable workflow and saga state machines for MMF.

#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Mutex;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkflowStatus {
    Created,
    Running,
    Paused,
    Completed,
    Failed,
    Cancelled,
    Compensating,
    Compensated,
    CompensationFailed,
    TimedOut,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StepStatus {
    Pending,
    Running,
    WaitingRetry,
    Completed,
    Failed,
    Skipped,
    Compensating,
    Compensated,
    CompensationFailed,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StepType {
    Action,
    Decision,
    Parallel,
    Loop,
    Wait,
    Compensation,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(default)]
pub struct WorkflowRetryPolicy {
    pub max_attempts: u32,
    pub initial_delay_ms: u64,
    pub maximum_delay_ms: u64,
    pub exponential_base: u32,
}

impl Default for WorkflowRetryPolicy {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            initial_delay_ms: 1_000,
            maximum_delay_ms: 60_000,
            exponential_base: 2,
        }
    }
}

impl WorkflowRetryPolicy {
    pub fn validate(&self) -> Result<(), WorkflowError> {
        if self.max_attempts == 0 || self.exponential_base == 0 {
            return Err(WorkflowError::InvalidDefinition(
                "retry attempts and exponential base must be positive".to_owned(),
            ));
        }
        Ok(())
    }

    #[must_use]
    pub fn delay_ms(&self, completed_attempts: u32) -> u64 {
        let exponent = completed_attempts.saturating_sub(1).min(31);
        self.initial_delay_ms
            .saturating_mul(u64::from(self.exponential_base).saturating_pow(exponent))
            .min(self.maximum_delay_ms)
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct StepDefinition {
    pub id: String,
    pub step_type: StepType,
    #[serde(default)]
    pub dependencies: BTreeSet<String>,
    #[serde(default)]
    pub retry: WorkflowRetryPolicy,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timeout_ms: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub compensation: Option<String>,
    #[serde(default)]
    pub configuration: Value,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct WorkflowDefinition {
    pub id: String,
    pub version: u32,
    pub steps: Vec<StepDefinition>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timeout_ms: Option<u64>,
}

impl WorkflowDefinition {
    pub fn validate(&self) -> Result<(), WorkflowError> {
        if self.id.trim().is_empty() || self.version == 0 || self.steps.is_empty() {
            return Err(WorkflowError::InvalidDefinition(
                "workflow requires an ID, version, and steps".to_owned(),
            ));
        }
        let ids = self
            .steps
            .iter()
            .map(|step| step.id.as_str())
            .collect::<BTreeSet<_>>();
        if ids.len() != self.steps.len() || ids.contains("") {
            return Err(WorkflowError::InvalidDefinition(
                "step IDs must be non-empty and unique".to_owned(),
            ));
        }
        for step in &self.steps {
            step.retry.validate()?;
            if step.dependencies.contains(&step.id)
                || step
                    .dependencies
                    .iter()
                    .any(|dependency| !ids.contains(dependency.as_str()))
            {
                return Err(WorkflowError::InvalidDefinition(format!(
                    "step '{}' has an invalid dependency",
                    step.id
                )));
            }
        }
        for step in &self.steps {
            if self.has_dependency_cycle(&step.id, &mut BTreeSet::new(), &mut BTreeSet::new()) {
                return Err(WorkflowError::InvalidDefinition(format!(
                    "dependency cycle at '{}'",
                    step.id
                )));
            }
        }
        Ok(())
    }

    fn has_dependency_cycle(
        &self,
        id: &str,
        path: &mut BTreeSet<String>,
        complete: &mut BTreeSet<String>,
    ) -> bool {
        if complete.contains(id) {
            return false;
        }
        if !path.insert(id.to_owned()) {
            return true;
        }
        let cyclic = self
            .steps
            .iter()
            .find(|step| step.id == id)
            .is_some_and(|step| {
                step.dependencies
                    .iter()
                    .any(|dependency| self.has_dependency_cycle(dependency, path, complete))
            });
        path.remove(id);
        complete.insert(id.to_owned());
        cyclic
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct StepResult {
    pub success: bool,
    #[serde(default)]
    pub data: Value,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(default)]
    pub should_retry: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub retry_delay_ms: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct StepExecution {
    pub status: StepStatus,
    pub attempts: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub started_at_ms: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub completed_at_ms: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub available_at_ms: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<StepResult>,
}

impl Default for StepExecution {
    fn default() -> Self {
        Self {
            status: StepStatus::Pending,
            attempts: 0,
            started_at_ms: None,
            completed_at_ms: None,
            available_at_ms: None,
            result: None,
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct WorkflowExecution {
    pub execution_id: String,
    pub definition_id: String,
    pub definition_version: u32,
    pub correlation_id: String,
    pub status: WorkflowStatus,
    pub created_at_ms: u64,
    pub updated_at_ms: u64,
    #[serde(default)]
    pub data: BTreeMap<String, Value>,
    #[serde(default)]
    pub metadata: BTreeMap<String, Value>,
    pub steps: BTreeMap<String, StepExecution>,
}

impl WorkflowExecution {
    pub fn create(
        definition: &WorkflowDefinition,
        execution_id: impl Into<String>,
        correlation_id: impl Into<String>,
        now_ms: u64,
        data: BTreeMap<String, Value>,
    ) -> Result<Self, WorkflowError> {
        definition.validate()?;
        let steps = definition
            .steps
            .iter()
            .map(|step| (step.id.clone(), StepExecution::default()))
            .collect();
        Ok(Self {
            execution_id: execution_id.into(),
            definition_id: definition.id.clone(),
            definition_version: definition.version,
            correlation_id: correlation_id.into(),
            status: WorkflowStatus::Created,
            created_at_ms: now_ms,
            updated_at_ms: now_ms,
            data,
            metadata: BTreeMap::new(),
            steps,
        })
    }

    pub fn start(&mut self, now_ms: u64) -> Result<(), WorkflowError> {
        self.transition(WorkflowStatus::Created, WorkflowStatus::Running, now_ms)
    }

    pub fn pause(&mut self, now_ms: u64) -> Result<(), WorkflowError> {
        self.transition(WorkflowStatus::Running, WorkflowStatus::Paused, now_ms)
    }

    pub fn resume(&mut self, now_ms: u64) -> Result<(), WorkflowError> {
        self.transition(WorkflowStatus::Paused, WorkflowStatus::Running, now_ms)
    }

    pub fn cancel(&mut self, now_ms: u64) -> Result<(), WorkflowError> {
        if matches!(
            self.status,
            WorkflowStatus::Completed
                | WorkflowStatus::Compensated
                | WorkflowStatus::Cancelled
                | WorkflowStatus::CompensationFailed
        ) {
            return Err(WorkflowError::InvalidTransition {
                from: self.status,
                to: WorkflowStatus::Cancelled,
            });
        }
        self.status = WorkflowStatus::Cancelled;
        self.updated_at_ms = now_ms;
        Ok(())
    }

    #[must_use]
    pub fn ready_steps(&self, definition: &WorkflowDefinition, now_ms: u64) -> Vec<String> {
        if self.status != WorkflowStatus::Running {
            return Vec::new();
        }
        definition
            .steps
            .iter()
            .filter(|step| {
                let execution = &self.steps[&step.id];
                matches!(
                    execution.status,
                    StepStatus::Pending | StepStatus::WaitingRetry
                ) && execution
                    .available_at_ms
                    .is_none_or(|available| available <= now_ms)
                    && step.dependencies.iter().all(|dependency| {
                        self.steps
                            .get(dependency)
                            .is_some_and(|execution| execution.status == StepStatus::Completed)
                    })
            })
            .map(|step| step.id.clone())
            .collect()
    }

    pub fn begin_step(
        &mut self,
        definition: &WorkflowDefinition,
        step_id: &str,
        now_ms: u64,
    ) -> Result<(), WorkflowError> {
        if self.status != WorkflowStatus::Running {
            return Err(WorkflowError::InvalidOperation(
                "workflow is not running".to_owned(),
            ));
        }
        if !self
            .ready_steps(definition, now_ms)
            .iter()
            .any(|id| id == step_id)
        {
            return Err(WorkflowError::InvalidOperation(format!(
                "step '{step_id}' is not ready"
            )));
        }
        let step = self.step_mut(step_id)?;
        step.status = StepStatus::Running;
        step.attempts = step.attempts.saturating_add(1);
        step.started_at_ms = Some(now_ms);
        step.available_at_ms = None;
        self.updated_at_ms = now_ms;
        Ok(())
    }

    pub fn defer_step(
        &mut self,
        definition: &WorkflowDefinition,
        step_id: &str,
        available_at_ms: u64,
        now_ms: u64,
    ) -> Result<(), WorkflowError> {
        let definition_step = definition
            .steps
            .iter()
            .find(|step| step.id == step_id)
            .ok_or_else(|| WorkflowError::UnknownStep(step_id.to_owned()))?;
        if definition_step.step_type != StepType::Wait || available_at_ms <= now_ms {
            return Err(WorkflowError::InvalidOperation(
                "only wait steps may be deferred into the future".to_owned(),
            ));
        }
        let step = self.step_mut(step_id)?;
        if step.status != StepStatus::Pending {
            return Err(WorkflowError::InvalidOperation(format!(
                "step '{step_id}' cannot be deferred"
            )));
        }
        step.status = StepStatus::WaitingRetry;
        step.available_at_ms = Some(available_at_ms);
        self.updated_at_ms = now_ms;
        Ok(())
    }

    pub fn skip_step(&mut self, step_id: &str, now_ms: u64) -> Result<(), WorkflowError> {
        let step = self.step_mut(step_id)?;
        if step.status != StepStatus::Pending {
            return Err(WorkflowError::InvalidOperation(format!(
                "step '{step_id}' cannot be skipped"
            )));
        }
        step.status = StepStatus::Skipped;
        step.completed_at_ms = Some(now_ms);
        self.updated_at_ms = now_ms;
        Ok(())
    }

    pub fn reset_loop_step(
        &mut self,
        definition: &WorkflowDefinition,
        step_id: &str,
        now_ms: u64,
    ) -> Result<(), WorkflowError> {
        let definition_step = definition
            .steps
            .iter()
            .find(|step| step.id == step_id)
            .ok_or_else(|| WorkflowError::UnknownStep(step_id.to_owned()))?;
        if definition_step.step_type != StepType::Loop {
            return Err(WorkflowError::InvalidOperation(
                "only loop steps can be reset".to_owned(),
            ));
        }
        let step = self.step_mut(step_id)?;
        if step.status != StepStatus::Completed {
            return Err(WorkflowError::InvalidOperation(format!(
                "loop step '{step_id}' is not complete"
            )));
        }
        *step = StepExecution::default();
        self.status = WorkflowStatus::Running;
        self.updated_at_ms = now_ms;
        Ok(())
    }

    pub fn complete_step(
        &mut self,
        definition: &WorkflowDefinition,
        step_id: &str,
        result: StepResult,
        now_ms: u64,
    ) -> Result<(), WorkflowError> {
        let definition_step = definition
            .steps
            .iter()
            .find(|step| step.id == step_id)
            .ok_or_else(|| WorkflowError::UnknownStep(step_id.to_owned()))?;
        let step = self.step_mut(step_id)?;
        if step.status != StepStatus::Running {
            return Err(WorkflowError::InvalidOperation(format!(
                "step '{step_id}' is not running"
            )));
        }
        if result.success {
            step.status = StepStatus::Completed;
            step.completed_at_ms = Some(now_ms);
            step.result = Some(result);
        } else if result.should_retry && step.attempts < definition_step.retry.max_attempts {
            step.status = StepStatus::WaitingRetry;
            step.available_at_ms = Some(
                now_ms.saturating_add(
                    result
                        .retry_delay_ms
                        .unwrap_or_else(|| definition_step.retry.delay_ms(step.attempts)),
                ),
            );
            step.result = Some(result);
        } else {
            step.status = StepStatus::Failed;
            step.completed_at_ms = Some(now_ms);
            step.result = Some(result);
            self.status = if self.has_compensatable_steps(definition) {
                WorkflowStatus::Compensating
            } else {
                WorkflowStatus::Failed
            };
        }
        self.updated_at_ms = now_ms;
        if self.status == WorkflowStatus::Running
            && self
                .steps
                .values()
                .all(|step| matches!(step.status, StepStatus::Completed | StepStatus::Skipped))
        {
            self.status = WorkflowStatus::Completed;
        }
        Ok(())
    }

    #[must_use]
    pub fn next_compensation(&self, definition: &WorkflowDefinition) -> Option<(String, String)> {
        if self.status != WorkflowStatus::Compensating {
            return None;
        }
        definition.steps.iter().rev().find_map(|definition_step| {
            let execution = &self.steps[&definition_step.id];
            (execution.status == StepStatus::Completed).then(|| {
                definition_step
                    .compensation
                    .as_ref()
                    .map(|compensation| (definition_step.id.clone(), compensation.clone()))
            })?
        })
    }

    pub fn begin_compensation(&mut self, step_id: &str, now_ms: u64) -> Result<(), WorkflowError> {
        if self.status != WorkflowStatus::Compensating {
            return Err(WorkflowError::InvalidOperation(
                "workflow is not compensating".to_owned(),
            ));
        }
        let step = self.step_mut(step_id)?;
        if step.status != StepStatus::Completed {
            return Err(WorkflowError::InvalidOperation(format!(
                "step '{step_id}' cannot be compensated"
            )));
        }
        step.status = StepStatus::Compensating;
        self.updated_at_ms = now_ms;
        Ok(())
    }

    pub fn complete_compensation(
        &mut self,
        definition: &WorkflowDefinition,
        step_id: &str,
        success: bool,
        now_ms: u64,
    ) -> Result<(), WorkflowError> {
        let step = self.step_mut(step_id)?;
        if step.status != StepStatus::Compensating {
            return Err(WorkflowError::InvalidOperation(format!(
                "step '{step_id}' is not compensating"
            )));
        }
        step.status = if success {
            StepStatus::Compensated
        } else {
            StepStatus::CompensationFailed
        };
        self.updated_at_ms = now_ms;
        if !success {
            self.status = WorkflowStatus::CompensationFailed;
        } else if self.next_compensation(definition).is_none() {
            self.status = WorkflowStatus::Compensated;
        }
        Ok(())
    }

    pub fn enforce_timeout(
        &mut self,
        definition: &WorkflowDefinition,
        now_ms: u64,
    ) -> Result<bool, WorkflowError> {
        definition.validate()?;
        let workflow_expired = definition
            .timeout_ms
            .is_some_and(|timeout| now_ms.saturating_sub(self.created_at_ms) >= timeout);
        let step_expired = definition.steps.iter().any(|definition_step| {
            let execution = &self.steps[&definition_step.id];
            execution.status == StepStatus::Running
                && definition_step.timeout_ms.is_some_and(|timeout| {
                    execution
                        .started_at_ms
                        .is_some_and(|started| now_ms.saturating_sub(started) >= timeout)
                })
        });
        if workflow_expired || step_expired {
            self.status = WorkflowStatus::TimedOut;
            self.updated_at_ms = now_ms;
            return Ok(true);
        }
        Ok(false)
    }

    fn has_compensatable_steps(&self, definition: &WorkflowDefinition) -> bool {
        definition.steps.iter().any(|definition_step| {
            definition_step.compensation.is_some()
                && self.steps[&definition_step.id].status == StepStatus::Completed
        })
    }

    fn step_mut(&mut self, step_id: &str) -> Result<&mut StepExecution, WorkflowError> {
        self.steps
            .get_mut(step_id)
            .ok_or_else(|| WorkflowError::UnknownStep(step_id.to_owned()))
    }

    fn transition(
        &mut self,
        expected: WorkflowStatus,
        next: WorkflowStatus,
        now_ms: u64,
    ) -> Result<(), WorkflowError> {
        if self.status != expected {
            return Err(WorkflowError::InvalidTransition {
                from: self.status,
                to: next,
            });
        }
        self.status = next;
        self.updated_at_ms = now_ms;
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SagaStepDefinition {
    pub id: String,
    #[serde(default)]
    pub dependencies: BTreeSet<String>,
    pub action: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub compensation: Option<String>,
    #[serde(default)]
    pub retry: WorkflowRetryPolicy,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timeout_ms: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SagaDefinition {
    pub id: String,
    pub version: u32,
    pub steps: Vec<SagaStepDefinition>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timeout_ms: Option<u64>,
}

impl SagaDefinition {
    #[must_use]
    pub fn as_workflow(&self) -> WorkflowDefinition {
        WorkflowDefinition {
            id: self.id.clone(),
            version: self.version,
            timeout_ms: self.timeout_ms,
            steps: self
                .steps
                .iter()
                .map(|step| StepDefinition {
                    id: step.id.clone(),
                    step_type: StepType::Action,
                    dependencies: step.dependencies.clone(),
                    retry: step.retry.clone(),
                    timeout_ms: step.timeout_ms,
                    compensation: step.compensation.clone(),
                    configuration: serde_json::json!({"action": step.action}),
                })
                .collect(),
        }
    }
}

#[async_trait]
pub trait WorkflowRepository: Send + Sync {
    async fn save(&self, execution: WorkflowExecution) -> Result<(), WorkflowError>;
    async fn load(&self, execution_id: &str) -> Result<Option<WorkflowExecution>, WorkflowError>;
}

#[derive(Debug, Default)]
pub struct InMemoryWorkflowRepository {
    executions: Mutex<BTreeMap<String, WorkflowExecution>>,
}

#[async_trait]
impl WorkflowRepository for InMemoryWorkflowRepository {
    async fn save(&self, execution: WorkflowExecution) -> Result<(), WorkflowError> {
        self.executions
            .lock()
            .map_err(|_| WorkflowError::Repository("workflow repository poisoned".to_owned()))?
            .insert(execution.execution_id.clone(), execution);
        Ok(())
    }

    async fn load(&self, execution_id: &str) -> Result<Option<WorkflowExecution>, WorkflowError> {
        Ok(self
            .executions
            .lock()
            .map_err(|_| WorkflowError::Repository("workflow repository poisoned".to_owned()))?
            .get(execution_id)
            .cloned())
    }
}

#[async_trait]
pub trait WorkflowActionProvider: Send + Sync {
    async fn execute(
        &self,
        action: &str,
        execution: &WorkflowExecution,
        step: &StepDefinition,
    ) -> Result<StepResult, WorkflowError>;
    async fn compensate(
        &self,
        action: &str,
        execution: &WorkflowExecution,
        step: &StepDefinition,
    ) -> Result<(), WorkflowError>;
}

#[derive(Debug, Error)]
pub enum WorkflowError {
    #[error("invalid workflow definition: {0}")]
    InvalidDefinition(String),
    #[error("invalid workflow transition from {from:?} to {to:?}")]
    InvalidTransition {
        from: WorkflowStatus,
        to: WorkflowStatus,
    },
    #[error("unknown workflow step: {0}")]
    UnknownStep(String),
    #[error("invalid workflow operation: {0}")]
    InvalidOperation(String),
    #[error("workflow repository error: {0}")]
    Repository(String),
    #[error("workflow action provider unavailable: {0}")]
    ProviderUnavailable(String),
}
