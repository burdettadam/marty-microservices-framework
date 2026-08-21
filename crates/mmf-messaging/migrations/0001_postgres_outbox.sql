CREATE SCHEMA IF NOT EXISTS mmf_messaging;

CREATE TABLE IF NOT EXISTS mmf_messaging.outbox_messages (
    message_id TEXT PRIMARY KEY,
    source_service TEXT NOT NULL,
    tenant_id TEXT,
    partition INTEGER NOT NULL CHECK (partition >= 0),
    priority SMALLINT NOT NULL,
    message JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','scheduled','processing','processed','failed','dead_letter','retry','skipped')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
    next_attempt_at_ms BIGINT,
    last_error TEXT,
    processed_at_ms BIGINT,
    lease_token TEXT,
    lease_expires_at_ms BIGINT,
    created_at_ms BIGINT NOT NULL,
    scheduled_at_ms BIGINT,
    expires_at_ms BIGINT
);

CREATE INDEX IF NOT EXISTS ix_mmf_outbox_due
    ON mmf_messaging.outbox_messages
    (source_service, status, next_attempt_at_ms, scheduled_at_ms, priority DESC, created_at_ms);
CREATE INDEX IF NOT EXISTS ix_mmf_outbox_lease
    ON mmf_messaging.outbox_messages
    (source_service, status, lease_expires_at_ms);
CREATE INDEX IF NOT EXISTS ix_mmf_outbox_tenant
    ON mmf_messaging.outbox_messages
    (source_service, tenant_id, created_at_ms DESC);

CREATE TABLE IF NOT EXISTS mmf_messaging.inbox_messages (
    source_service TEXT NOT NULL,
    message_id TEXT NOT NULL,
    processed_at_ms BIGINT NOT NULL,
    PRIMARY KEY (source_service, message_id)
);

CREATE INDEX IF NOT EXISTS ix_mmf_inbox_retention
    ON mmf_messaging.inbox_messages (source_service, processed_at_ms);
