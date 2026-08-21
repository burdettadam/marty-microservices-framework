use sqlx::{PgPool, Postgres, Row, Transaction};
use uuid::Uuid;

use crate::{DeadLetter, Message, MessageStatus, MessagingError, OutboxEntry, stable_partition};

const MIGRATION_LOCK_ID: i64 = 7_141_925_003_001;

#[derive(Clone, Debug)]
pub struct PostgresOutboxStore {
    pool: PgPool,
    source_service: String,
    partition_count: u32,
}

impl PostgresOutboxStore {
    pub fn new(
        pool: PgPool,
        source_service: impl Into<String>,
        partition_count: u32,
    ) -> Result<Self, MessagingError> {
        let source_service = source_service.into();
        if source_service.trim().is_empty() || partition_count == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "outbox source service and positive partition count are required".into(),
            ));
        }
        Ok(Self {
            pool,
            source_service,
            partition_count,
        })
    }

    #[must_use]
    pub fn pool(&self) -> &PgPool {
        &self.pool
    }

    pub async fn migrate(&self) -> Result<(), MessagingError> {
        let mut transaction = self.pool.begin().await.map_err(storage)?;
        sqlx::query("SELECT pg_advisory_xact_lock($1)")
            .bind(MIGRATION_LOCK_ID)
            .execute(&mut *transaction)
            .await
            .map_err(storage)?;
        sqlx::raw_sql(include_str!("../migrations/0001_postgres_outbox.sql"))
            .execute(&mut *transaction)
            .await
            .map_err(storage)?;
        transaction.commit().await.map_err(storage)
    }

    pub async fn enqueue(&self, message: Message) -> Result<u32, MessagingError> {
        let mut transaction = self.pool.begin().await.map_err(storage)?;
        let partition = self
            .enqueue_in_transaction(&mut transaction, message)
            .await?;
        transaction.commit().await.map_err(storage)?;
        Ok(partition)
    }

    pub async fn enqueue_in_transaction(
        &self,
        transaction: &mut Transaction<'_, Postgres>,
        mut message: Message,
    ) -> Result<u32, MessagingError> {
        match message.metadata.source_service.as_deref() {
            Some(source) if source != self.source_service => {
                return Err(MessagingError::InvalidConfiguration(
                    "message source does not match the outbox source service".into(),
                ));
            }
            None => message.metadata.source_service = Some(self.source_service.clone()),
            Some(_) => {}
        }
        message.validate(message.metadata.created_at_ms)?;
        let message_id = message.metadata.message_id.clone();
        let partition_key = message
            .metadata
            .partition_key
            .as_deref()
            .or(message.metadata.ordering_key.as_deref())
            .unwrap_or(&message_id);
        let partition = stable_partition(partition_key, self.partition_count);
        let message_json = serde_json::to_value(&message)
            .map_err(|error| MessagingError::Serialization(error.to_string()))?;
        let result = sqlx::query(
            "INSERT INTO mmf_messaging.outbox_messages (
                message_id,source_service,tenant_id,partition,priority,message,status,
                attempt_count,max_attempts,next_attempt_at_ms,last_error,processed_at_ms,
                lease_token,lease_expires_at_ms,created_at_ms,scheduled_at_ms,expires_at_ms
             ) VALUES ($1,$2,$3,$4,$5,$6,$7,0,$8,NULL,NULL,NULL,NULL,NULL,$9,$10,$11)",
        )
        .bind(&message_id)
        .bind(&self.source_service)
        .bind(&message.metadata.tenant_id)
        .bind(i32::try_from(partition).map_err(|_| {
            MessagingError::InvalidConfiguration("outbox partition exceeds PostgreSQL range".into())
        })?)
        .bind(i16::from(message.priority.value()))
        .bind(message_json)
        .bind(status_name(MessageStatus::Pending))
        .bind(
            i32::try_from(message.max_retries.saturating_add(1)).map_err(|_| {
                MessagingError::InvalidConfiguration(
                    "outbox retry count exceeds PostgreSQL range".into(),
                )
            })?,
        )
        .bind(to_i64(message.metadata.created_at_ms, "created_at_ms")?)
        .bind(optional_i64(
            message.metadata.scheduled_at_ms,
            "scheduled_at_ms",
        )?)
        .bind(optional_i64(
            message.metadata.expires_at_ms,
            "expires_at_ms",
        )?)
        .execute(&mut **transaction)
        .await;
        match result {
            Ok(_) => Ok(partition),
            Err(error)
                if error
                    .as_database_error()
                    .and_then(sqlx::error::DatabaseError::code)
                    .as_deref()
                    == Some("23505") =>
            {
                Err(MessagingError::Duplicate(message_id))
            }
            Err(error) => Err(storage(error)),
        }
    }

    pub async fn claim_due(
        &self,
        now_ms: u64,
        lease_duration_ms: u64,
        limit: usize,
        partition: Option<u32>,
    ) -> Result<Vec<OutboxEntry>, MessagingError> {
        if lease_duration_ms == 0 || limit == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "outbox lease duration and claim limit must be greater than zero".into(),
            ));
        }
        let now = to_i64(now_ms, "now_ms")?;
        let lease_expires = to_i64(
            now_ms.saturating_add(lease_duration_ms),
            "lease_expires_at_ms",
        )?;
        let partition = partition
            .map(|value| {
                i32::try_from(value).map_err(|_| {
                    MessagingError::InvalidConfiguration(
                        "outbox partition exceeds PostgreSQL range".into(),
                    )
                })
            })
            .transpose()?;
        let mut transaction = self.pool.begin().await.map_err(storage)?;
        sqlx::query(
            "UPDATE mmf_messaging.outbox_messages
             SET status='retry',lease_token=NULL,lease_expires_at_ms=NULL
             WHERE source_service=$1 AND status='processing'
               AND lease_expires_at_ms IS NOT NULL AND lease_expires_at_ms <= $2",
        )
        .bind(&self.source_service)
        .bind(now)
        .execute(&mut *transaction)
        .await
        .map_err(storage)?;
        let ids = sqlx::query(
            "SELECT message_id FROM mmf_messaging.outbox_messages
             WHERE source_service=$1 AND status IN ('pending','retry')
               AND (scheduled_at_ms IS NULL OR scheduled_at_ms <= $2)
               AND (next_attempt_at_ms IS NULL OR next_attempt_at_ms <= $2)
               AND (expires_at_ms IS NULL OR expires_at_ms > $2)
               AND ($3::integer IS NULL OR partition=$3)
             ORDER BY priority DESC,created_at_ms,message_id
             FOR UPDATE SKIP LOCKED LIMIT $4",
        )
        .bind(&self.source_service)
        .bind(now)
        .bind(partition)
        .bind(i64::try_from(limit).unwrap_or(i64::MAX))
        .fetch_all(&mut *transaction)
        .await
        .map_err(storage)?;
        let mut claimed = Vec::with_capacity(ids.len());
        for row in ids {
            let message_id: String = row.try_get("message_id").map_err(storage)?;
            let token = Uuid::new_v4().to_string();
            let row = sqlx::query(
                "UPDATE mmf_messaging.outbox_messages
                 SET status='processing',attempt_count=attempt_count+1,
                     lease_token=$3,lease_expires_at_ms=$4
                 WHERE source_service=$1 AND message_id=$2 RETURNING *",
            )
            .bind(&self.source_service)
            .bind(message_id)
            .bind(token)
            .bind(lease_expires)
            .fetch_one(&mut *transaction)
            .await
            .map_err(storage)?;
            claimed.push(entry_from_row(&row)?);
        }
        transaction.commit().await.map_err(storage)?;
        Ok(claimed)
    }

    pub async fn mark_processed_by_lease(
        &self,
        message_id: &str,
        lease_token: &str,
        now_ms: u64,
    ) -> Result<(), MessagingError> {
        require_identity(message_id, lease_token)?;
        let result = sqlx::query(
            "UPDATE mmf_messaging.outbox_messages
             SET status='processed',processed_at_ms=$4,last_error=NULL,
                 lease_token=NULL,lease_expires_at_ms=NULL
             WHERE source_service=$1 AND message_id=$2 AND status='processing' AND lease_token=$3",
        )
        .bind(&self.source_service)
        .bind(message_id)
        .bind(lease_token)
        .bind(to_i64(now_ms, "now_ms")?)
        .execute(&self.pool)
        .await
        .map_err(storage)?;
        require_lease_update(result.rows_affected(), message_id)
    }

    pub async fn mark_failed_by_lease(
        &self,
        message_id: &str,
        lease_token: &str,
        reason: &str,
        next_attempt_at_ms: Option<u64>,
        now_ms: u64,
    ) -> Result<MessageStatus, MessagingError> {
        require_identity(message_id, lease_token)?;
        if reason.trim().is_empty() {
            return Err(MessagingError::InvalidConfiguration(
                "outbox failure reason is required".into(),
            ));
        }
        let mut transaction = self.pool.begin().await.map_err(storage)?;
        let row = sqlx::query(
            "SELECT attempt_count,max_attempts FROM mmf_messaging.outbox_messages
             WHERE source_service=$1 AND message_id=$2 AND status='processing'
               AND lease_token=$3 FOR UPDATE",
        )
        .bind(&self.source_service)
        .bind(message_id)
        .bind(lease_token)
        .fetch_optional(&mut *transaction)
        .await
        .map_err(storage)?
        .ok_or_else(|| MessagingError::LeaseConflict(message_id.to_owned()))?;
        let attempt_count: i32 = row.try_get("attempt_count").map_err(storage)?;
        let max_attempts: i32 = row.try_get("max_attempts").map_err(storage)?;
        let status = if attempt_count >= max_attempts {
            MessageStatus::DeadLetter
        } else {
            MessageStatus::Retry
        };
        sqlx::query(
            "UPDATE mmf_messaging.outbox_messages
             SET status=$4,last_error=$5,next_attempt_at_ms=$6,
                 processed_at_ms=CASE WHEN $4='dead_letter' THEN $7 ELSE processed_at_ms END,
                 lease_token=NULL,lease_expires_at_ms=NULL
             WHERE source_service=$1 AND message_id=$2 AND lease_token=$3",
        )
        .bind(&self.source_service)
        .bind(message_id)
        .bind(lease_token)
        .bind(status_name(status))
        .bind(reason)
        .bind(optional_i64(next_attempt_at_ms, "next_attempt_at_ms")?)
        .bind(to_i64(now_ms, "now_ms")?)
        .execute(&mut *transaction)
        .await
        .map_err(storage)?;
        transaction.commit().await.map_err(storage)?;
        Ok(status)
    }

    pub async fn requeue_dead_letter(&self, message_id: &str) -> Result<bool, MessagingError> {
        if message_id.trim().is_empty() {
            return Err(MessagingError::InvalidConfiguration(
                "outbox message ID is required".into(),
            ));
        }
        let result = sqlx::query(
            "UPDATE mmf_messaging.outbox_messages
             SET status='pending',attempt_count=0,next_attempt_at_ms=NULL,last_error=NULL,
                 processed_at_ms=NULL,lease_token=NULL,lease_expires_at_ms=NULL
             WHERE source_service=$1 AND message_id=$2 AND status='dead_letter'",
        )
        .bind(&self.source_service)
        .bind(message_id)
        .execute(&self.pool)
        .await
        .map_err(storage)?;
        Ok(result.rows_affected() == 1)
    }

    pub async fn begin_inbox(&self, message_id: &str, now_ms: u64) -> Result<(), MessagingError> {
        let mut transaction = self.pool.begin().await.map_err(storage)?;
        self.begin_inbox_in_transaction(&mut transaction, message_id, now_ms)
            .await?;
        transaction.commit().await.map_err(storage)
    }

    pub async fn begin_inbox_in_transaction(
        &self,
        transaction: &mut Transaction<'_, Postgres>,
        message_id: &str,
        now_ms: u64,
    ) -> Result<(), MessagingError> {
        if message_id.trim().is_empty() {
            return Err(MessagingError::InvalidConfiguration(
                "inbox message ID is required".into(),
            ));
        }
        let result = sqlx::query(
            "INSERT INTO mmf_messaging.inbox_messages(source_service,message_id,processed_at_ms)
             VALUES ($1,$2,$3)",
        )
        .bind(&self.source_service)
        .bind(message_id)
        .bind(to_i64(now_ms, "now_ms")?)
        .execute(&mut **transaction)
        .await;
        match result {
            Ok(_) => Ok(()),
            Err(error)
                if error
                    .as_database_error()
                    .and_then(sqlx::error::DatabaseError::code)
                    .as_deref()
                    == Some("23505") =>
            {
                Err(MessagingError::Duplicate(message_id.to_owned()))
            }
            Err(error) => Err(storage(error)),
        }
    }

    pub async fn pending_count(&self, now_ms: u64) -> Result<u64, MessagingError> {
        let count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM mmf_messaging.outbox_messages
             WHERE source_service=$1 AND status IN ('pending','retry')
               AND (scheduled_at_ms IS NULL OR scheduled_at_ms <= $2)
               AND (next_attempt_at_ms IS NULL OR next_attempt_at_ms <= $2)
               AND (expires_at_ms IS NULL OR expires_at_ms > $2)",
        )
        .bind(&self.source_service)
        .bind(to_i64(now_ms, "now_ms")?)
        .fetch_one(&self.pool)
        .await
        .map_err(storage)?;
        u64::try_from(count).map_err(|_| MessagingError::Storage("negative outbox count".into()))
    }

    pub async fn entry(&self, message_id: &str) -> Result<Option<OutboxEntry>, MessagingError> {
        let row = sqlx::query(
            "SELECT * FROM mmf_messaging.outbox_messages
             WHERE source_service=$1 AND message_id=$2",
        )
        .bind(&self.source_service)
        .bind(message_id)
        .fetch_optional(&self.pool)
        .await
        .map_err(storage)?;
        row.as_ref().map(entry_from_row).transpose()
    }

    pub async fn dead_letters(&self, limit: usize) -> Result<Vec<DeadLetter>, MessagingError> {
        if limit == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "dead-letter limit must be greater than zero".into(),
            ));
        }
        let rows = sqlx::query(
            "SELECT message_id,message->>'message_type' AS message_type,
                    message->>'topic' AS topic,last_error,processed_at_ms,attempt_count
             FROM mmf_messaging.outbox_messages
             WHERE source_service=$1 AND status='dead_letter'
             ORDER BY processed_at_ms DESC,message_id LIMIT $2",
        )
        .bind(&self.source_service)
        .bind(i64::try_from(limit).unwrap_or(i64::MAX))
        .fetch_all(&self.pool)
        .await
        .map_err(storage)?;
        rows.iter()
            .map(|row| {
                Ok(DeadLetter {
                    message_id: row.try_get("message_id").map_err(storage)?,
                    message_type: row.try_get("message_type").map_err(storage)?,
                    topic: row.try_get("topic").map_err(storage)?,
                    reason: row.try_get("last_error").map_err(storage)?,
                    failed_at_ms: from_i64(
                        row.try_get("processed_at_ms").map_err(storage)?,
                        "processed_at_ms",
                    )?,
                    attempt_count: u32::try_from(
                        row.try_get::<i32, _>("attempt_count").map_err(storage)?,
                    )
                    .map_err(|_| MessagingError::Storage("invalid outbox attempt count".into()))?,
                })
            })
            .collect()
    }

    pub async fn replay_ids(
        &self,
        message_type: Option<&str>,
        limit: usize,
    ) -> Result<Vec<String>, MessagingError> {
        if limit == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "replay limit must be greater than zero".into(),
            ));
        }
        sqlx::query_scalar(
            "SELECT message_id FROM mmf_messaging.outbox_messages
             WHERE source_service=$1 AND ($2::text IS NULL OR message->>'message_type'=$2)
             ORDER BY created_at_ms,message_id LIMIT $3",
        )
        .bind(&self.source_service)
        .bind(message_type)
        .bind(i64::try_from(limit).unwrap_or(i64::MAX))
        .fetch_all(&self.pool)
        .await
        .map_err(storage)
    }

    pub async fn scrub_expired(&self, now_ms: u64, limit: usize) -> Result<u64, MessagingError> {
        if limit == 0 {
            return Err(MessagingError::InvalidConfiguration(
                "outbox scrub limit must be greater than zero".into(),
            ));
        }
        let now = to_i64(now_ms, "now_ms")?;
        let mut transaction = self.pool.begin().await.map_err(storage)?;
        let rows = sqlx::query(
            "SELECT message_id,message FROM mmf_messaging.outbox_messages
             WHERE source_service=$1 AND expires_at_ms IS NOT NULL AND expires_at_ms <= $2
               AND status NOT IN ('processed','skipped')
             ORDER BY expires_at_ms,message_id FOR UPDATE SKIP LOCKED LIMIT $3",
        )
        .bind(&self.source_service)
        .bind(now)
        .bind(i64::try_from(limit).unwrap_or(i64::MAX))
        .fetch_all(&mut *transaction)
        .await
        .map_err(storage)?;
        for row in &rows {
            let message_id: String = row.try_get("message_id").map_err(storage)?;
            let mut message: Message =
                serde_json::from_value(row.try_get("message").map_err(storage)?)
                    .map_err(|error| MessagingError::Serialization(error.to_string()))?;
            message.payload = serde_json::Value::Null;
            message.routing_key.clear();
            message.reply_to = None;
            message.status = MessageStatus::Skipped;
            sqlx::query(
                "UPDATE mmf_messaging.outbox_messages
                 SET message=$3,status='skipped',last_error='retention_expired',
                     lease_token=NULL,lease_expires_at_ms=NULL
                 WHERE source_service=$1 AND message_id=$2",
            )
            .bind(&self.source_service)
            .bind(message_id)
            .bind(
                serde_json::to_value(message)
                    .map_err(|error| MessagingError::Serialization(error.to_string()))?,
            )
            .execute(&mut *transaction)
            .await
            .map_err(storage)?;
        }
        transaction.commit().await.map_err(storage)?;
        u64::try_from(rows.len())
            .map_err(|_| MessagingError::Storage("outbox scrub count overflow".into()))
    }

    pub async fn cleanup(&self, before_ms: u64) -> Result<(u64, u64), MessagingError> {
        let before = to_i64(before_ms, "before_ms")?;
        let mut transaction = self.pool.begin().await.map_err(storage)?;
        let outbox = sqlx::query(
            "DELETE FROM mmf_messaging.outbox_messages
             WHERE source_service=$1 AND processed_at_ms IS NOT NULL AND processed_at_ms < $2",
        )
        .bind(&self.source_service)
        .bind(before)
        .execute(&mut *transaction)
        .await
        .map_err(storage)?
        .rows_affected();
        let inbox = sqlx::query(
            "DELETE FROM mmf_messaging.inbox_messages
             WHERE source_service=$1 AND processed_at_ms < $2",
        )
        .bind(&self.source_service)
        .bind(before)
        .execute(&mut *transaction)
        .await
        .map_err(storage)?
        .rows_affected();
        transaction.commit().await.map_err(storage)?;
        Ok((outbox, inbox))
    }

    pub async fn health(&self) -> Result<(), MessagingError> {
        let value: i32 = sqlx::query_scalar("SELECT 1")
            .fetch_one(&self.pool)
            .await
            .map_err(|error| MessagingError::BackendUnavailable(error.to_string()))?;
        if value == 1 {
            Ok(())
        } else {
            Err(MessagingError::BackendUnavailable(
                "PostgreSQL outbox health check returned an unexpected value".into(),
            ))
        }
    }
}

