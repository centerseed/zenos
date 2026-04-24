-- =====================================================================
-- Wave 9 Phase D03a: Legacy L3-Action shadow tables
-- =====================================================================
-- These tables preserve structured triage state for rows that cannot be
-- parent_id-backfilled or whose existing chain is invalid during Phase D.
-- They are intentionally additive and are dropped in Phase F07.
-- =====================================================================

CREATE TABLE IF NOT EXISTS zenos.legacy_orphan_tasks (
    task_id             text NOT NULL,
    partner_id          text NOT NULL REFERENCES zenos.partners(id) ON DELETE CASCADE,
    reason              text NOT NULL,
    detected_at         timestamptz NOT NULL DEFAULT now(),
    resolved_at         timestamptz,
    resolver_partner_id text,
    manual_parent_id    text,

    PRIMARY KEY (partner_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_legacy_orphan_tasks_unresolved
    ON zenos.legacy_orphan_tasks(partner_id, detected_at)
    WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS zenos.legacy_parent_chain_warnings (
    task_id             text NOT NULL,
    partner_id          text NOT NULL REFERENCES zenos.partners(id) ON DELETE CASCADE,
    chain_snapshot_json jsonb NOT NULL,
    detected_at         timestamptz NOT NULL DEFAULT now(),
    triaged_at          timestamptz,

    PRIMARY KEY (partner_id, task_id)
);

CREATE INDEX IF NOT EXISTS idx_legacy_parent_chain_warnings_untriaged
    ON zenos.legacy_parent_chain_warnings(partner_id, detected_at)
    WHERE triaged_at IS NULL;

-- Rollback:
-- DROP TABLE IF EXISTS zenos.legacy_parent_chain_warnings;
-- DROP TABLE IF EXISTS zenos.legacy_orphan_tasks;
