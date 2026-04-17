begin;

alter table zenos.entities
  add column if not exists bundle_highlights_json jsonb null default '[]'::jsonb;

alter table zenos.entities
  add column if not exists highlights_updated_at timestamptz null;

commit;
