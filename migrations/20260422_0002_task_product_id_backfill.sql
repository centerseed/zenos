BEGIN;

-- ADR-044 / PLAN-task-ownership-ssot / S02
-- Backfill tasks.product_id / plans.product_id before NOT NULL finalization.
-- Resolution order:
--   1. task_entities attached product entity
--   2. legacy project string -> product entity.name
--   3. partner.default_project -> product entity.name
--   4. partner first product entity fallback + governance review audit marker

SET search_path TO zenos, public;

-- Step 2a: task_entities product link wins.
WITH product_from_links AS (
  SELECT target.partner_id, target.task_id, MIN(te.entity_id) AS product_id
  FROM (
    SELECT t.partner_id, t.id AS task_id
    FROM zenos.tasks t
    LEFT JOIN zenos.entities current_product
      ON current_product.partner_id = t.partner_id
     AND current_product.id = t.product_id
     AND current_product.type = 'product'
    WHERE t.product_id IS NULL OR current_product.id IS NULL
  ) target
  JOIN zenos.task_entities te
    ON te.partner_id = target.partner_id
   AND te.task_id = target.task_id
  JOIN zenos.entities e
    ON e.partner_id = te.partner_id
   AND e.id = te.entity_id
  WHERE e.type = 'product'
  GROUP BY target.partner_id, target.task_id
)
UPDATE zenos.tasks t
SET product_id = pfl.product_id
FROM product_from_links pfl
WHERE t.partner_id = pfl.partner_id
  AND t.id = pfl.task_id
  AND t.product_id IS DISTINCT FROM pfl.product_id;

-- Step 2b: legacy task.project string -> product entity.name.
WITH resolved_from_project_name AS (
  SELECT DISTINCT ON (target.partner_id, target.task_id)
         target.partner_id,
         target.task_id,
         e.id AS product_id
  FROM (
    SELECT t.partner_id, t.id AS task_id, t.project
    FROM zenos.tasks t
    LEFT JOIN zenos.entities current_product
      ON current_product.partner_id = t.partner_id
     AND current_product.id = t.product_id
     AND current_product.type = 'product'
    WHERE t.product_id IS NULL OR current_product.id IS NULL
  ) target
  JOIN zenos.entities e
    ON e.partner_id = target.partner_id
   AND e.type = 'product'
   AND LOWER(BTRIM(e.name)) = LOWER(BTRIM(COALESCE(target.project, '')))
  ORDER BY target.partner_id, target.task_id, e.created_at NULLS LAST, e.id
)
UPDATE zenos.tasks t
SET product_id = src.product_id
FROM resolved_from_project_name src
WHERE t.partner_id = src.partner_id
  AND t.id = src.task_id
  AND t.product_id IS DISTINCT FROM src.product_id;

-- Step 2c: partner.default_project string -> product entity.name.
WITH product_from_partner_default AS (
  SELECT DISTINCT ON (target.partner_id, target.task_id)
         target.partner_id,
         target.task_id,
         e.id AS product_id
  FROM (
    SELECT t.partner_id, t.id AS task_id
    FROM zenos.tasks t
    LEFT JOIN zenos.entities current_product
      ON current_product.partner_id = t.partner_id
     AND current_product.id = t.product_id
     AND current_product.type = 'product'
    WHERE t.product_id IS NULL OR current_product.id IS NULL
  ) target
  JOIN zenos.partners p
    ON p.id = target.partner_id
  JOIN zenos.entities e
    ON e.partner_id = target.partner_id
   AND e.type = 'product'
   AND LOWER(BTRIM(e.name)) = LOWER(BTRIM(COALESCE(p.default_project, '')))
  ORDER BY target.partner_id, target.task_id, e.created_at NULLS LAST, e.id
)
UPDATE zenos.tasks t
SET product_id = src.product_id
FROM product_from_partner_default src
WHERE t.partner_id = src.partner_id
  AND t.id = src.task_id
  AND t.product_id IS DISTINCT FROM src.product_id;

-- Step 2d: fallback to first product entity per partner and mark for governance review.
WITH first_product_per_partner AS (
  SELECT DISTINCT ON (e.partner_id)
         e.partner_id,
         e.id AS product_id
  FROM zenos.entities e
  WHERE e.type = 'product'
  ORDER BY e.partner_id, e.created_at NULLS LAST, e.id
),
fallback_targets AS (
  SELECT t.partner_id, t.id AS task_id, fp.product_id
  FROM zenos.tasks t
  LEFT JOIN zenos.entities current_product
    ON current_product.partner_id = t.partner_id
   AND current_product.id = t.product_id
   AND current_product.type = 'product'
  JOIN first_product_per_partner fp
    ON fp.partner_id = t.partner_id
  WHERE t.product_id IS NULL OR current_product.id IS NULL
)
UPDATE zenos.tasks t
SET product_id = ft.product_id,
    source_metadata_json = jsonb_set(
      COALESCE(t.source_metadata_json, '{}'::jsonb),
      '{governance,review_tags}',
      COALESCE(t.source_metadata_json->'governance'->'review_tags', '[]'::jsonb) || '["governance:review_product_assignment"]'::jsonb,
      true
    )
