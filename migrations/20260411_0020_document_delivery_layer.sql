-- ADR-032: Document Delivery Layer
-- Adds stable delivery metadata on entities and introduces
-- document revision snapshots + share token tables.

BEGIN;

SET search_path TO zenos, public;

-- 1) Entity-level delivery metadata
ALTER TABLE entities
  ADD COLUMN IF NOT EXISTS canonical_path text NULL;

ALTER TABLE entities
  ADD COLUMN IF NOT EXISTS primary_snapshot_revision_id text NULL;

ALTER TABLE entities
  ADD COLUMN IF NOT EXISTS last_published_at timestamptz NULL;

ALTER TABLE entities
  ADD COLUMN IF NOT EXISTS delivery_status text NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_entities_delivery_status'
  ) THEN
    ALTER TABLE entities
      ADD CONSTRAINT chk_entities_delivery_status
      CHECK (
        delivery_status IS NULL
        OR delivery_status IN ('ready', 'stale', 'blocked')
      );
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_entities_partner_canonical_path
  ON entities (partner_id, canonical_path)
  WHERE canonical_path IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_entities_partner_delivery_status
  ON entities (partner_id, delivery_status)
  WHERE delivery_status IS NOT NULL;

-- 2) Snapshot revisions
CREATE TABLE IF NOT EXISTS document_revisions (
  id text PRIMARY KEY,
  partner_id text NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  doc_id text NOT NULL,
  source_id text NULL,
  source_version_ref text NULL,
  snapshot_bucket text NOT NULL,
  snapshot_object_path text NOT NULL,
  content_hash text NOT NULL,
  render_format text NOT NULL DEFAULT 'markdown',
  content_type text NOT NULL DEFAULT 'text/markdown',
  created_by text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_document_revisions_partner_id_id UNIQUE (partner_id, id),
  CONSTRAINT fk_document_revisions_doc
    FOREIGN KEY (partner_id, doc_id) REFERENCES entities(partner_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_document_revisions_partner_doc_created
  ON document_revisions (partner_id, doc_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_document_revisions_partner_source
  ON document_revisions (partner_id, source_id)
  WHERE source_id IS NOT NULL;

-- 3) Share tokens (external read links)
CREATE TABLE IF NOT EXISTS document_share_tokens (
  id text PRIMARY KEY,
  partner_id text NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  doc_id text NOT NULL,
  token_hash text NOT NULL,
  scope text NOT NULL DEFAULT 'read',
  expires_at timestamptz NULL,
  max_access_count integer NULL,
  used_count integer NOT NULL DEFAULT 0,
  revoked_at timestamptz NULL,
  created_by text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_document_share_tokens_partner_id_id UNIQUE (partner_id, id),
  CONSTRAINT uq_document_share_tokens_token_hash UNIQUE (token_hash),
  CONSTRAINT fk_document_share_tokens_doc
    FOREIGN KEY (partner_id, doc_id) REFERENCES entities(partner_id, id) ON DELETE CASCADE,
  CONSTRAINT chk_document_share_tokens_scope
    CHECK (scope IN ('read')),
  CONSTRAINT chk_document_share_tokens_max_access
    CHECK (max_access_count IS NULL OR max_access_count > 0)
);

CREATE INDEX IF NOT EXISTS idx_document_share_tokens_partner_doc
  ON document_share_tokens (partner_id, doc_id);

CREATE INDEX IF NOT EXISTS idx_document_share_tokens_expires
  ON document_share_tokens (expires_at)
  WHERE expires_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_document_share_tokens_revoked
  ON document_share_tokens (revoked_at)
  WHERE revoked_at IS NOT NULL;

COMMIT;
