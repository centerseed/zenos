-- Migration: audit_events table
-- Purpose: Persist governance audit logs for Dashboard query support

CREATE TABLE IF NOT EXISTS zenos.audit_events (
    event_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id    TEXT        NOT NULL,
    actor_id      TEXT        NOT NULL,
    actor_type    TEXT        NOT NULL DEFAULT 'partner',
    operation     TEXT        NOT NULL,
    resource_type TEXT        NOT NULL,
    resource_id   TEXT,
    changes_json  JSONB,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_events_partner_id_idx ON zenos.audit_events (partner_id);
CREATE INDEX IF NOT EXISTS audit_events_timestamp_idx  ON zenos.audit_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS audit_events_operation_idx  ON zenos.audit_events (partner_id, operation);

-- Immutable: no delete or update
REVOKE DELETE ON zenos.audit_events FROM PUBLIC;
REVOKE UPDATE ON zenos.audit_events FROM PUBLIC;
