-- =====================================================================
-- Wave 9 Phase A: L3-Action MTI Schema Preflight (additive only)
-- =====================================================================
-- Task: 6a49007e (A02+A04+A05 merged)
-- Plan: PLAN-ontology-grand-refactor-wave9-migration
-- SPEC: docs/specs/SPEC-ontology-architecture.md §9 (lines 132-538)
-- Decisions locked in A01 (docs/runbooks/wave9-preflight-findings.md):
--   - task_handoff_events: independent table (SPEC §9.6)
--   - milestone: independent entity_l3_milestone subclass (C04)
-- Cross-plan coord: PLAN-data-model-consolidation S03 only introduces
--   EntityStatus.archived + preflight; does NOT create entities_base.
--   This migration is the SSOT for entities_base. Checked 2026-04-23.
-- fix-15 (Wave 9 Phase B prime review round 4):
--   entities_base uses composite PK (partner_id, id) to enforce
--   partner-scoped isolation. parent_id FK is composite to prevent
--   cross-partner pollution. All subclass tables use composite PKs and
--   composite FKs referencing entities_base(partner_id, id).
--   task_handoff_events likewise uses a composite FK.
-- Rollback: see SQL comment block at file end.
-- =====================================================================

-- =====================================================================
-- 1. entities_base  (SPEC §9, lines 132-152)
-- =====================================================================
-- Base table for all entity types under MTI.
-- Runtime today still uses zenos.entities; this table is additive-only.
-- No FK back to zenos.entities — new table is standalone.
--
-- fix-15: composite PK (partner_id, id) enforces partner-scoped isolation.
-- parent_id FK is composite (partner_id, parent_id) to prevent cross-partner
-- parent references. Level-1 entities must have no parent (CHECK constraint).
-- id itself is NOT the PK — the composite (partner_id, id) is.
-- =====================================================================
CREATE TABLE zenos.entities_base (
    id                      text NOT NULL,
    partner_id              text NOT NULL REFERENCES zenos.partners(id),
    name                    text NOT NULL,
    type_label              text NOT NULL,
    level                   integer NOT NULL CHECK (level IN (1, 2, 3)),
    parent_id               text,
    status                  text NOT NULL,
    visibility              text NOT NULL DEFAULT 'public',
    visible_to_roles        text[] NOT NULL DEFAULT '{}',
    visible_to_members      text[] NOT NULL DEFAULT '{}',
    visible_to_departments  text[] NOT NULL DEFAULT '{}',
    owner                   text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (partner_id, id),
    FOREIGN KEY (partner_id, parent_id)
        REFERENCES zenos.entities_base (partner_id, id) ON DELETE SET NULL (parent_id),
    CHECK (level != 1 OR parent_id IS NULL)   -- L1 must have no parent
);

-- =====================================================================
-- 2. entity_l3_milestone  (SPEC §9.2, lines 418-430)
-- =====================================================================
-- Subclass for milestones (absorbs legacy goal entity type).
-- fix-15: composite PK (partner_id, entity_id) + composite FK referencing
--   entities_base(partner_id, id) to enforce partner-scoped isolation.
-- =====================================================================
CREATE TABLE zenos.entity_l3_milestone (
    partner_id                  text NOT NULL,
    entity_id                   text NOT NULL,
    description                 text NOT NULL,
    task_status                 text NOT NULL CHECK (task_status IN ('planned', 'active', 'completed', 'cancelled')),
    assignee                    text,
    dispatcher                  text NOT NULL,
    acceptance_criteria_json    jsonb NOT NULL DEFAULT '[]',
    priority                    text NOT NULL DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    result                      text,
    target_date                 date,
    completion_criteria         text,

    PRIMARY KEY (partner_id, entity_id),
    FOREIGN KEY (partner_id, entity_id)
        REFERENCES zenos.entities_base (partner_id, id) ON DELETE CASCADE
);

-- =====================================================================
-- 3. entity_l3_plan  (SPEC §9.3, lines 443-455)
-- =====================================================================
-- Subclass for task groups / plans.
-- fix-15: composite PK (partner_id, entity_id) + composite FK.
-- =====================================================================
CREATE TABLE zenos.entity_l3_plan (
    partner_id                  text NOT NULL,
    entity_id                   text NOT NULL,
    description                 text NOT NULL,
    task_status                 text NOT NULL CHECK (task_status IN ('draft', 'active', 'completed', 'cancelled')),
    assignee                    text,
    dispatcher                  text NOT NULL,
    acceptance_criteria_json    jsonb NOT NULL DEFAULT '[]',
    priority                    text NOT NULL DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    result                      text,
    goal_statement              text NOT NULL,
    entry_criteria              text NOT NULL,
    exit_criteria               text NOT NULL,

    PRIMARY KEY (partner_id, entity_id),
    FOREIGN KEY (partner_id, entity_id)
        REFERENCES zenos.entities_base (partner_id, id) ON DELETE CASCADE
);

