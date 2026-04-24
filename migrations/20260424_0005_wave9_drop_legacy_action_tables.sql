-- Wave 9 Phase F: drop legacy Action tables after owner-approved early cleanup.
--
-- Preconditions:
-- - entity_l3_task/entity_l3_subtask fully cover zenos.tasks
-- - entity_l3_plan fully covers zenos.plans
-- - task_blockers has no rows
-- - legacy orphan/warning shadow tables have no rows
-- - task handoff events are copied into zenos.task_handoff_events before drop

BEGIN;

DO $$
DECLARE
    missing_tasks integer;
    missing_plans integer;
    blocker_rows integer;
    orphan_rows integer;
    warning_rows integer;
BEGIN
    SELECT count(*) INTO missing_tasks
    FROM zenos.tasks t
    WHERE NOT EXISTS (
        SELECT 1
        FROM zenos.entity_l3_task l3
        WHERE l3.partner_id = t.partner_id AND l3.entity_id = t.id
    )
    AND NOT EXISTS (
        SELECT 1
        FROM zenos.entity_l3_subtask l3
        WHERE l3.partner_id = t.partner_id AND l3.entity_id = t.id
    );

    IF missing_tasks > 0 THEN
        RAISE EXCEPTION 'Wave 9 Phase F blocked: % legacy tasks are missing L3 rows', missing_tasks;
    END IF;

    SELECT count(*) INTO missing_plans
    FROM zenos.plans p
    WHERE NOT EXISTS (
        SELECT 1
        FROM zenos.entity_l3_plan l3
        WHERE l3.partner_id = p.partner_id AND l3.entity_id = p.id
    );

    IF missing_plans > 0 THEN
        RAISE EXCEPTION 'Wave 9 Phase F blocked: % legacy plans are missing L3 rows', missing_plans;
    END IF;

    SELECT count(*) INTO blocker_rows FROM zenos.task_blockers;
    IF blocker_rows > 0 THEN
        RAISE EXCEPTION 'Wave 9 Phase F blocked: task_blockers still has % rows', blocker_rows;
    END IF;

    SELECT count(*) INTO orphan_rows FROM zenos.legacy_orphan_tasks;
    IF orphan_rows > 0 THEN
        RAISE EXCEPTION 'Wave 9 Phase F blocked: legacy_orphan_tasks still has % rows', orphan_rows;
    END IF;

    SELECT count(*) INTO warning_rows FROM zenos.legacy_parent_chain_warnings;
    IF warning_rows > 0 THEN
        RAISE EXCEPTION 'Wave 9 Phase F blocked: legacy_parent_chain_warnings still has % rows', warning_rows;
    END IF;
END $$;

INSERT INTO zenos.task_handoff_events (
    partner_id,
    task_entity_id,
    from_dispatcher,
    to_dispatcher,
    reason,
    notes,
    output_ref,
    created_at
)
SELECT
    t.partner_id,
    t.id,
    event.value->>'from_dispatcher',
    COALESCE(NULLIF(event.value->>'to_dispatcher', ''), 'human'),
    COALESCE(event.value->>'reason', ''),
    event.value->>'notes',
    event.value->>'output_ref',
    COALESCE((event.value->>'at')::timestamptz, t.updated_at, t.created_at, now())
FROM zenos.tasks t
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(t.handoff_events, '[]'::jsonb)) AS event(value)
WHERE NOT EXISTS (
    SELECT 1
    FROM zenos.task_handoff_events existing
    WHERE existing.partner_id = t.partner_id
      AND existing.task_entity_id = t.id
      AND existing.created_at = COALESCE((event.value->>'at')::timestamptz, t.updated_at, t.created_at, now())
      AND existing.to_dispatcher = COALESCE(NULLIF(event.value->>'to_dispatcher', ''), 'human')
      AND existing.reason = COALESCE(event.value->>'reason', '')
);

DROP TABLE IF EXISTS zenos.task_entities;
DROP TABLE IF EXISTS zenos.task_blockers;
DROP TABLE IF EXISTS zenos.tasks;
DROP TABLE IF EXISTS zenos.plans;
DROP TABLE IF EXISTS zenos.legacy_orphan_tasks;
DROP TABLE IF EXISTS zenos.legacy_parent_chain_warnings;

COMMIT;
