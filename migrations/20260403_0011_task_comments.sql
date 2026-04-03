-- Task comments table for client portal collaboration
-- No FK constraints: task_id may span tenants; tenant isolation handled at API layer via task visibility checks.
CREATE TABLE IF NOT EXISTS zenos.task_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL,
  partner_id TEXT NOT NULL,
  content TEXT NOT NULL CHECK (length(trim(content)) > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_task_comments_task_id ON zenos.task_comments(task_id);
