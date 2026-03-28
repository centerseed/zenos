begin;

CREATE TABLE IF NOT EXISTS zenos.entity_entries (
  id              text        NOT NULL,
  partner_id      text        NOT NULL,
  entity_id       text        NOT NULL,
  type            text        NOT NULL,
  content         text        NOT NULL,
  context         text,
  author          text,
  source_task_id  text,
  status          text        NOT NULL DEFAULT 'active',
  superseded_by   text,
  created_at      timestamptz NOT NULL DEFAULT now(),

  PRIMARY KEY (id),
  UNIQUE (partner_id, id),
  FOREIGN KEY (partner_id, entity_id) REFERENCES zenos.entities(partner_id, id),
  FOREIGN KEY (partner_id, superseded_by) REFERENCES zenos.entity_entries(partner_id, id),
  CONSTRAINT chk_entry_type CHECK (type IN ('decision', 'insight', 'limitation', 'change', 'context')),
  CONSTRAINT chk_entry_status CHECK (status IN ('active', 'superseded', 'archived')),
  CONSTRAINT chk_entry_content_length CHECK (char_length(content) BETWEEN 1 AND 200),
  CONSTRAINT chk_entry_context_length CHECK (context IS NULL OR char_length(context) <= 200),
  CONSTRAINT chk_entry_superseded_consistency CHECK (
    (status != 'superseded') OR (superseded_by IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_entries_partner_entity ON zenos.entity_entries(partner_id, entity_id);
CREATE INDEX IF NOT EXISTS idx_entries_partner_entity_type ON zenos.entity_entries(partner_id, entity_id, type);
CREATE INDEX IF NOT EXISTS idx_entries_partner_entity_active ON zenos.entity_entries(partner_id, entity_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_entries_partner_created ON zenos.entity_entries(partner_id, created_at DESC);

commit;
