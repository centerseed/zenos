begin;

alter table if exists tasks
  add column if not exists plan_id text null,
  add column if not exists plan_order integer null,
  add column if not exists depends_on_task_ids_json jsonb not null default '[]'::jsonb;

-- task belongs to plan-like task group; no separate plan table in this phase.
create index if not exists idx_tasks_partner_plan_id
  on tasks(partner_id, plan_id)
  where plan_id is not null;

create index if not exists idx_tasks_partner_plan_order
  on tasks(partner_id, plan_id, plan_order)
  where plan_id is not null;

-- Keep plan order unique within one partner plan when provided.
create unique index if not exists uq_tasks_partner_plan_order
  on tasks(partner_id, plan_id, plan_order)
  where plan_id is not null and plan_order is not null;

alter table if exists tasks
  add constraint chk_tasks_plan_order_positive
  check (plan_order is null or plan_order >= 1);

alter table if exists tasks
  add constraint chk_tasks_plan_order_requires_plan_id
  check (plan_order is null or plan_id is not null);

commit;
