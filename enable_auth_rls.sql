
-- Run this ONLY when you switch AUTH_REQUIRED = "true".
-- It enables per-user security for the multi-user version.

alter table public.lockin_programs enable row level security;
alter table public.daily_lockin enable row level security;
alter table public.lockin_tasks enable row level security;
alter table public.workouts enable row level security;
alter table public.focus_sessions enable row level security;
alter table public.lockin_notes enable row level security;

drop policy if exists "own_programs" on public.lockin_programs;
create policy "own_programs" on public.lockin_programs
for all to authenticated
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

drop policy if exists "own_daily" on public.daily_lockin;
create policy "own_daily" on public.daily_lockin
for all to authenticated
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

drop policy if exists "own_tasks" on public.lockin_tasks;
create policy "own_tasks" on public.lockin_tasks
for all to authenticated
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

drop policy if exists "own_workouts" on public.workouts;
create policy "own_workouts" on public.workouts
for all to authenticated
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

drop policy if exists "own_focus" on public.focus_sessions;
create policy "own_focus" on public.focus_sessions
for all to authenticated
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

drop policy if exists "own_notes" on public.lockin_notes;
create policy "own_notes" on public.lockin_notes
for all to authenticated
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);
