-- ZenOS SQL cutover initial migration
-- Spec source: docs/specs/SPEC-zenos-sql-cutover.md

begin;

create schema if not exists zenos;
set search_path to zenos, public;

-- 1) partners
create table if not exists partners (
  id text primary key,
  email text not null unique,
  display_name text not null,
  api_key text not null default '',
  authorized_entity_ids text[] not null default '{}'::text[],
  status text not null default 'active',
  is_admin boolean not null default false,
  shared_partner_id text null,
  default_project text null,
  invited_by text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint chk_partners_status
    check (status in ('invited', 'active', 'suspended'))
);

create unique index if not exists uq_partners_api_key_non_empty
  on partners(api_key)
  where api_key <> '';
create index if not exists idx_partners_status on partners(status);
create index if not exists idx_partners_shared_partner on partners(shared_partner_id);
create index if not exists idx_partners_authorized_entities on partners using gin(authorized_entity_ids);

-- 2) entities
create table if not exists entities (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  name text not null,
  type text not null,
  level integer null,
  parent_id text null,
  project_id text null,
  status text not null default 'active',
  summary text not null,
  tags_json jsonb not null default '{}'::jsonb,
  details_json jsonb null,
  confirmed_by_user boolean not null default false,
  owner text null,
  sources_json jsonb not null default '[]'::jsonb,
  visibility text not null default 'public',
  last_reviewed_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_entities_partner_id_id unique (partner_id, id),
  constraint chk_entities_type
    check (type in ('product', 'module', 'goal', 'role', 'project', 'document')),
  constraint chk_entities_status
    check (status in ('active', 'paused', 'completed', 'planned', 'current', 'stale', 'draft', 'conflict')),
  constraint chk_entities_visibility
    check (visibility in ('public', 'restricted')),
  constraint chk_entities_project_root
    check ((type not in ('product', 'project')) or project_id = id),
  constraint fk_entities_parent
    foreign key (partner_id, parent_id) references entities(partner_id, id) on delete set null,
  constraint fk_entities_project
    foreign key (partner_id, project_id) references entities(partner_id, id) on delete set null
);

create index if not exists idx_entities_partner_type on entities(partner_id, type);
create index if not exists idx_entities_partner_parent on entities(partner_id, parent_id);
create index if not exists idx_entities_partner_status on entities(partner_id, status);
create index if not exists idx_entities_partner_confirmed on entities(partner_id, confirmed_by_user);
create index if not exists idx_entities_partner_name on entities(partner_id, name);
create index if not exists idx_entities_partner_project_id on entities(partner_id, project_id);

-- 3) relationships
create table if not exists relationships (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  source_entity_id text not null,
  target_entity_id text not null,
  type text not null,
  description text not null,
  confirmed_by_user boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_relationships_partner_id_id unique (partner_id, id),
  constraint uq_relationships_dedup unique (partner_id, source_entity_id, target_entity_id, type),
  constraint fk_relationships_source
    foreign key (partner_id, source_entity_id) references entities(partner_id, id) on delete cascade,
  constraint fk_relationships_target
    foreign key (partner_id, target_entity_id) references entities(partner_id, id) on delete cascade,
  constraint chk_relationships_type
    check (type in ('depends_on', 'serves', 'owned_by', 'part_of', 'blocks', 'related_to', 'impacts', 'enables')),
  constraint chk_relationships_no_self_loop
    check (source_entity_id <> target_entity_id)
);

create index if not exists idx_relationships_partner_source on relationships(partner_id, source_entity_id);
create index if not exists idx_relationships_partner_target on relationships(partner_id, target_entity_id);
create index if not exists idx_relationships_partner_type on relationships(partner_id, type);
create index if not exists idx_relationships_partner_source_type on relationships(partner_id, source_entity_id, type);

-- 4) documents
create table if not exists documents (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  title text not null,
  source_json jsonb not null,
  tags_json jsonb not null default '{}'::jsonb,
  summary text not null,
  status text not null default 'current',
  confirmed_by_user boolean not null default false,
  last_reviewed_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_documents_partner_id_id unique (partner_id, id),
  constraint chk_documents_status
    check (status in ('current', 'stale', 'archived', 'draft', 'conflict')),
  constraint chk_documents_source_type
    check ((source_json ? 'type') and (source_json->>'type') in ('github', 'gdrive', 'notion', 'upload'))
);

