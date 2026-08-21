use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Mutex};

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::PatternError;

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum QueryExecutionMode {
    Sync,
    Async,
    Streaming,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Command {
    pub id: String,
    pub command_type: String,
    pub aggregate_id: Option<String>,
    pub correlation_id: Option<String>,
    pub causation_id: Option<String>,
    pub issued_at_ms: u64,
    #[serde(default)]
    pub payload: Value,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

impl Command {
    pub fn validate(&self) -> Result<(), PatternError> {
        if self.id.trim().is_empty() || self.command_type.trim().is_empty() {
            return Err(PatternError::InvalidConfiguration(
                "command requires an ID and type".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Query {
    pub id: String,
    pub query_type: String,
    pub correlation_id: Option<String>,
    pub issued_at_ms: u64,
    pub mode: QueryExecutionMode,
    #[serde(default)]
    pub payload: Value,
    #[serde(default)]
    pub metadata: BTreeMap<String, String>,
}

impl Query {
    pub fn validate(&self) -> Result<(), PatternError> {
        if self.id.trim().is_empty() || self.query_type.trim().is_empty() {
            return Err(PatternError::InvalidConfiguration(
                "query requires an ID and type".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CommandResult {
    pub success: bool,
    #[serde(default)]
    pub value: Value,
    #[serde(default)]
    pub emitted_event_ids: Vec<String>,
    pub error: Option<String>,
}

#[async_trait]
pub trait CommandHandler: Send + Sync {
    async fn handle(&self, command: &Command) -> Result<CommandResult, PatternError>;
}

#[async_trait]
pub trait QueryHandler: Send + Sync {
    async fn handle(&self, query: &Query) -> Result<Value, PatternError>;
}

#[derive(Default)]
pub struct CqrsBus {
    command_handlers: BTreeMap<String, Arc<dyn CommandHandler>>,
    query_handlers: BTreeMap<String, Arc<dyn QueryHandler>>,
    completed_commands: Mutex<BTreeMap<String, CommandResult>>,
    active_commands: Mutex<BTreeSet<String>>,
}

impl CqrsBus {
    pub fn register_command(
        &mut self,
        command_type: impl Into<String>,
        handler: Arc<dyn CommandHandler>,
    ) -> Result<(), PatternError> {
        let command_type = command_type.into();
        if command_type.trim().is_empty() || self.command_handlers.contains_key(&command_type) {
            return Err(PatternError::InvalidConfiguration(format!(
                "invalid or duplicate command handler: {command_type}"
            )));
        }
        self.command_handlers.insert(command_type, handler);
        Ok(())
    }

    pub fn register_query(
        &mut self,
        query_type: impl Into<String>,
        handler: Arc<dyn QueryHandler>,
    ) -> Result<(), PatternError> {
        let query_type = query_type.into();
        if query_type.trim().is_empty() || self.query_handlers.contains_key(&query_type) {
            return Err(PatternError::InvalidConfiguration(format!(
                "invalid or duplicate query handler: {query_type}"
            )));
        }
        self.query_handlers.insert(query_type, handler);
        Ok(())
    }

    pub async fn execute_command(&self, command: &Command) -> Result<CommandResult, PatternError> {
        command.validate()?;
        let handler = self
            .command_handlers
            .get(&command.command_type)
            .ok_or_else(|| PatternError::HandlerUnavailable(command.command_type.clone()))?;
        if let Some(result) = self
            .completed_commands
            .lock()
            .map_err(|_| PatternError::Operation("command result store poisoned".to_owned()))?
            .get(&command.id)
            .cloned()
        {
            return Ok(result);
        }
        {
            let mut active = self
                .active_commands
                .lock()
                .map_err(|_| PatternError::Operation("command lock poisoned".to_owned()))?;
            if !active.insert(command.id.clone()) {
                return Err(PatternError::Duplicate(command.id.clone()));
            }
        }
        let result = handler.handle(command).await;
        self.active_commands
            .lock()
            .map_err(|_| PatternError::Operation("command lock poisoned".to_owned()))?
            .remove(&command.id);
        let result = result?;
        self.completed_commands
            .lock()
            .map_err(|_| PatternError::Operation("command result store poisoned".to_owned()))?
            .insert(command.id.clone(), result.clone());
        Ok(result)
    }

    pub async fn execute_query(&self, query: &Query) -> Result<Value, PatternError> {
        query.validate()?;
        self.query_handlers
            .get(&query.query_type)
            .ok_or_else(|| PatternError::HandlerUnavailable(query.query_type.clone()))?
            .handle(query)
            .await
    }
}
