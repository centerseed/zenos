BEGIN;

-- ADR-044 / PLAN-task-ownership-ssot / S01
-- Rename action-layer ownership FK from project_id -> product_id for tasks/plans.
-- This migration does NOT add NOT NULL; backfill/finalize happen in S02/S03.
--
-- Manual rollback SQL (run inside a transaction if needed):
--   ALTER TABLE zenos.tasks RENAME COLUMN product_id TO project_id;
--   ALTER TABLE zenos.plans RENAME COLUMN product_id TO project_id;
--   ALTER INDEX zenos.idx_tasks_partner_product_id RENAME TO idx_tasks_partner_project_id;
--   ALTER INDEX zenos.idx_plans_partner_product_id RENAME TO idx_plans_partner_project_id;
--   ALTER TABLE zenos.tasks RENAME CONSTRAINT fk_tasks_product TO fk_tasks_project;
--   ALTER TABLE zenos.plans RENAME CONSTRAINT fk_plans_product TO fk_plans_project;

SET search_path TO zenos, public;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'zenos' AND table_name = 'tasks' AND column_name = 'project_id'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'zenos' AND table_name = 'tasks' AND column_name = 'product_id'
  ) THEN
    ALTER TABLE zenos.tasks RENAME COLUMN project_id TO product_id;
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'zenos' AND table_name = 'plans' AND column_name = 'project_id'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'zenos' AND table_name = 'plans' AND column_name = 'product_id'
  ) THEN
    ALTER TABLE zenos.plans RENAME COLUMN project_id TO product_id;
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'zenos' AND indexname = 'idx_tasks_partner_project_id'
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'zenos' AND indexname = 'idx_tasks_partner_product_id'
  ) THEN
    ALTER INDEX zenos.idx_tasks_partner_project_id RENAME TO idx_tasks_partner_product_id;
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'zenos' AND indexname = 'idx_plans_partner_project_id'
  ) AND NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'zenos' AND indexname = 'idx_plans_partner_product_id'
  ) THEN
    ALTER INDEX zenos.idx_plans_partner_project_id RENAME TO idx_plans_partner_product_id;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_tasks_partner_product_id
  ON zenos.tasks(partner_id, product_id);

CREATE INDEX IF NOT EXISTS idx_plans_partner_product_id
  ON zenos.plans(partner_id, product_id)
  WHERE product_id IS NOT NULL;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'zenos'
      AND table_name = 'tasks'
      AND constraint_name = 'fk_tasks_project'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'zenos'
      AND table_name = 'tasks'
      AND constraint_name = 'fk_tasks_product'
  ) THEN
    ALTER TABLE zenos.tasks RENAME CONSTRAINT fk_tasks_project TO fk_tasks_product;
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'zenos'
      AND table_name = 'plans'
      AND constraint_name = 'fk_plans_project'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'zenos'
      AND table_name = 'plans'
      AND constraint_name = 'fk_plans_product'
  ) THEN
    ALTER TABLE zenos.plans RENAME CONSTRAINT fk_plans_project TO fk_plans_product;
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'zenos'
      AND table_name = 'tasks'
      AND constraint_name = 'fk_tasks_product'
  ) THEN
    ALTER TABLE zenos.tasks
      ADD CONSTRAINT fk_tasks_product
      FOREIGN KEY (partner_id, product_id)
      REFERENCES zenos.entities(partner_id, id)
      ON DELETE SET NULL
      NOT VALID;
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'zenos'
      AND table_name = 'plans'
      AND constraint_name = 'fk_plans_product'
  ) THEN
    ALTER TABLE zenos.plans
      ADD CONSTRAINT fk_plans_product
      FOREIGN KEY (partner_id, product_id)
      REFERENCES zenos.entities(partner_id, id)
      ON DELETE SET NULL
      NOT VALID;
  END IF;
END
$$;

COMMIT;
