BEGIN;

ALTER TABLE zenos.entity_entries
  ADD COLUMN IF NOT EXISTS archive_reason text;

ALTER TABLE zenos.entity_entries
  ADD CONSTRAINT chk_entry_archive_reason
    CHECK (archive_reason IS NULL OR archive_reason IN ('merged', 'manual'));

ALTER TABLE zenos.entity_entries
  ADD CONSTRAINT chk_entry_archived_has_reason
    CHECK ((status != 'archived') OR (archive_reason IS NOT NULL));

COMMIT;