FROM fallback_targets ft
WHERE t.partner_id = ft.partner_id
  AND t.id = ft.task_id
  AND t.product_id IS DISTINCT FROM ft.product_id;

INSERT INTO zenos.audit_events (
  partner_id,
  actor_id,
  actor_type,
  operation,
  resource_type,
  resource_id,
  changes_json
)
SELECT
  ft.partner_id,
  'migration:20260422_0002_task_product_id_backfill',
  'system',
  'governance.review_product_assignment',
  'task',
  ft.task_id,
  jsonb_build_object(
    'tag', 'governance:review_product_assignment',
    'resolved_product_id', ft.product_id,
    'resolution', 'fallback:first_product_entity'
  )
FROM (
  SELECT t.partner_id, t.id AS task_id, t.product_id
  FROM zenos.tasks t
  WHERE t.source_metadata_json::text LIKE '%governance:review_product_assignment%'
) ft;

-- Plans: prefer product_id already assigned on child tasks.
WITH product_from_plan_tasks AS (
  SELECT t.partner_id, t.plan_id, MIN(t.product_id) AS product_id
  FROM zenos.tasks t
  WHERE t.plan_id IS NOT NULL
    AND t.product_id IS NOT NULL
  GROUP BY t.partner_id, t.plan_id
)
UPDATE zenos.plans p
SET product_id = src.product_id
FROM product_from_plan_tasks src
WHERE p.partner_id = src.partner_id
  AND p.id = src.plan_id
  AND p.product_id IS DISTINCT FROM src.product_id;

WITH plan_project_name_match AS (
  SELECT DISTINCT ON (p.partner_id, p.id)
         p.partner_id,
         p.id AS plan_id,
         e.id AS product_id
  FROM zenos.plans p
  JOIN zenos.entities e
    ON e.partner_id = p.partner_id
   AND e.type = 'product'
   AND LOWER(BTRIM(e.name)) = LOWER(BTRIM(COALESCE(p.project, '')))
  LEFT JOIN zenos.entities current_product
    ON current_product.partner_id = p.partner_id
   AND current_product.id = p.product_id
   AND current_product.type = 'product'
  WHERE p.product_id IS NULL OR current_product.id IS NULL
  ORDER BY p.partner_id, p.id, e.created_at NULLS LAST, e.id
)
UPDATE zenos.plans p
SET product_id = src.product_id
FROM plan_project_name_match src
WHERE p.partner_id = src.partner_id
  AND p.id = src.plan_id
  AND p.product_id IS DISTINCT FROM src.product_id;

WITH plan_partner_default_match AS (
  SELECT DISTINCT ON (p.partner_id, p.id)
         p.partner_id,
         p.id AS plan_id,
         e.id AS product_id
  FROM zenos.plans p
  JOIN zenos.partners partner
    ON partner.id = p.partner_id
  JOIN zenos.entities e
    ON e.partner_id = p.partner_id
   AND e.type = 'product'
   AND LOWER(BTRIM(e.name)) = LOWER(BTRIM(COALESCE(partner.default_project, '')))
  LEFT JOIN zenos.entities current_product
    ON current_product.partner_id = p.partner_id
   AND current_product.id = p.product_id
   AND current_product.type = 'product'
  WHERE p.product_id IS NULL OR current_product.id IS NULL
  ORDER BY p.partner_id, p.id, e.created_at NULLS LAST, e.id
)
UPDATE zenos.plans p
SET product_id = src.product_id
FROM plan_partner_default_match src
WHERE p.partner_id = src.partner_id
  AND p.id = src.plan_id
  AND p.product_id IS DISTINCT FROM src.product_id;

WITH first_product_per_partner AS (
  SELECT DISTINCT ON (e.partner_id)
         e.partner_id,
         e.id AS product_id
  FROM zenos.entities e
  WHERE e.type = 'product'
  ORDER BY e.partner_id, e.created_at NULLS LAST, e.id
),
invalid_plans AS (
  SELECT p.partner_id, p.id AS plan_id
  FROM zenos.plans p
  LEFT JOIN zenos.entities current_product
    ON current_product.partner_id = p.partner_id
   AND current_product.id = p.product_id
   AND current_product.type = 'product'
  WHERE p.product_id IS NULL OR current_product.id IS NULL
)
UPDATE zenos.plans p
SET product_id = fp.product_id
FROM first_product_per_partner fp
JOIN invalid_plans ip
  ON ip.partner_id = fp.partner_id
WHERE p.partner_id = fp.partner_id
  AND p.id = ip.plan_id;

COMMIT;
