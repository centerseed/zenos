begin;

-- Enable pgvector extension (requires superuser or pg_extension_owner privilege)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding columns to zenos.entities (Phase 1 of Pillar A semantic retrieval)
-- zenos.documents is intentionally excluded (ADR-042 scope)
ALTER TABLE zenos.entities
    ADD COLUMN IF NOT EXISTS summary_embedding vector(768),
    ADD COLUMN IF NOT EXISTS embedding_model text,
    ADD COLUMN IF NOT EXISTS embedded_at timestamptz,
    ADD COLUMN IF NOT EXISTS embedded_summary_hash text;

-- HNSW index for cosine similarity search on summary_embedding
-- Provision early for scale even though 298-entity corpus does not strictly require it
CREATE INDEX IF NOT EXISTS idx_entities_summary_embedding_hnsw
    ON zenos.entities
    USING hnsw (summary_embedding vector_cosine_ops);

commit;