create index if not exists idx_documents_partner_status on documents(partner_id, status);
create index if not exists idx_documents_partner_confirmed on documents(partner_id, confirmed_by_user);
create index if not exists idx_documents_partner_title on documents(partner_id, title);

-- 5) document_entities
create table if not exists document_entities (
  document_id text not null,
  entity_id text not null,
  partner_id text not null references partners(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (document_id, entity_id),
  constraint fk_document_entities_document
    foreign key (partner_id, document_id) references documents(partner_id, id) on delete cascade,
  constraint fk_document_entities_entity
    foreign key (partner_id, entity_id) references entities(partner_id, id) on delete cascade
);

create index if not exists idx_document_entities_partner_entity on document_entities(partner_id, entity_id);
create index if not exists idx_document_entities_partner_document on document_entities(partner_id, document_id);

-- 6) protocols
create table if not exists protocols (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  entity_id text not null,
  entity_name text not null,
  content_json jsonb not null,
  gaps_json jsonb not null default '[]'::jsonb,
  version text not null default '1.0',
  confirmed_by_user boolean not null default false,
  generated_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_protocols_partner_id_id unique (partner_id, id),
  constraint uq_protocols_partner_entity unique (partner_id, entity_id),
  constraint fk_protocols_entity
    foreign key (partner_id, entity_id) references entities(partner_id, id) on delete cascade
);

create index if not exists idx_protocols_partner_name on protocols(partner_id, entity_name);
create index if not exists idx_protocols_partner_confirmed on protocols(partner_id, confirmed_by_user);

-- 7) blindspots
create table if not exists blindspots (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  description text not null,
  severity text not null,
  suggested_action text not null,
  status text not null default 'open',
  confirmed_by_user boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_blindspots_partner_id_id unique (partner_id, id),
  constraint chk_blindspots_severity
    check (severity in ('red', 'yellow', 'green')),
  constraint chk_blindspots_status
    check (status in ('open', 'acknowledged', 'resolved'))
);

create index if not exists idx_blindspots_partner_status on blindspots(partner_id, status);
create index if not exists idx_blindspots_partner_severity on blindspots(partner_id, severity);
create index if not exists idx_blindspots_partner_confirmed on blindspots(partner_id, confirmed_by_user);

-- 8) blindspot_entities
create table if not exists blindspot_entities (
  blindspot_id text not null,
  entity_id text not null,
  partner_id text not null references partners(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blindspot_id, entity_id),
  constraint fk_blindspot_entities_blindspot
    foreign key (partner_id, blindspot_id) references blindspots(partner_id, id) on delete cascade,
  constraint fk_blindspot_entities_entity
    foreign key (partner_id, entity_id) references entities(partner_id, id) on delete cascade
);

create index if not exists idx_blindspot_entities_partner_entity on blindspot_entities(partner_id, entity_id);
create index if not exists idx_blindspot_entities_partner_blindspot on blindspot_entities(partner_id, blindspot_id);

-- 9) tasks
create table if not exists tasks (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  title text not null,
  description text not null default '',
  status text not null default 'backlog',
  priority text not null default 'medium',
  priority_reason text not null default '',
  assignee text null,
  assignee_role_id text null,
  created_by text not null,
  plan_id text null,
  plan_order integer null,
  depends_on_task_ids_json jsonb not null default '[]'::jsonb,
  linked_protocol text null,
  linked_blindspot text null,
  source_type text not null default '',
  context_summary text not null default '',
  due_date timestamptz null,
  blocked_reason text null,
  acceptance_criteria_json jsonb not null default '[]'::jsonb,
  completed_by text null,
  confirmed_by_creator boolean not null default false,
  rejection_reason text null,
  result text null,
  project text not null default '',
  project_id text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz null,
  constraint uq_tasks_partner_id_id unique (partner_id, id),
  constraint fk_tasks_assignee_role
    foreign key (partner_id, assignee_role_id) references entities(partner_id, id) on delete set null,
  constraint fk_tasks_linked_protocol
    foreign key (partner_id, linked_protocol) references protocols(partner_id, id) on delete set null,
  constraint fk_tasks_linked_blindspot
    foreign key (partner_id, linked_blindspot) references blindspots(partner_id, id) on delete set null,
  constraint fk_tasks_project
    foreign key (partner_id, project_id) references entities(partner_id, id) on delete set null,
  constraint chk_tasks_status
    check (status in ('backlog', 'todo', 'in_progress', 'review', 'done', 'archived', 'blocked', 'cancelled')),
  constraint chk_tasks_priority
    check (priority in ('critical', 'high', 'medium', 'low')),
  constraint chk_tasks_blocked_reason
    check ((status <> 'blocked') or (blocked_reason is not null and blocked_reason <> '')),
  constraint chk_tasks_review_result
    check ((status <> 'review') or (result is not null)),
  constraint chk_tasks_done_completed_at
    check ((status <> 'done') or (completed_at is not null)),
  constraint chk_tasks_plan_order_positive
    check (plan_order is null or plan_order >= 1),
  constraint chk_tasks_plan_order_requires_plan_id
    check (plan_order is null or plan_id is not null)
);

