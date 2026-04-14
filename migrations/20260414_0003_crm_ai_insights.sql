begin;

create table if not exists crm.ai_insights (
  id           text primary key,
  partner_id   text not null references zenos.partners(id) on delete cascade,
  deal_id      text not null,
  activity_id  text,
  insight_type text not null,
  content      text not null default '',
  metadata     jsonb not null default '{}'::jsonb,
  status       text not null default 'active',
  created_at   timestamptz not null default now(),

  constraint chk_insight_type check (insight_type in ('briefing', 'debrief', 'commitment')),
  constraint chk_insight_status check (status in ('active', 'open', 'done', 'archived'))
);

create index if not exists idx_ai_insights_deal on crm.ai_insights(partner_id, deal_id);
create index if not exists idx_ai_insights_type on crm.ai_insights(partner_id, deal_id, insight_type);
create index if not exists idx_ai_insights_activity on crm.ai_insights(partner_id, activity_id) where activity_id is not null;

commit;
