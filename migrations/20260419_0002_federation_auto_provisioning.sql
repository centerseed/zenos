-- Migration: Federation Auto-Provisioning
-- SPEC-federation-auto-provisioning: P0 Owner-Approve Flow + P1 Domain Auto-Link

BEGIN;

-- Extend trusted_apps with auto-provisioning config
ALTER TABLE zenos.trusted_apps
    ADD COLUMN IF NOT EXISTS default_workspace_id  TEXT REFERENCES zenos.partners(id),
    ADD COLUMN IF NOT EXISTS auto_link_email_domains TEXT[] NOT NULL DEFAULT '{}';

-- Pending identity link requests awaiting workspace owner approval
CREATE TABLE IF NOT EXISTS zenos.pending_identity_links (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id           UUID NOT NULL REFERENCES zenos.trusted_apps(app_id),
    issuer           TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    email            TEXT,
    workspace_id     TEXT NOT NULL REFERENCES zenos.partners(id),
    status           TEXT NOT NULL DEFAULT 'pending',
    reviewed_by      TEXT REFERENCES zenos.partners(id),
    reviewed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '7 days'
);

-- Only one active pending request per (app, issuer, user)
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_links_active
    ON zenos.pending_identity_links (app_id, issuer, external_user_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_pending_links_workspace
    ON zenos.pending_identity_links (workspace_id, status);

COMMIT;
