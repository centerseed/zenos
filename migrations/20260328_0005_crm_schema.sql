begin;

-- 1. Expand zenos.entities type check constraint to include CRM types
alter table zenos.entities
  drop constraint if exists chk_entities_type;

alter table zenos.entities
  add constraint chk_entities_type
  check (type in (
    'product', 'module', 'goal', 'role', 'project', 'document',
    'company', 'person'
  ));

-- 2. Create crm schema
create schema if not exists crm;

-- 3. crm.companies
create table if not exists crm.companies (
  id              text primary key,
  partner_id      text not null references zenos.partners(id) on delete cascade,
  name            text not null,
  industry        text,
  size_range      text,   -- '1-10' | '11-50' | '51-200' | '200+'
  region          text,
  notes           text,
  zenos_entity_id text,   -- nullable; soft ref to zenos.entities.id
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index if not exists idx_crm_companies_partner on crm.companies(partner_id);
create index if not exists idx_crm_companies_name    on crm.companies(partner_id, name);

-- 4. crm.contacts
create table if not exists crm.contacts (
  id              text primary key,
  partner_id      text not null references zenos.partners(id) on delete cascade,
  company_id      text not null references crm.companies(id) on delete cascade,
  name            text not null,
  title           text,
  email           text,
  phone           text,
  notes           text,
  zenos_entity_id text,   -- nullable; soft ref to zenos.entities.id
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index if not exists idx_crm_contacts_partner on crm.contacts(partner_id);
create index if not exists idx_crm_contacts_company on crm.contacts(partner_id, company_id);

-- 5. crm.deals
create table if not exists crm.deals (
  id                  text primary key,
  partner_id          text not null references zenos.partners(id) on delete cascade,
  title               text not null,
  company_id          text not null references crm.companies(id),
  owner_partner_id    text not null references zenos.partners(id),
  funnel_stage        text not null default '潛在客戶',
  amount_twd          integer,
  deal_type           text,
  source_type         text,
  referrer            text,
  expected_close_date date,
  signed_date         date,
  scope_description   text,
  deliverables        text[] not null default '{}'::text[],
  notes               text,
  is_closed_lost      boolean not null default false,
  is_on_hold          boolean not null default false,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint chk_deals_funnel_stage check (funnel_stage in (
    '潛在客戶', '需求訪談', '提案報價', '合約議價', '導入中', '結案'
  )),
  constraint chk_deals_deal_type check (deal_type is null or deal_type in (
    '一次性專案', '顧問合約', 'Retainer'
  )),
  constraint chk_deals_source_type check (source_type is null or source_type in (
    '轉介紹', '自開發', '合作夥伴', '社群', '活動'
  ))
);
create index if not exists idx_crm_deals_partner on crm.deals(partner_id);
create index if not exists idx_crm_deals_company on crm.deals(partner_id, company_id);
create index if not exists idx_crm_deals_stage   on crm.deals(partner_id, funnel_stage);
create index if not exists idx_crm_deals_owner   on crm.deals(partner_id, owner_partner_id);

-- 6. crm.activities
create table if not exists crm.activities (
  id            text primary key,
  partner_id    text not null references zenos.partners(id) on delete cascade,
  deal_id       text not null references crm.deals(id) on delete cascade,
  activity_type text not null,
  activity_at   timestamptz not null default now(),
  summary       text not null,
  recorded_by   text not null references zenos.partners(id),
  is_system     boolean not null default false,
  created_at    timestamptz not null default now(),
  constraint chk_activities_type check (activity_type in (
    '電話', 'Email', '會議', 'Demo', '備忘', '系統'
  ))
);
create index if not exists idx_crm_activities_deal    on crm.activities(deal_id);
create index if not exists idx_crm_activities_partner on crm.activities(partner_id);

commit;
