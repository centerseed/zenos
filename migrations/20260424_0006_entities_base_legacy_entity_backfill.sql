-- =====================================================================
-- DF-20260424-4: legacy entity rows -> entities_base backfill
-- =====================================================================
-- Purpose:
--   relationships now reference zenos.entities_base. Runtime writes mirror new
--   Entity rows into entities_base, but existing product/module/document/etc.
--   rows may predate that mirror and would still fail relationship FK checks.
--
-- Safety:
--   Additive and idempotent. Goal entities are excluded because Wave 9 maps
--   legacy goal rows through entity_l3_milestone with type_label='milestone'.
-- =====================================================================

INSERT INTO zenos.entities_base (
    id, partner_id, name, type_label, level, parent_id, status,
    visibility, visible_to_roles, visible_to_members,
    visible_to_departments, owner, created_at, updated_at
)
SELECT
    e.id,
    e.partner_id,
    e.name,
    e.type,
    COALESCE(
        e.level,
        CASE e.type
            WHEN 'product' THEN 1
            WHEN 'company' THEN 1
            WHEN 'person' THEN 1
            WHEN 'deal' THEN 1
            WHEN 'module' THEN 2
            WHEN 'document' THEN 3
            WHEN 'role' THEN 3
            WHEN 'project' THEN 3
            ELSE 3
        END
    ) AS level,
    CASE
        WHEN COALESCE(
            e.level,
            CASE e.type
                WHEN 'product' THEN 1
                WHEN 'company' THEN 1
                WHEN 'person' THEN 1
                WHEN 'deal' THEN 1
                WHEN 'module' THEN 2
                WHEN 'document' THEN 3
                WHEN 'role' THEN 3
                WHEN 'project' THEN 3
                ELSE 3
            END
        ) = 1 THEN NULL
        ELSE e.parent_id
    END AS parent_id,
    e.status,
    COALESCE(e.visibility, 'public'),
    COALESCE(e.visible_to_roles, '{}'::text[]),
    COALESCE(e.visible_to_members, '{}'::text[]),
    COALESCE(e.visible_to_departments, '{}'::text[]),
    e.owner,
    COALESCE(e.created_at, now()),
    COALESCE(e.updated_at, now())
FROM zenos.entities e
WHERE e.type <> 'goal'
ON CONFLICT (partner_id, id) DO UPDATE SET
    name=EXCLUDED.name,
    type_label=EXCLUDED.type_label,
    level=EXCLUDED.level,
    parent_id=EXCLUDED.parent_id,
    status=EXCLUDED.status,
    visibility=EXCLUDED.visibility,
    visible_to_roles=EXCLUDED.visible_to_roles,
    visible_to_members=EXCLUDED.visible_to_members,
    visible_to_departments=EXCLUDED.visible_to_departments,
    owner=EXCLUDED.owner,
    updated_at=EXCLUDED.updated_at;

-- Rollback:
--   No destructive rollback. This migration only mirrors canonical legacy
--   entity metadata into the additive entities_base table.
