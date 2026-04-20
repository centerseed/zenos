-- SPEC-docs-native-edit-and-helper-ingest
-- Phase 1: Helper Ingest Contract + zenos_native source type
--
-- Notes:
--   sources is JSONB array on entities.sources_json. New per-source JSON keys
--   (external_id / external_updated_at / last_synced_at / snapshot_summary)
--   do NOT require DDL. Validation + uniqueness enforced in application layer.
--
-- This migration adds ONLY:
--   1. Partial expression index on (partner_id, sources_json) for cross-doc
--      duplicate detection query performance.
--   2. No hard constraints (we use warnings, not rejections, for cross-doc duplicates).

BEGIN;

SET search_path TO zenos, public;

-- Optional performance index; queries of form:
--   SELECT id FROM entities
--   WHERE partner_id = $1
--     AND sources_json @> '[{"external_id": "notion:abc"}]'::jsonb
-- benefit from this GIN index on sources_json (partner_id filter goes through
-- existing btree index on partner_id; Postgres combines via bitmap scan).
--
-- Note: original design used GIN(partner_id, sources_json) but that needs the
-- btree_gin extension, which is not enabled in this schema (only 'vector' is).
-- Fixed: index sources_json only; partner_id filter relies on separate btree.
CREATE INDEX IF NOT EXISTS idx_entities_source_external_ids
  ON entities USING gin (sources_json);

-- Note: snapshot_summary size is enforced in application (reject > 10KB in write handler).
-- Postgres's TOAST handles large JSONB rows but we don't want to balloon them here.

COMMENT ON INDEX idx_entities_source_external_ids
  IS 'GIN index on sources_json for Helper Ingest Contract cross-doc duplicate external_id lookups (SPEC-docs-native-edit-and-helper-ingest). Architect-fixed 2026-04-20: original design tried GIN(partner_id, sources_json) which needs btree_gin extension not enabled here.';

COMMIT;
