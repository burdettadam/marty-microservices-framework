use async_trait::async_trait;
use serde::{Deserialize, Serialize};

use crate::DataError;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct MigrationRevision {
    pub revision: String,
    pub parent: Option<String>,
    pub description: String,
    pub applied_at_ms: Option<u64>,
    pub checksum: String,
}

impl MigrationRevision {
    pub fn validate(&self) -> Result<(), DataError> {
        if self.revision.trim().is_empty()
            || self.description.trim().is_empty()
            || self.checksum.trim().is_empty()
        {
            return Err(DataError::InvalidConfiguration(
                "migration revision, description, and checksum are required".into(),
            ));
        }
        Ok(())
    }
}

#[async_trait]
pub trait MigrationManager: Send + Sync {
    async fn initialize(
        &self,
        service_name: &str,
        migrations_location: &str,
    ) -> Result<(), DataError>;
    async fn create(
        &self,
        message: &str,
        autogenerate: bool,
        sql_mode: bool,
    ) -> Result<Option<MigrationRevision>, DataError>;
    async fn upgrade(&self, revision: &str, sql_mode: bool) -> Result<(), DataError>;
    async fn downgrade(&self, revision: &str, sql_mode: bool) -> Result<(), DataError>;
    async fn current(&self) -> Result<Option<String>, DataError>;
    async fn history(&self, verbose: bool) -> Result<Vec<MigrationRevision>, DataError>;
    async fn verify_schema(&self) -> Result<SchemaVerification, DataError>;
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SchemaVerification {
    pub matches: bool,
    pub current_revision: Option<String>,
    pub expected_revision: Option<String>,
    #[serde(default)]
    pub differences: Vec<String>,
}

impl SchemaVerification {
    pub fn require_match(&self) -> Result<(), DataError> {
        if self.matches && self.differences.is_empty() {
            Ok(())
        } else {
            Err(DataError::Migration(
                "database schema is out of date".into(),
            ))
        }
    }
}
