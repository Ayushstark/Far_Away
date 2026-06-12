-- Align the live Supabase tables with the CareOS owner-or-family data model.
-- Safe to run more than once in the Supabase SQL editor.

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'health_events'
      and column_name = 'famiily_member_id'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'health_events'
      and column_name = 'family_member_id'
  ) then
    alter table public.health_events
      rename column famiily_member_id to family_member_id;
  end if;
end $$;

alter table public.health_events
  alter column family_member_id drop not null;

alter table public.medications
  alter column family_member_id drop not null;
