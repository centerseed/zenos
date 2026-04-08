-- Align entity visibility storage with SPEC-identity-and-access / ADR-018.
-- 1) Backfill legacy role-restricted -> restricted
-- 2) Remove role-restricted from DB constraint so no new legacy values enter
-- 3) Clear legacy role/department-scoped fields on rows that were only using role-restricted

begin;

set search_path to zenos, public;

update entities
set visibility = 'restricted',
    visible_to_roles = '{}'::text[],
    visible_to_departments = '{}'::text[],
    updated_at = now()
where visibility = 'role-restricted';

do $$
begin
  if exists (
    select 1 from pg_constraint
    where conname = 'chk_entities_visibility'
      and connamespace = 'zenos'::regnamespace
  ) then
    alter table entities drop constraint chk_entities_visibility;
  end if;
end
$$;

alter table entities
  add constraint chk_entities_visibility
  check (visibility in ('public', 'restricted', 'confidential'));

commit;
