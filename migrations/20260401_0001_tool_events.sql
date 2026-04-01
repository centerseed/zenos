-- Migration: Add tool_events table for agent behavior tracking
-- SPEC-governance-feedback-loop P2-1

CREATE TABLE zenos.tool_events (
  id          bigserial   PRIMARY KEY,
  partner_id  text        NOT NULL REFERENCES zenos.partners(id),
  tool_name   text        NOT NULL,
  entity_id   text,
  query       text,
  result_count integer,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_tool_events_partner_entity ON zenos.tool_events(partner_id, entity_id, tool_name);
CREATE INDEX idx_tool_events_partner_created ON zenos.tool_events(partner_id, created_at DESC);