-- =====================================================================
-- 4. entity_l3_task  (SPEC §9.4, lines 470-485)
-- =====================================================================
-- Subclass for executable work items.
-- CHECK constraints are NOT VALID: built but not enforced until Phase D/E VALIDATE.
-- fix-15: composite PK (partner_id, entity_id) + composite FK.
-- =====================================================================
CREATE TABLE zenos.entity_l3_task (
    partner_id                  text NOT NULL,
    entity_id                   text NOT NULL,
    description                 text NOT NULL,
    task_status                 text NOT NULL CHECK (task_status IN ('todo', 'in_progress', 'review', 'done', 'cancelled')),
    assignee                    text,
    dispatcher                  text NOT NULL,
    acceptance_criteria_json    jsonb NOT NULL DEFAULT '[]',
    priority                    text NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    result                      text,
    plan_order                  integer,
    depends_on_json             jsonb NOT NULL DEFAULT '[]',
    blocked_reason              text,
    due_date                    date,

    PRIMARY KEY (partner_id, entity_id),
    FOREIGN KEY (partner_id, entity_id)
        REFERENCES zenos.entities_base (partner_id, id) ON DELETE CASCADE
);

ALTER TABLE zenos.entity_l3_task
    ADD CONSTRAINT entity_l3_task_review_needs_result
    CHECK (task_status != 'review' OR result IS NOT NULL) NOT VALID;

-- =====================================================================
-- 5. entity_l3_subtask  (SPEC §9.5, lines 499-514)
-- =====================================================================
-- Subclass for agent-dispatched sub-units of a task.
-- fix-13: inline CHECK constraints on task_status and priority to match
-- entity_l3_task (no additional cross-column CHECK so inline is cleaner).
-- fix-15: composite PK (partner_id, entity_id) + composite FK.
-- =====================================================================
CREATE TABLE zenos.entity_l3_subtask (
    partner_id                  text NOT NULL,
    entity_id                   text NOT NULL,
    description                 text NOT NULL,
    task_status                 text NOT NULL CHECK (task_status IN ('todo', 'in_progress', 'review', 'done', 'cancelled')),
    assignee                    text,
    dispatcher                  text NOT NULL,
    acceptance_criteria_json    jsonb NOT NULL DEFAULT '[]',
    priority                    text NOT NULL DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    result                      text,
    plan_order                  integer,
    depends_on_json             jsonb NOT NULL DEFAULT '[]',
    blocked_reason              text,
    due_date                    date,
    dispatched_by_agent         text NOT NULL,
    auto_created                boolean NOT NULL DEFAULT true,

    PRIMARY KEY (partner_id, entity_id),
    FOREIGN KEY (partner_id, entity_id)
        REFERENCES zenos.entities_base (partner_id, id) ON DELETE CASCADE
);

-- =====================================================================
-- 6. task_handoff_events  (SPEC §9.6, lines 527-538)
-- =====================================================================
-- Append-only audit log for task dispatcher handoffs.
-- Replaces zenos.tasks.handoff_events JSONB column in Phase C+.
-- No FK back to zenos.tasks — parallel table during migration window.
-- fix-15: task_entity_id FK is composite (partner_id, task_entity_id)
--   referencing entities_base(partner_id, id) to enforce partner-scoped
--   isolation. partner_id column added to the table.
-- =====================================================================
CREATE TABLE zenos.task_handoff_events (
    id              bigserial PRIMARY KEY,
    partner_id      text NOT NULL REFERENCES zenos.partners(id),
    task_entity_id  text NOT NULL,
    from_dispatcher text,
    to_dispatcher   text NOT NULL,
    reason          text NOT NULL,
    notes           text,
    output_ref      text,
    created_at      timestamptz NOT NULL DEFAULT now(),

    FOREIGN KEY (partner_id, task_entity_id)
        REFERENCES zenos.entities_base (partner_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_handoff_events_task
    ON zenos.task_handoff_events (task_entity_id, created_at);

-- =====================================================================
-- Rollback (manual DOWN migration)
-- =====================================================================
-- Subclass tables must be dropped before entities_base (FK dependency order).
-- DROP TABLE IF EXISTS zenos.task_handoff_events CASCADE;
-- DROP TABLE IF EXISTS zenos.entity_l3_subtask CASCADE;
-- DROP TABLE IF EXISTS zenos.entity_l3_task CASCADE;
-- DROP TABLE IF EXISTS zenos.entity_l3_plan CASCADE;
-- DROP TABLE IF EXISTS zenos.entity_l3_milestone CASCADE;
-- DROP TABLE IF EXISTS zenos.entities_base CASCADE;
