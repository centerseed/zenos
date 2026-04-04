-- Migration: Add work_journal table
-- Date: 2026-04-04
-- Purpose: Operational work journal for agents — record session/flow summaries,
--          read at session start to restore context without user re-briefing.

CREATE TABLE IF NOT EXISTS zenos.work_journal (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id  TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    project     TEXT,
    flow_type   TEXT,
    summary     TEXT        NOT NULL CHECK (length(trim(summary)) > 0 AND length(summary) <= 500),
    tags        TEXT[]      NOT NULL DEFAULT '{}',
    is_summary  BOOLEAN     NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_work_journal_partner_created
    ON zenos.work_journal (partner_id, created_at DESC);
