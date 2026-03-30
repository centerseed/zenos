-- Permission governance rollout (plan-permission-governance-rollout-v1, step 2)
-- Adds partner role/department scope and entity-level role/member/department visibility.

begin;

set search_path to zenos, public;

alter table if exists partners
  add column if not exists roles text[] not null default '{}'::text[],
  add column if not exists department text not null default 'all';

alter table if exists entities
  add column if not exists visible_to_roles text[] not null default '{}'::text[],
  add column if not exists visible_to_members text[] not null default '{}'::text[],
  add column if not exists visible_to_departments text[] not null default '{}'::text[];

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
  check (visibility in ('public', 'restricted', 'role-restricted', 'confidential'));

create index if not exists idx_partners_roles on partners using gin(roles);
create index if not exists idx_partners_department on partners(department);
create index if not exists idx_entities_visible_roles on entities using gin(visible_to_roles);
create index if not exists idx_entities_visible_members on entities using gin(visible_to_members);
create index if not exists idx_entities_visible_departments on entities using gin(visible_to_departments);

commit;
