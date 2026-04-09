-- Migration: Add governance_health_cache table
-- Date: 2026-04-09
-- Purpose: Cache governance health signal (overall_level) per partner for
--          Dashboard display. Written by batch_update_sources / analyze(health),
--          read by GET /api/data/governance-health.

CREATE TABLE IF NOT EXISTS zenos.governance_health_cache (
    partner_id    TEXT        NOT NULL PRIMARY KEY,
    overall_level TEXT        NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
