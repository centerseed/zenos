begin;

alter table zenos.usage_logs
  add column if not exists outcome text not null default 'success';

create index if not exists idx_usage_logs_partner_model_outcome_created_at
  on zenos.usage_logs(partner_id, model, outcome, created_at desc);

commit;
