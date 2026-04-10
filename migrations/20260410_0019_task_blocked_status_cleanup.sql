-- Migration: Action Layer task status alignment
-- Purpose: remove legacy "blocked" status values by normalizing to "todo"
-- NOTE: blocking semantics stay in blocked_by / blocked_reason fields.

UPDATE zenos.tasks
SET status = 'todo',
    updated_at = now()
WHERE status = 'blocked';
