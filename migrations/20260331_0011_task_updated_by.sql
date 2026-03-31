-- Track the last task updater for governance accountability.
ALTER TABLE zenos.tasks
ADD COLUMN IF NOT EXISTS updated_by text NULL;

-- Backfill existing rows so legacy data has a deterministic updater.
UPDATE zenos.tasks
SET updated_by = COALESCE(updated_by, created_by)
WHERE updated_by IS NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_partner_updated_by
  ON zenos.tasks(partner_id, updated_by);
