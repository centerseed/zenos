-- Add structured source metadata for task provenance and external sync indicators.
ALTER TABLE zenos.tasks
ADD COLUMN IF NOT EXISTS source_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb;
