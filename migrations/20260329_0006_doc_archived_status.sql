begin;

-- Drop and recreate chk_entities_status to add 'archived' as a valid status.
-- Current allowed values: 'active', 'paused', 'completed', 'planned', 'current', 'stale', 'draft', 'conflict'
-- Adding 'archived' to support dead-link document entity archival (SPEC-doc-source-governance).
ALTER TABLE zenos.entities
  DROP CONSTRAINT chk_entities_status;

ALTER TABLE zenos.entities
  ADD CONSTRAINT chk_entities_status
  CHECK (status IN ('active', 'paused', 'completed', 'planned', 'current', 'stale', 'draft', 'conflict', 'archived'));

commit;
