-- CareOS: allow archiving or removing a family member profile.
-- Run this once in the Supabase SQL editor after supabase_data_retention.sql.

alter table family_members
add column if not exists lifecycle_status text default 'active',
add column if not exists retention_reason text;

update family_members set lifecycle_status = 'active' where lifecycle_status is null;

create index if not exists idx_family_lifecycle
on family_members(owner_id, lifecycle_status);
