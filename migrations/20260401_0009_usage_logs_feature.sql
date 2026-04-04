begin;

alter table zenos.usage_logs
  add column if not exists feature text not null default '';

create index if not exists idx_usage_logs_partner_feature_created_at
  on zenos.usage_logs(partner_id, feature, created_at desc);

commit;
