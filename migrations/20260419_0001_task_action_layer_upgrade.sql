begin;

-- Action-Layer upgrade: subtask / dispatcher / handoff (SPEC-task-governance §2026-04-19)

ALTER TABLE zenos.tasks ADD COLUMN parent_task_id TEXT;
ALTER TABLE zenos.tasks ADD COLUMN dispatcher TEXT;
ALTER TABLE zenos.tasks ADD COLUMN handoff_events JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX idx_tasks_parent_task_id ON zenos.tasks(parent_task_id) WHERE parent_task_id IS NOT NULL;
CREATE INDEX idx_tasks_dispatcher ON zenos.tasks(dispatcher) WHERE dispatcher IS NOT NULL;

commit;
