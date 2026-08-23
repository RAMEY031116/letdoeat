
create extension if not exists pgcrypto;

create table if not exists public.lockin_programs (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    start_date date not null,
    end_date date not null,
    goal text,
    status text not null default 'active',
    created_at timestamptz not null default now()
);

create table if not exists public.daily_lockin (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    log_date date not null,
    wake_by_8 boolean not null default false,
    lunch_cardio boolean not null default false,
    evening_training boolean not null default false,
    cooked boolean not null default false,
    calorie_target_hit boolean not null default false,
    protein_target_hit boolean not null default false,
    study_minutes integer not null default 0 check (study_minutes >= 0),
    business_minutes integer not null default 0 check (business_minutes >= 0),
    art_minutes integer not null default 0 check (art_minutes >= 0),
    room_tidy boolean not null default false,
    bed_by_23 boolean not null default false,
    sleep_hours numeric(4,2) not null default 0 check (sleep_hours >= 0 and sleep_hours <= 24),
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id, log_date)
);

create table if not exists public.lockin_tasks (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    title text not null,
    notes text,
    priority text not null default 'Medium',
    task_date date not null,
    task_time time,
    category text not null default 'Personal',
    completed boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists public.workouts (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    workout_date date not null,
    session text not null,
    exercise text,
    sets integer not null default 0,
    reps integer not null default 0,
    weight numeric(8,2) not null default 0,
    duration_minutes integer not null default 0,
    notes text,
    created_at timestamptz not null default now()
);

create table if not exists public.focus_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    session_date date not null,
    focus_type text not null,
    minutes integer not null default 0,
    note text,
    created_at timestamptz not null default now()
);

create index if not exists idx_programs_user on public.lockin_programs(user_id);
create index if not exists idx_daily_user_date on public.daily_lockin(user_id, log_date);
create index if not exists idx_tasks_user_date on public.lockin_tasks(user_id, task_date);
create index if not exists idx_workouts_user_date on public.workouts(user_id, workout_date);
create index if not exists idx_focus_user_date on public.focus_sessions(user_id, session_date);

alter table public.lockin_programs disable row level security;
alter table public.daily_lockin disable row level security;
alter table public.lockin_tasks disable row level security;
alter table public.workouts disable row level security;
alter table public.focus_sessions disable row level security;
