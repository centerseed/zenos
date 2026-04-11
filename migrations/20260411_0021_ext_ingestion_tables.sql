-- Migration: Zentropy external ingestion tables
-- Spec: SPEC-zentropy-ingestion-contract
-- ADR: ADR-031-zentropy-ingestion-governance-boundary

CREATE TABLE IF NOT EXISTS zenos.external_signals (
    id TEXT PRIMARY KEY,
    partner_id TEXT NOT NULL REFERENCES zenos.partners(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    external_signal_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    raw_ref TEXT NOT NULL,
    summary TEXT NOT NULL,
    intent TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_external_signals_partner_workspace_external
        UNIQUE (partner_id, workspace_id, external_signal_id),
    CONSTRAINT chk_external_signals_event_type
        CHECK (event_type IN ('task_input', 'idea_input', 'reflection_input')),
    CONSTRAINT chk_external_signals_intent
        CHECK (intent IN ('todo', 'explore', 'decide', 'reflect')),
    CONSTRAINT chk_external_signals_confidence
        CHECK (confidence >= 0.0 AND confidence <= 1.0)
);
CREATE INDEX IF NOT EXISTS idx_external_signals_lookup
    ON zenos.external_signals(partner_id, workspace_id, product_id, occurred_at);

CREATE TABLE IF NOT EXISTS zenos.ingestion_batches (
    id TEXT PRIMARY KEY,
    partner_id TEXT NOT NULL REFERENCES zenos.partners(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    window_from TIMESTAMPTZ NOT NULL,
    window_to TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ingestion_batches_partner_id_id UNIQUE (partner_id, id),
    CONSTRAINT chk_ingestion_batches_status
        CHECK (status IN ('draft', 'distilled', 'committed', 'partial', 'failed'))
);
CREATE INDEX IF NOT EXISTS idx_ingestion_batches_lookup
    ON zenos.ingestion_batches(partner_id, workspace_id, product_id, created_at DESC);

CREATE TABLE IF NOT EXISTS zenos.ingestion_candidates (
    id TEXT PRIMARY KEY,
    partner_id TEXT NOT NULL REFERENCES zenos.partners(id) ON DELETE CASCADE,
    batch_id TEXT NOT NULL,
    candidate_type TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT NOT NULL DEFAULT '',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ingestion_candidates_partner_id_id UNIQUE (partner_id, id),
    CONSTRAINT fk_ingestion_candidates_batch
        FOREIGN KEY (partner_id, batch_id)
        REFERENCES zenos.ingestion_batches(partner_id, id)
        ON DELETE CASCADE,
    CONSTRAINT chk_ingestion_candidates_type
        CHECK (candidate_type IN ('task', 'entry', 'l2_update')),
    CONSTRAINT chk_ingestion_candidates_status
        CHECK (status IN ('draft', 'queued', 'committed', 'rejected')),
    CONSTRAINT chk_ingestion_candidates_confidence
        CHECK (confidence >= 0.0 AND confidence <= 1.0)
);
CREATE INDEX IF NOT EXISTS idx_ingestion_candidates_batch
    ON zenos.ingestion_candidates(partner_id, batch_id, candidate_type, status);

CREATE TABLE IF NOT EXISTS zenos.ingestion_review_queue (
    id TEXT PRIMARY KEY,
    partner_id TEXT NOT NULL REFERENCES zenos.partners(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    candidate_id TEXT NULL,
    review_type TEXT NOT NULL DEFAULT 'l2_update',
    status TEXT NOT NULL DEFAULT 'pending',
    note TEXT NOT NULL DEFAULT '',
    candidate_payload_json JSONB NULL,
    reviewed_by TEXT NULL,
    reviewed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_ingestion_review_batch
        FOREIGN KEY (partner_id, batch_id)
        REFERENCES zenos.ingestion_batches(partner_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_ingestion_review_candidate
        FOREIGN KEY (partner_id, candidate_id)
        REFERENCES zenos.ingestion_candidates(partner_id, id)
        ON DELETE SET NULL,
    CONSTRAINT chk_ingestion_review_status
        CHECK (status IN ('pending', 'approved', 'rejected')),
    CONSTRAINT chk_ingestion_review_type
        CHECK (review_type IN ('l2_update', 'entry_review', 'task_review'))
);
CREATE INDEX IF NOT EXISTS idx_ingestion_review_lookup
    ON zenos.ingestion_review_queue(partner_id, workspace_id, product_id, status, created_at DESC);
