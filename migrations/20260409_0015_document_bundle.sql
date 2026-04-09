-- ADR-022: Document Bundle — L3 entity upgrade for semantic document index
-- Adds doc_role, change_summary, summary_updated_at to entities table
-- for document-type entities. Non-document entities will have these as NULL.

BEGIN;

SET search_path TO zenos, public;

-- 1) doc_role: distinguishes single-doc vs index-doc entities
--    Default 'single' for backward compatibility with existing doc entities.
ALTER TABLE entities
  ADD COLUMN IF NOT EXISTS doc_role text NULL DEFAULT NULL;

-- Only constrain doc_role values when set (NULL = non-document entity)
ALTER TABLE entities
  ADD CONSTRAINT chk_entities_doc_role
    CHECK (doc_role IS NULL OR doc_role IN ('single', 'index'));

-- 2) change_summary: human-authored summary of recent document changes
ALTER TABLE entities
  ADD COLUMN IF NOT EXISTS change_summary text NULL;

-- 3) summary_updated_at: tracks when change_summary was last updated
ALTER TABLE entities
  ADD COLUMN IF NOT EXISTS summary_updated_at timestamptz NULL;

-- Backfill: set doc_role='single' for all existing document entities
UPDATE entities SET doc_role = 'single' WHERE type = 'document' AND doc_role IS NULL;

COMMIT;
