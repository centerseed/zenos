-- =====================================================================
-- Wave 9 Phase D: upgrade empty L3-Action preflight tables to composite FK schema
-- =====================================================================
-- Context:
--   Production had an earlier 0004 table shape without partner_id on the
--   entity_l3_* subclass tables. Because 0004 used CREATE TABLE, rerunning the
--   later IF NOT EXISTS DDL did not mutate those existing empty tables.
--
-- Safety:
--   This migration aborts unless every L3-Action table is empty. It must never
--   drop rows. After the guard passes, tables are recreated with the composite
--   partner-scoped schema expected by Wave 9 Phase C/D code.
-- =====================================================================

DO $$
DECLARE
    total_rows bigint;
BEGIN
    SELECT
        (SELECT count(*) FROM zenos.entities_base)
      + (SELECT count(*) FROM zenos.entity_l3_milestone)
      + (SELECT count(*) FROM zenos.entity_l3_plan)
      + (SELECT count(*) FROM zenos.entity_l3_task)
      + (SELECT count(*) FROM zenos.entity_l3_subtask)
      + (SELECT count(*) FROM zenos.task_handoff_events)
    INTO total_rows;

    IF total_rows != 0 THEN
        RAISE EXCEPTION 'Refusing to recreate L3-Action tables: % existing row(s)', total_rows;
    END IF;
END $$;

DROP TABLE IF EXISTS zenos.task_handoff_events CASCADE;
DROP TABLE IF EXISTS zenos.entity_l3_subtask CASCADE;
DROP TABLE IF EXISTS zenos.entity_l3_task CASCADE;
DROP TABLE IF EXISTS zenos.entity_l3_plan CASCADE;
DROP TABLE IF EXISTS zenos.entity_l3_milestone CASCADE;
DROP TABLE IF EXISTS zenos.entities_base CASCADE;

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
    CHECK (level != 1 OR parent_id IS NULL)
);

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

-- Rollback:
-- There is no data-preserving down migration for this corrective DDL.
-- Restore from DB backup if rollback is required.
