-- Add explicit partner access mode to separate identity from scope.

begin;

alter table zenos.partners
  add column if not exists access_mode text not null default 'unassigned';

alter table zenos.partners
  drop constraint if exists chk_partners_access_mode;

alter table zenos.partners
  add constraint chk_partners_access_mode
  check (access_mode in ('internal', 'scoped', 'unassigned'));

update zenos.partners
set access_mode = case
  when is_admin then 'internal'
  when coalesce(array_length(authorized_entity_ids, 1), 0) > 0 then 'scoped'
  when status = 'active' then 'internal'
  else 'unassigned'
end
where access_mode is null
   or access_mode not in ('internal', 'scoped', 'unassigned');

commit;
