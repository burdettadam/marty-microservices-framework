//! Persistence models and ports for the built-in identity service.

use std::collections::{BTreeMap, BTreeSet};

use async_trait::async_trait;
use mmf_security::{AuthenticatedUser, AuthenticationMethod};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::RwLock;

use crate::ServiceError;

/// Stable storage representation independent of a database implementation.
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct IdentityUserRecord {
    #[serde(flatten)]
    pub user: AuthenticatedUser,
}

impl IdentityUserRecord {
    pub fn validate(&self) -> Result<(), ServiceError> {
        self.user
            .validate()
            .map_err(|error| ServiceError::InvalidConfiguration(error.to_string()))?;
        Ok(())
    }
}

/// Explicit update fields prevent adapters from mutating storage-only columns.
#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct IdentityUserPatch {
    pub username: Option<Option<String>>,
    pub email: Option<Option<String>>,
    pub roles: Option<BTreeSet<String>>,
    pub permissions: Option<BTreeSet<String>>,
    pub session_id: Option<Option<String>>,
    pub auth_method: Option<Option<AuthenticationMethod>>,
    pub expires_at_ms: Option<Option<u64>>,
    pub attributes: Option<BTreeMap<String, Value>>,
    pub user_type: Option<Option<String>>,
    pub applicant_id: Option<Option<String>>,
}

impl IdentityUserPatch {
    fn apply_to(self, record: &mut IdentityUserRecord) {
        if let Some(value) = self.username {
            record.user.username = value;
        }
        if let Some(value) = self.email {
            record.user.email = value;
        }
        if let Some(value) = self.roles {
            record.user.roles = value;
        }
        if let Some(value) = self.permissions {
            record.user.permissions = value;
        }
        if let Some(value) = self.session_id {
            record.user.session_id = value;
        }
        if let Some(value) = self.auth_method {
            record.user.auth_method = value;
        }
        if let Some(value) = self.expires_at_ms {
            record.user.expires_at_ms = value;
        }
        if let Some(value) = self.attributes {
            record.user.attributes = value;
        }
        if let Some(value) = self.user_type {
            record.user.user_type = value;
        }
        if let Some(value) = self.applicant_id {
            record.user.applicant_id = value;
        }
    }
}

/// Database-neutral repository contract implemented by memory, SQL, or remote adapters.
#[async_trait]
pub trait IdentityUserRepository: Send + Sync {
    async fn insert(&self, record: IdentityUserRecord) -> Result<IdentityUserRecord, ServiceError>;
    async fn upsert(&self, record: IdentityUserRecord) -> Result<IdentityUserRecord, ServiceError>;
    async fn find_by_id(&self, user_id: &str) -> Result<Option<IdentityUserRecord>, ServiceError>;
    async fn find_by_username(
        &self,
        username: &str,
    ) -> Result<Option<IdentityUserRecord>, ServiceError>;
    async fn find_by_email(&self, email: &str) -> Result<Option<IdentityUserRecord>, ServiceError>;
    async fn find_by_session_id(
        &self,
        session_id: &str,
    ) -> Result<Option<IdentityUserRecord>, ServiceError>;
    async fn list(
        &self,
        offset: usize,
        limit: usize,
    ) -> Result<Vec<IdentityUserRecord>, ServiceError>;
    async fn update(
        &self,
        user_id: &str,
        patch: IdentityUserPatch,
    ) -> Result<IdentityUserRecord, ServiceError>;
    async fn delete(&self, user_id: &str) -> Result<bool, ServiceError>;
    async fn exists(&self, user_id: &str) -> Result<bool, ServiceError>;
    async fn count(&self) -> Result<u64, ServiceError>;
}

/// Deterministic adapter for tests, development, and single-process services.
#[derive(Default)]
pub struct InMemoryIdentityUserRepository {
    records: RwLock<BTreeMap<String, IdentityUserRecord>>,
}

impl InMemoryIdentityUserRepository {
    fn validate_unique(
        records: &BTreeMap<String, IdentityUserRecord>,
        candidate: &IdentityUserRecord,
        replacing_id: Option<&str>,
    ) -> Result<(), ServiceError> {
        for record in records
            .values()
            .filter(|record| replacing_id.is_none_or(|user_id| record.user.user_id != user_id))
        {
            if candidate.user.username.is_some() && candidate.user.username == record.user.username
            {
                return Err(ServiceError::Conflict(format!(
                    "username {} is already assigned",
                    candidate.user.username.as_deref().unwrap_or_default()
                )));
            }
            if candidate.user.email.is_some() && candidate.user.email == record.user.email {
                return Err(ServiceError::Conflict(format!(
                    "email {} is already assigned",
                    candidate.user.email.as_deref().unwrap_or_default()
                )));
            }
            if candidate.user.session_id.is_some()
                && candidate.user.session_id == record.user.session_id
            {
                return Err(ServiceError::Conflict(format!(
                    "session {} is already assigned",
                    candidate.user.session_id.as_deref().unwrap_or_default()
                )));
            }
        }
        Ok(())
    }