fn entry_from_row(row: &sqlx::postgres::PgRow) -> Result<OutboxEntry, MessagingError> {
    let mut message: Message = serde_json::from_value(row.try_get("message").map_err(storage)?)
        .map_err(|error| MessagingError::Serialization(error.to_string()))?;
    let status = parse_status(row.try_get("status").map_err(storage)?)?;
    message.status = status;
    Ok(OutboxEntry {
        message,
        partition: u32::try_from(row.try_get::<i32, _>("partition").map_err(storage)?)
            .map_err(|_| MessagingError::Storage("invalid outbox partition".into()))?,
        status,
        attempt_count: u32::try_from(row.try_get::<i32, _>("attempt_count").map_err(storage)?)
            .map_err(|_| MessagingError::Storage("invalid outbox attempt count".into()))?,
        max_attempts: u32::try_from(row.try_get::<i32, _>("max_attempts").map_err(storage)?)
            .map_err(|_| MessagingError::Storage("invalid outbox max attempts".into()))?,
        next_attempt_at_ms: optional_from_i64(
            row.try_get("next_attempt_at_ms").map_err(storage)?,
            "next_attempt_at_ms",
        )?,
        last_error: row.try_get("last_error").map_err(storage)?,
        processed_at_ms: optional_from_i64(
            row.try_get("processed_at_ms").map_err(storage)?,
            "processed_at_ms",
        )?,
        lease_token: row.try_get("lease_token").map_err(storage)?,
        lease_expires_at_ms: optional_from_i64(
            row.try_get("lease_expires_at_ms").map_err(storage)?,
            "lease_expires_at_ms",
        )?,
    })
}

