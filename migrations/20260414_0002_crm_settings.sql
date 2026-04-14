begin;

-- crm.settings: partner-level key-value config store for CRM features
create table if not exists crm.settings (
  partner_id text not null references zenos.partners(id) on delete cascade,
  key        text not null,
  value      jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (partner_id, key)
);

create index if not exists idx_crm_settings_partner on crm.settings(partner_id);

commit;
