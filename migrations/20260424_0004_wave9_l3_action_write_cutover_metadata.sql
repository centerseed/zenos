-- =====================================================================
-- Wave 9 Phase E02: L3-Action write-cutover metadata
-- =====================================================================
-- Purpose:
--   Allow runtime mutations to stop writing legacy zenos.tasks / zenos.plans
--   rows while preserving the external MCP contract on the L3 read path.
--
--   Before this migration, L3 read queries still LEFT JOIN legacy tables for
--   metadata such as created_by, source_metadata, project, product_id, and
--   attachments. E02 requires these fields to live on the L3 subclass rows.
--
-- Safety:
--   Additive columns first, then backfill from legacy rows. Existing L3 rows
--   keep serving through COALESCE during the deployment window.
-- =====================================================================

-- 1) Task/subtask contract metadata formerly sourced from zenos.tasks.
ALTER TABLE zenos.entity_l3_task
    ADD COLUMN IF NOT EXISTS priority_reason text,
    ADD COLUMN IF NOT EXISTS assignee_role_id text,
    ADD COLUMN IF NOT EXISTS created_by text,
    ADD COLUMN IF NOT EXISTS updated_by text,
    ADD COLUMN IF NOT EXISTS linked_protocol text,
    ADD COLUMN IF NOT EXISTS linked_blindspot text,
    ADD COLUMN IF NOT EXISTS source_type text,
    ADD COLUMN IF NOT EXISTS source_metadata_json jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS context_summary text,
    ADD COLUMN IF NOT EXISTS completed_by text,
    ADD COLUMN IF NOT EXISTS confirmed_by_creator boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS rejection_reason text,
    ADD COLUMN IF NOT EXISTS project text,
    ADD COLUMN IF NOT EXISTS product_id text,
    ADD COLUMN IF NOT EXISTS attachments jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS completed_at timestamptz;

ALTER TABLE zenos.entity_l3_subtask
    ADD COLUMN IF NOT EXISTS priority_reason text,
    ADD COLUMN IF NOT EXISTS assignee_role_id text,
    ADD COLUMN IF NOT EXISTS created_by text,
    ADD COLUMN IF NOT EXISTS updated_by text,
    ADD COLUMN IF NOT EXISTS linked_protocol text,
    ADD COLUMN IF NOT EXISTS linked_blindspot text,
    ADD COLUMN IF NOT EXISTS source_type text,
    ADD COLUMN IF NOT EXISTS source_metadata_json jsonb NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS context_summary text,
    ADD COLUMN IF NOT EXISTS completed_by text,
    ADD COLUMN IF NOT EXISTS confirmed_by_creator boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS rejection_reason text,
    ADD COLUMN IF NOT EXISTS project text,
    ADD COLUMN IF NOT EXISTS product_id text,
    ADD COLUMN IF NOT EXISTS attachments jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS completed_at timestamptz;

UPDATE zenos.entity_l3_task l3
SET priority_reason = t.priority_reason,
    assignee_role_id = t.assignee_role_id,
    created_by = t.created_by,
    updated_by = t.updated_by,
    linked_protocol = t.linked_protocol,
    linked_blindspot = t.linked_blindspot,
    source_type = t.source_type,
    source_metadata_json = COALESCE(t.source_metadata_json, '{}'),
    context_summary = t.context_summary,
    completed_by = t.completed_by,
    confirmed_by_creator = COALESCE(t.confirmed_by_creator, false),
    rejection_reason = t.rejection_reason,
    project = t.project,
    product_id = t.product_id,
    attachments = COALESCE(t.attachments, '[]'),
    completed_at = t.completed_at
FROM zenos.tasks t
WHERE l3.partner_id = t.partner_id
  AND l3.entity_id = t.id;

UPDATE zenos.entity_l3_subtask l3
SET priority_reason = t.priority_reason,
    assignee_role_id = t.assignee_role_id,
    created_by = t.created_by,
    updated_by = t.updated_by,
    linked_protocol = t.linked_protocol,
    linked_blindspot = t.linked_blindspot,
    source_type = t.source_type,
    source_metadata_json = COALESCE(t.source_metadata_json, '{}'),
    context_summary = t.context_summary,
    completed_by = t.completed_by,
    confirmed_by_creator = COALESCE(t.confirmed_by_creator, false),
    rejection_reason = t.rejection_reason,
    project = t.project,
    product_id = t.product_id,
    attachments = COALESCE(t.attachments, '[]'),
    completed_at = t.completed_at
FROM zenos.tasks t
WHERE l3.partner_id = t.partner_id
  AND l3.entity_id = t.id;

-- 2) Plan contract metadata formerly sourced from zenos.plans.
ALTER TABLE zenos.entity_l3_plan
    ADD COLUMN IF NOT EXISTS created_by text,
    ADD COLUMN IF NOT EXISTS updated_by text,
    ADD COLUMN IF NOT EXISTS project text,
    ADD COLUMN IF NOT EXISTS product_id text;

UPDATE zenos.entity_l3_plan l3
SET created_by = p.created_by,
    updated_by = p.updated_by,
    project = p.project,
    product_id = p.product_id
FROM zenos.plans p
WHERE l3.partner_id = p.partner_id
  AND l3.entity_id = p.id;

-- 3) Relationships must accept L3-Action sources. The old relationship table
-- referenced zenos.entities, which rejects entity_l3_task rows. Wave 9's
-- canonical relationship graph references entities_base.
ALTER TABLE zenos.relationships
    DROP CONSTRAINT IF EXISTS fk_relationships_source,
    DROP CONSTRAINT IF EXISTS fk_relationships_target;

ALTER TABLE zenos.relationships
    ADD CONSTRAINT fk_relationships_source_base
        FOREIGN KEY (partner_id, source_entity_id)
        REFERENCES zenos.entities_base(partner_id, id)
        ON DELETE CASCADE
        NOT VALID,
    ADD CONSTRAINT fk_relationships_target_base
        FOREIGN KEY (partner_id, target_entity_id)
        REFERENCES zenos.entities_base(partner_id, id)
        ON DELETE CASCADE
        NOT VALID;

ALTER TABLE zenos.relationships VALIDATE CONSTRAINT fk_relationships_source_base;
ALTER TABLE zenos.relationships VALIDATE CONSTRAINT fk_relationships_target_base;

-- Rollback:
--   1. Recreate fk_relationships_source/target against zenos.entities only if
--      all relationship rows point to legacy zenos.entities rows.
--   2. Drop the metadata columns after confirming L3 write-only is disabled.
