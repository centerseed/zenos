begin;

-- 1. 擴充 entity type constraint 加入 'deal'
alter table zenos.entities
  drop constraint if exists chk_entities_type;

alter table zenos.entities
  add constraint chk_entities_type
  check (type in (
    'product', 'module', 'goal', 'role', 'project', 'document',
    'company', 'person', 'deal'
  ));

-- 2. crm.deals 新增 zenos_entity_id
alter table crm.deals
  add column if not exists zenos_entity_id text;

commit;
