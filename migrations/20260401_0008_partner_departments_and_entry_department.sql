begin;

create table if not exists zenos.partner_departments (
  tenant_id text not null,
  name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, name)
);

alter table zenos.entity_entries
  add column if not exists department text;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'chk_entry_department_length'
      and conrelid = 'zenos.entity_entries'::regclass
  ) then
    alter table zenos.entity_entries
      add constraint chk_entry_department_length
      check (department is null or char_length(department) <= 50);
  end if;
end $$;

insert into zenos.partner_departments (tenant_id, name)
select distinct coalesce(shared_partner_id, id), coalesce(nullif(trim(department), ''), 'all')
from zenos.partners
on conflict (tenant_id, name) do nothing;

insert into zenos.partner_departments (tenant_id, name)
select distinct coalesce(shared_partner_id, id), 'all'
from zenos.partners
on conflict (tenant_id, name) do nothing;

create index if not exists idx_partner_departments_tenant on zenos.partner_departments(tenant_id);
create index if not exists idx_entries_partner_department on zenos.entity_entries(partner_id, department);

commit;