create index if not exists idx_tasks_partner_status on tasks(partner_id, status);
create index if not exists idx_tasks_partner_assignee on tasks(partner_id, assignee);
create index if not exists idx_tasks_partner_created_by on tasks(partner_id, created_by);
create index if not exists idx_tasks_partner_project on tasks(partner_id, project);
create index if not exists idx_tasks_partner_project_id on tasks(partner_id, project_id);
create index if not exists idx_tasks_partner_priority on tasks(partner_id, priority);
create index if not exists idx_tasks_partner_due_date on tasks(partner_id, due_date);
create index if not exists idx_tasks_partner_linked_blindspot on tasks(partner_id, linked_blindspot);
create index if not exists idx_tasks_partner_confirmed on tasks(partner_id, confirmed_by_creator);
create index if not exists idx_tasks_partner_plan_id on tasks(partner_id, plan_id) where plan_id is not null;
create index if not exists idx_tasks_partner_plan_order on tasks(partner_id, plan_id, plan_order) where plan_id is not null;
create unique index if not exists uq_tasks_partner_plan_order
  on tasks(partner_id, plan_id, plan_order)
  where plan_id is not null and plan_order is not null;

-- 10) task_blockers
create table if not exists task_blockers (
  task_id text not null,
  blocker_task_id text not null,
  partner_id text not null references partners(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (task_id, blocker_task_id),
  constraint fk_task_blockers_task
    foreign key (partner_id, task_id) references tasks(partner_id, id) on delete cascade,
  constraint fk_task_blockers_blocker
    foreign key (partner_id, blocker_task_id) references tasks(partner_id, id) on delete cascade,
  constraint chk_task_blockers_no_self
    check (task_id <> blocker_task_id)
);

create index if not exists idx_task_blockers_partner_task on task_blockers(partner_id, task_id);
create index if not exists idx_task_blockers_partner_blocker on task_blockers(partner_id, blocker_task_id);

-- 11) task_entities
create table if not exists task_entities (
  task_id text not null,
  entity_id text not null,
  partner_id text not null references partners(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (task_id, entity_id),
  constraint fk_task_entities_task
    foreign key (partner_id, task_id) references tasks(partner_id, id) on delete cascade,
  constraint fk_task_entities_entity
    foreign key (partner_id, entity_id) references entities(partner_id, id) on delete cascade
);

create index if not exists idx_task_entities_partner_entity on task_entities(partner_id, entity_id);
create index if not exists idx_task_entities_partner_task on task_entities(partner_id, task_id);

-- 12) usage_logs
create table if not exists usage_logs (
  id bigserial primary key,
  partner_id text not null references partners(id) on delete cascade,
  model text not null,
  tokens_in integer not null default 0,
  tokens_out integer not null default 0,
  created_at timestamptz not null default now(),
  constraint uq_usage_logs_partner_id_id unique (partner_id, id)
);

create index if not exists idx_usage_logs_partner_created_at
  on usage_logs(partner_id, created_at desc);

-- Migration assumptions / open items:
-- 1) This migration creates runtime schema only; data backfill/final sync scripts are separate.
-- 2) documents/protocols/blindspots do not include project_id in v1.
--    Repository layer must provide deterministic project-scope derivation joins.
-- 3) JSON payload schema validation is intentionally minimal (enum-like checks only),
--    keeping strict structural validation in import/repository code.
-- 4) A down migration is not included in this file; rollback is expected via backup/restore runbook.

commit;
