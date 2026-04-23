begin;

set search_path to zenos, public;

-- ADR-046 Phase 1a preflight:
-- 1. documents.id must not collide with entities.id in the same partner scope
-- 2. documents.title must not collide with existing type='document' entity names
-- 3. entities.status must accept 'archived' before any backfill tries to map it

do $$
declare
  v_id_conflicts integer;
  v_title_conflicts integer;
begin
  select count(*)
    into v_id_conflicts
    from zenos.documents d
    join zenos.entities e
      on e.partner_id = d.partner_id
     and e.id = d.id;

  if v_id_conflicts <> 0 then
    raise exception
      'ADR-046 preflight failed: % document/entity id collisions detected',
      v_id_conflicts;
  end if;

  select count(*)
    into v_title_conflicts
    from zenos.documents d
    join zenos.entities e
      on e.partner_id = d.partner_id
     and e.type = 'document'
     and lower(e.name) = lower(d.title);

  if v_title_conflicts <> 0 then
    raise exception
      'ADR-046 preflight failed: % document title collisions detected against existing document entities',
      v_title_conflicts;
  end if;
end $$;

alter table zenos.entities
  drop constraint if exists chk_entities_status;

alter table zenos.entities
  add constraint chk_entities_status
  check (status in (
    'active', 'paused', 'completed', 'planned',
    'archived', 'current', 'stale', 'draft', 'conflict'
  ));

commit;
