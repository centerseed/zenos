-- Simplify task status model:
-- backlog + todo   -> todo
-- blocked          -> in_progress
-- done + archived  -> done
-- keep review / cancelled

UPDATE zenos.tasks
SET status = CASE status
  WHEN 'backlog' THEN 'todo'
  WHEN 'blocked' THEN 'in_progress'
  WHEN 'archived' THEN 'done'
  ELSE status
END
WHERE status IN ('backlog', 'blocked', 'archived');

-- Ensure done rows have completed_at.
UPDATE zenos.tasks
SET completed_at = COALESCE(completed_at, updated_at, created_at, now())
WHERE status = 'done' AND completed_at IS NULL;

ALTER TABLE zenos.tasks
  DROP CONSTRAINT IF EXISTS chk_tasks_status;

ALTER TABLE zenos.tasks
  ADD CONSTRAINT chk_tasks_status
  CHECK (status IN ('todo', 'in_progress', 'review', 'done', 'cancelled'));

-- blocked status removed; blocked_reason now optional metadata only.
ALTER TABLE zenos.tasks
  DROP CONSTRAINT IF EXISTS chk_tasks_blocked_reason;

ALTER TABLE zenos.tasks
  ADD CONSTRAINT chk_tasks_blocked_reason
  CHECK (true);
