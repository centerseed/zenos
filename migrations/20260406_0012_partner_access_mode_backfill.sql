-- Fix backfill for existing partners after adding access_mode.

begin;

update zenos.partners
set access_mode = case
  when is_admin then 'internal'
  when coalesce(array_length(authorized_entity_ids, 1), 0) > 0 then 'scoped'
  when status = 'active' then 'internal'
  else 'unassigned'
end
where
  (is_admin and access_mode <> 'internal')
  or (not is_admin and coalesce(array_length(authorized_entity_ids, 1), 0) > 0 and access_mode <> 'scoped')
  or (
    not is_admin
    and coalesce(array_length(authorized_entity_ids, 1), 0) = 0
    and status = 'active'
    and access_mode <> 'internal'
  )
  or (status <> 'active' and coalesce(array_length(authorized_entity_ids, 1), 0) = 0 and access_mode <> 'unassigned');

commit;
