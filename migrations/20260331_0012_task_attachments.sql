-- Add attachments JSONB column to tasks table for storing file/image/link metadata.
ALTER TABLE zenos.tasks
ADD COLUMN IF NOT EXISTS attachments JSONB DEFAULT '[]'::jsonb;
