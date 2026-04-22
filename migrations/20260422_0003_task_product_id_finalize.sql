BEGIN;

-- ADR-044 / PLAN-task-ownership-ssot / S03
-- Cleanup elevated product links from task_entities and finalize NOT NULL contract.

SET search_path TO zenos, public;

DELETE FROM zenos.task_entities te
USING zenos.tasks t, zenos.entities e
WHERE t.partner_id = te.partner_id
  AND t.id = te.task_id
  AND e.partner_id = te.partner_id
  AND e.id = te.entity_id
  AND e.type = 'product'
  AND t.product_id = e.id;

ALTER TABLE zenos.tasks
  ALTER COLUMN product_id SET NOT NULL;

ALTER TABLE zenos.plans
  ALTER COLUMN product_id SET NOT NULL;

ALTER TABLE zenos.tasks
  VALIDATE CONSTRAINT fk_tasks_product;

ALTER TABLE zenos.plans
  VALIDATE CONSTRAINT fk_plans_product;

-- Cross-table type validation stays in application service:
-- TaskService / PlanService enforce product_id -> entities.type='product'.

COMMIT;
