begin;

set search_path to zenos, public;

with related_candidates as (
  select
    de.partner_id,
    de.document_id,
    array_agg(de.entity_id order by de.entity_id) as candidate_parent_ids
  from zenos.document_entities de
  group by de.partner_id, de.document_id
),
docs_to_backfill as (
  select
    d.partner_id,
    d.id,
    d.title,
    d.summary,
    d.status,
    d.tags_json,
    d.confirmed_by_user,
    d.last_reviewed_at,
    d.created_at,
    d.updated_at,
    d.source_json,
    coalesce(rc.candidate_parent_ids, array[]::text[]) as candidate_parent_ids
  from zenos.documents d
  left join related_candidates rc
    on rc.partner_id = d.partner_id
   and rc.document_id = d.id
)
insert into zenos.entities (
  id,
  partner_id,
  name,
  type,
  level,
  parent_id,
  status,
  summary,
  tags_json,
  details_json,
  confirmed_by_user,
  owner,
  sources_json,
  visibility,
  created_at,
  updated_at,
  last_reviewed_at,
  doc_role
)
select
  d.id,
  d.partner_id,
  d.title,
  'document',
  3,
  null,
  d.status,
  d.summary,
  d.tags_json,
  jsonb_build_object(
    'primary_parent_remediation',
    jsonb_build_object(
      'status', 'pending',
      'reason', 'historical_document_entities_lacked_order',
      'candidate_parent_ids', to_jsonb(d.candidate_parent_ids),
      'backfilled_at', to_jsonb(now()),
      'resolved_at', null,
      'resolved_by', null
    )
  ),
  d.confirmed_by_user,
  null,
  jsonb_build_array(
    d.source_json
      || jsonb_build_object(
        'source_id', 'legacy-' || d.id,
        'label', d.title,
        'is_primary', true,
        'status', 'valid',
        'source_status', 'valid'
      )
  ),
  'public',
  d.created_at,
  d.updated_at,
  d.last_reviewed_at,
  'single'
from docs_to_backfill d
where not exists (
  select 1
  from zenos.entities e
  where e.partner_id = d.partner_id
    and e.id = d.id
);

insert into zenos.relationships (
  id,
  partner_id,
  source_entity_id,
  target_entity_id,
  type,
  description,
  confirmed_by_user
)
select
  md5('docrel:' || de.partner_id || ':' || de.document_id || ':' || de.entity_id),
  de.partner_id,
  de.document_id,
  de.entity_id,
  'related_to',
  'Backfilled from legacy document_entities during ADR-046 migration',
  true
from zenos.document_entities de
join zenos.entities doc
  on doc.partner_id = de.partner_id
 and doc.id = de.document_id
 and doc.type = 'document'
on conflict on constraint uq_relationships_dedup do nothing;

commit;