    fn find(
        records: &BTreeMap<String, IdentityUserRecord>,
        predicate: impl Fn(&IdentityUserRecord) -> bool,
    ) -> Option<IdentityUserRecord> {
        records.values().find(|record| predicate(record)).cloned()
    }
}

#[async_trait]
impl IdentityUserRepository for InMemoryIdentityUserRepository {
    async fn insert(&self, record: IdentityUserRecord) -> Result<IdentityUserRecord, ServiceError> {
        record.validate()?;
        let mut records = self.records.write().await;
        if records.contains_key(&record.user.user_id) {
            return Err(ServiceError::Conflict(format!(
                "user {} already exists",
                record.user.user_id
            )));
        }
        Self::validate_unique(&records, &record, None)?;
        records.insert(record.user.user_id.clone(), record.clone());
        Ok(record)
    }

    async fn upsert(&self, record: IdentityUserRecord) -> Result<IdentityUserRecord, ServiceError> {
        record.validate()?;
        let mut records = self.records.write().await;
        Self::validate_unique(&records, &record, Some(&record.user.user_id))?;
        records.insert(record.user.user_id.clone(), record.clone());
        Ok(record)
    }

    async fn find_by_id(&self, user_id: &str) -> Result<Option<IdentityUserRecord>, ServiceError> {
        Ok(self.records.read().await.get(user_id).cloned())
    }

    async fn find_by_username(
        &self,
        username: &str,
    ) -> Result<Option<IdentityUserRecord>, ServiceError> {
        let records = self.records.read().await;
        Ok(Self::find(&records, |record| {
            record.user.username.as_deref() == Some(username)
        }))
    }

    async fn find_by_email(&self, email: &str) -> Result<Option<IdentityUserRecord>, ServiceError> {
        let records = self.records.read().await;
        Ok(Self::find(&records, |record| {
            record.user.email.as_deref() == Some(email)
        }))
    }

    async fn find_by_session_id(
        &self,
        session_id: &str,
    ) -> Result<Option<IdentityUserRecord>, ServiceError> {
        let records = self.records.read().await;
        Ok(Self::find(&records, |record| {
            record.user.session_id.as_deref() == Some(session_id)
        }))
    }

    async fn list(
        &self,
        offset: usize,
        limit: usize,
    ) -> Result<Vec<IdentityUserRecord>, ServiceError> {
        if limit == 0 {
            return Err(ServiceError::InvalidConfiguration(
                "pagination limit must be greater than zero".into(),
            ));
        }
        Ok(self
            .records
            .read()
            .await
            .values()
            .skip(offset)
            .take(limit)
            .cloned()
            .collect())
    }

    async fn update(
        &self,
        user_id: &str,
        patch: IdentityUserPatch,
    ) -> Result<IdentityUserRecord, ServiceError> {
        let mut records = self.records.write().await;
        let mut record = records
            .get(user_id)
            .cloned()
            .ok_or_else(|| ServiceError::NotFound(format!("user {user_id} was not found")))?;
        patch.apply_to(&mut record);
        record.validate()?;
        Self::validate_unique(&records, &record, Some(user_id))?;
        records.insert(user_id.into(), record.clone());
        Ok(record)
    }

    async fn delete(&self, user_id: &str) -> Result<bool, ServiceError> {
        Ok(self.records.write().await.remove(user_id).is_some())
    }

    async fn exists(&self, user_id: &str) -> Result<bool, ServiceError> {
        Ok(self.records.read().await.contains_key(user_id))
    }

