-- CareOS: enable Row-Level Security as a defense-in-depth safety net.
--
-- The FastAPI backend talks to Supabase with the SERVICE ROLE key, which
-- always bypasses RLS - so nothing about how the app behaves today changes
-- after running this. What it does do: if the publishable/anon key (the one
-- key the browser ever sees) were ever used to query these tables directly -
-- by a bug, a future feature, or someone poking the API with dev tools - it
-- would see and touch only rows that belong to the signed-in Supabase Auth
-- user, instead of the whole table.
--
-- Safe to run once in the Supabase SQL editor, after supabase_schema_fix.sql
-- (which adds users.auth_user_id, the column every policy below relies on).
-- Re-running is safe: "drop policy if exists" then re-create.

alter table public.users enable row level security;
alter table public.family_members enable row level security;
alter table public.health_events enable row level security;
alter table public.medications enable row level security;
alter table public.reports enable row level security;
alter table public.data_lifecycle_events enable row level security;

-- users: a signed-in person can only see/edit their own row.
drop policy if exists "users_owner_all" on public.users;
create policy "users_owner_all"
on public.users
for all
using (auth_user_id = auth.uid())
with check (auth_user_id = auth.uid());

-- family_members: scoped to the owning user's own dependents.
drop policy if exists "family_members_owner_all" on public.family_members;
create policy "family_members_owner_all"
on public.family_members
for all
using (
  owner_id in (select id from public.users where auth_user_id = auth.uid())
)
with check (
  owner_id in (select id from public.users where auth_user_id = auth.uid())
);

-- health_events / medications / reports: scoped by user_id (the owner or
-- family member's record), same pattern for all three.
drop policy if exists "health_events_owner_all" on public.health_events;
create policy "health_events_owner_all"
on public.health_events
for all
using (
  user_id in (select id from public.users where auth_user_id = auth.uid())
)
with check (
  user_id in (select id from public.users where auth_user_id = auth.uid())
);

drop policy if exists "medications_owner_all" on public.medications;
create policy "medications_owner_all"
on public.medications
for all
using (
  user_id in (select id from public.users where auth_user_id = auth.uid())
)
with check (
  user_id in (select id from public.users where auth_user_id = auth.uid())
);

drop policy if exists "reports_owner_all" on public.reports;
create policy "reports_owner_all"
on public.reports
for all
using (
  user_id in (select id from public.users where auth_user_id = auth.uid())
)
with check (
  user_id in (select id from public.users where auth_user_id = auth.uid())
);

-- data_lifecycle_events: the audit trail, same owner scoping.
drop policy if exists "data_lifecycle_events_owner_all" on public.data_lifecycle_events;
create policy "data_lifecycle_events_owner_all"
on public.data_lifecycle_events
for all
using (
  user_id in (select id from public.users where auth_user_id = auth.uid())
)
with check (
  user_id in (select id from public.users where auth_user_id = auth.uid())
);

-- Note: the demo/seed owner (id 9000001, seeded by seed_data.py) has no
-- auth_user_id, so it is not reachable under any signed-in user's policy.
-- That's expected - the demo profile is only ever read/written through the
-- backend's service-role key, which RLS never restricts.