fn status_name(status: MessageStatus) -> &'static str {
    match status {
        MessageStatus::Pending => "pending",
        MessageStatus::Scheduled => "scheduled",
        MessageStatus::Processing => "processing",
        MessageStatus::Processed => "processed",
        MessageStatus::Failed => "failed",
        MessageStatus::DeadLetter => "dead_letter",
        MessageStatus::Retry => "retry",
        MessageStatus::Skipped => "skipped",
    }
}

fn parse_status(value: &str) -> Result<MessageStatus, MessagingError> {
    match value {
        "pending" => Ok(MessageStatus::Pending),
        "scheduled" => Ok(MessageStatus::Scheduled),
        "processing" => Ok(MessageStatus::Processing),
        "processed" => Ok(MessageStatus::Processed),
        "failed" => Ok(MessageStatus::Failed),
        "dead_letter" => Ok(MessageStatus::DeadLetter),
        "retry" => Ok(MessageStatus::Retry),
        "skipped" => Ok(MessageStatus::Skipped),
        other => Err(MessagingError::Storage(format!(
            "invalid persisted outbox status: {other}"
        ))),
    }
}

fn require_identity(message_id: &str, lease_token: &str) -> Result<(), MessagingError> {
    if message_id.trim().is_empty() || lease_token.trim().is_empty() {
        Err(MessagingError::InvalidConfiguration(
            "outbox message ID and lease token are required".into(),
        ))
    } else {
        Ok(())
    }
}

fn require_lease_update(rows: u64, message_id: &str) -> Result<(), MessagingError> {
    if rows == 1 {
        Ok(())
    } else {
        Err(MessagingError::LeaseConflict(message_id.to_owned()))
    }
}

fn to_i64(value: u64, field: &str) -> Result<i64, MessagingError> {
    i64::try_from(value).map_err(|_| {
        MessagingError::InvalidConfiguration(format!("{field} exceeds PostgreSQL range"))
    })
}

fn optional_i64(value: Option<u64>, field: &str) -> Result<Option<i64>, MessagingError> {
    value.map(|value| to_i64(value, field)).transpose()
}

fn from_i64(value: i64, field: &str) -> Result<u64, MessagingError> {
    u64::try_from(value).map_err(|_| MessagingError::Storage(format!("negative persisted {field}")))
}

fn optional_from_i64(value: Option<i64>, field: &str) -> Result<Option<u64>, MessagingError> {
    value.map(|value| from_i64(value, field)).transpose()
}

#[allow(clippy::needless_pass_by_value)]
fn storage(error: sqlx::Error) -> MessagingError {
    MessagingError::Storage(error.to_string())
}
