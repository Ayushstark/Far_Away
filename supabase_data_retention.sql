-- CareOS Round 2: data retention and lifecycle completion signals.
-- Run this once in the Supabase SQL editor after supabase_schema_fix.sql.

alter table health_events
add column if not exists lifecycle_status text default 'active',
add column if not exists archived_at timestamptz,
add column if not exists deleted_at timestamptz,
add column if not exists restored_at timestamptz,
add column if not exists retention_reason text;

alter table reports
add column if not exists lifecycle_status text default 'active',
add column if not exists archived_at timestamptz,
add column if not exists deleted_at timestamptz,
add column if not exists restored_at timestamptz,
add column if not exists retention_reason text;

alter table medications
add column if not exists lifecycle_status text default 'active',
add column if not exists archived_at timestamptz,
add column if not exists deleted_at timestamptz,
add column if not exists restored_at timestamptz,
add column if not exists retention_reason text;

update health_events set lifecycle_status = 'active' where lifecycle_status is null;
update reports set lifecycle_status = 'active' where lifecycle_status is null;
update medications set lifecycle_status = 'active' where lifecycle_status is null;

create table if not exists data_lifecycle_events (
  id bigserial primary key,
  user_id int8 not null,
  family_member_id int8 null,
  target_table text not null,
  target_id int8 not null,
  action text not null,
  completion_status text not null,
  previous_status text,
  next_status text,
  reason text,
  error_message text,
  snapshot jsonb,
  created_at timestamptz default now(),
  completed_at timestamptz
);

create index if not exists idx_lifecycle_user
on data_lifecycle_events(user_id, created_at desc);

create index if not exists idx_lifecycle_target
on data_lifecycle_events(target_table, target_id, created_at desc);

create index if not exists idx_health_lifecycle
on health_events(user_id, family_member_id, lifecycle_status);

create index if not exists idx_reports_lifecycle
on reports(user_id, family_member_id, lifecycle_status);

create index if not exists idx_meds_lifecycle
on medications(user_id, family_member_id, lifecycle_status);