    async fn count(&self) -> Result<u64, ServiceError> {
        u64::try_from(self.records.read().await.len())
            .map_err(|_| ServiceError::Operation("user count exceeds u64".into()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Deserialize)]
    struct Fixture {
        schema_version: u32,
        users: Vec<FixtureUser>,
        updates: FixtureUpdates,
        pagination: FixturePagination,
        failures: FixtureFailures,
    }

    #[derive(Deserialize)]
    struct FixtureUser {
        user_id: String,
        username: String,
        email: String,
        roles: BTreeSet<String>,
        permissions: BTreeSet<String>,
        session_id: String,
        auth_method: AuthenticationMethod,
        expires_at_ms: Option<u64>,
        created_at_ms: u64,
    }

    #[derive(Deserialize)]
    struct FixtureUpdates {
        email: String,
        roles: BTreeSet<String>,
    }

    #[derive(Deserialize)]
    struct FixturePagination {
        offset: usize,
        limit: usize,
        expected_user_id: String,
    }

    #[derive(Deserialize)]
    struct FixtureFailures {
        duplicate_user_id: String,
        duplicate_username: String,
        missing_user: String,
        zero_limit: String,
    }

    fn fixture() -> Fixture {
        serde_json::from_str(include_str!(
            "../../../contracts/identity-service-persistence-behavior.json"
        ))
        .expect("valid persistence behavior fixture")
    }

    fn record(user: &FixtureUser) -> IdentityUserRecord {
        IdentityUserRecord {
            user: AuthenticatedUser {
                user_id: user.user_id.clone(),
                username: Some(user.username.clone()),
                email: Some(user.email.clone()),
                roles: user.roles.clone(),
                permissions: user.permissions.clone(),
                session_id: Some(user.session_id.clone()),
                auth_method: Some(user.auth_method),
                expires_at_ms: user.expires_at_ms,
                created_at_ms: Some(user.created_at_ms),
                attributes: BTreeMap::new(),
                user_type: None,
                applicant_id: None,
            },
        }
    }

    #[tokio::test]
    async fn language_neutral_crud_and_query_behavior() {
        let fixture = fixture();
        assert_eq!(fixture.schema_version, 1);
        let repository = InMemoryIdentityUserRepository::default();
        for user in &fixture.users {
            repository.insert(record(user)).await.expect("insert");
        }
        assert_eq!(repository.count().await.expect("count"), 2);
        let first = &fixture.users[0];
        assert_eq!(
            repository
                .find_by_username(&first.username)
                .await
                .expect("find username")
                .expect("user")
                .user
                .user_id,
            first.user_id
        );
        assert!(
            repository
                .find_by_email(&first.email)
                .await
                .expect("find email")
                .is_some()
        );
        assert!(
            repository
                .find_by_session_id(&first.session_id)
                .await
                .expect("find session")
                .is_some()
        );
        let listed = repository
            .list(fixture.pagination.offset, fixture.pagination.limit)
            .await
            .expect("list");
        assert_eq!(listed[0].user.user_id, fixture.pagination.expected_user_id);
        let updated = repository
            .update(
                &first.user_id,
                IdentityUserPatch {
                    email: Some(Some(fixture.updates.email.clone())),
                    roles: Some(fixture.updates.roles.clone()),
                    ..IdentityUserPatch::default()
                },
            )
            .await
            .expect("update");
        assert_eq!(
            updated.user.email.as_deref(),
            Some(fixture.updates.email.as_str())
        );
        assert_eq!(updated.user.roles, fixture.updates.roles);
        assert!(repository.exists(&first.user_id).await.expect("exists"));
        assert!(repository.delete(&first.user_id).await.expect("delete"));
        assert!(!repository.exists(&first.user_id).await.expect("exists"));
    }

    #[tokio::test]
    async fn duplicate_invalid_and_missing_operations_fail_closed() {
        let fixture = fixture();
        let repository = InMemoryIdentityUserRepository::default();
        let first = record(&fixture.users[0]);
        repository.insert(first.clone()).await.expect("insert");
        assert_eq!(
            repository
                .insert(first.clone())
                .await
                .expect_err("duplicate")
                .to_string(),
            format!(
                "built-in service state conflict: {}",
                fixture.failures.duplicate_user_id
            )
        );
        let mut duplicate_name = record(&fixture.users[1]);
        duplicate_name.user.username = first.user.username.clone();
        assert_eq!(
            repository
                .insert(duplicate_name)
                .await
                .expect_err("duplicate")
                .to_string(),
            format!(
                "built-in service state conflict: {}",
                fixture.failures.duplicate_username
            )
        );
        assert_eq!(
            repository
                .update("missing", IdentityUserPatch::default())
                .await
                .expect_err("missing")
                .to_string(),
            format!(
                "built-in service record was not found: {}",
                fixture.failures.missing_user
            )
        );
        assert_eq!(
            repository
                .list(0, 0)
                .await
                .expect_err("zero limit")
                .to_string(),
            format!(
                "invalid built-in service configuration: {}",
                fixture.failures.zero_limit
            )
        );
    }
}
