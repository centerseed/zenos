-- Migration: Auth Federation Runtime
-- ADR-029: trusted_apps + identity_links tables

CREATE TABLE IF NOT EXISTS zenos.trusted_apps (
    app_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_name        TEXT NOT NULL UNIQUE,
    app_secret_hash TEXT NOT NULL,
    allowed_issuers TEXT[] NOT NULL DEFAULT '{}',
    allowed_scopes  TEXT[] NOT NULL DEFAULT '{read}',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_trusted_apps_name ON zenos.trusted_apps(app_name);

CREATE TABLE IF NOT EXISTS zenos.identity_links (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id           UUID NOT NULL REFERENCES zenos.trusted_apps(app_id),
    issuer           TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    email            TEXT,
    zenos_principal_id TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (app_id, issuer, external_user_id)
);
CREATE INDEX IF NOT EXISTS idx_identity_links_lookup ON zenos.identity_links(app_id, issuer, external_user_id);
CREATE INDEX IF NOT EXISTS idx_identity_links_principal ON zenos.identity_links(zenos_principal_id);
