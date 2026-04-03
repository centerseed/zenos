-- Migration: Add verb column to relationships table
-- Date: 2026-04-03
-- Purpose: Support semantic verb annotation on relationship edges (P0.1 of SPEC-knowledge-graph-semantic)

ALTER TABLE zenos.relationships ADD COLUMN IF NOT EXISTS verb TEXT;
