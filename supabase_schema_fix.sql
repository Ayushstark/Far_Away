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

update public.users
set age = 0
where age is null;

alter table public.users
  alter column age set not null;

-- Pair Supabase Auth accounts with the existing bigint CareOS user profiles.
alter table public.users
  add column if not exists auth_user_id uuid unique references auth.users(id) on delete cascade,
  add column if not exists email text,
  add column if not exists emergency_contacts text,
  add column if not exists emergency_contact text;

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'users'
      and column_name = 'emergency_contact'
  ) then
    update public.users
    set emergency_contacts = coalesce(emergency_contacts, emergency_contact, '')
    where emergency_contacts is null or emergency_contacts = '';
  end if;
end $$;

update public.users
set
  name = coalesce(name, ''),
  gender = coalesce(gender, ''),
  blood_group = coalesce(blood_group, ''),
  emergency_contacts = coalesce(emergency_contacts, '')
where name is null
   or gender is null
   or blood_group is null
   or emergency_contacts is null;

alter table public.users
  alter column name set not null,
  alter column gender set not null,
  alter column blood_group set not null,
  alter column emergency_contacts set not null;

-- The deployed API sends these as text[] because Supabase exposes them as arrays.
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'users'
      and column_name = 'known_conditions'
      and data_type <> 'ARRAY'
  ) then
    alter table public.users
      alter column known_conditions type text[]
      using case
        when known_conditions is null or known_conditions = '' then '{}'::text[]
        else string_to_array(known_conditions, ',')
      end;
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'users'
      and column_name = 'allergies'
      and data_type <> 'ARRAY'
  ) then
    alter table public.users
      alter column allergies type text[]
      using case
        when allergies is null or allergies = '' then '{}'::text[]
        else string_to_array(allergies, ',')
      end;
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'family_members'
      and column_name = 'known_conditions'
      and data_type <> 'ARRAY'
  ) then
    alter table public.family_members
      alter column known_conditions type text[]
      using case
        when known_conditions is null or known_conditions = '' then '{}'::text[]
        else string_to_array(known_conditions, ',')
      end;
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'medications'
      and column_name = 'timing'
      and data_type <> 'ARRAY'
  ) then
    alter table public.medications
      alter column timing type text[]
      using case
        when timing is null or timing = '' then '{}'::text[]
        else string_to_array(timing, ',')
      end;
  end if;
end $$;

update public.users
set
  known_conditions = coalesce(known_conditions, '{}'::text[]),
  allergies = coalesce(allergies, '{}'::text[]);

alter table public.users
  alter column known_conditions set default '{}'::text[],
  alter column allergies set default '{}'::text[],
  alter column known_conditions set not null,
  alter column allergies set not null;

update public.family_members
set known_conditions = coalesce(known_conditions, '{}'::text[]);

alter table public.family_members
  alter column known_conditions set default '{}'::text[];

update public.medications
set timing = coalesce(timing, '{}'::text[]);

alter table public.medications
  alter column timing set default '{}'::text[];
