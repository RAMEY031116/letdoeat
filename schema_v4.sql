
-- LOCK IN 90 V3
-- Safe additive migration. Does not delete your existing data.

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

alter table public.lockin_programs add column if not exists calorie_target integer default 2200;
alter table public.lockin_programs add column if not exists protein_target integer default 150;
alter table public.lockin_programs add column if not exists study_target integer default 60;
alter table public.lockin_programs add column if not exists business_target integer default 45;
alter table public.lockin_programs add column if not exists art_target integer default 30;
alter table public.lockin_programs add column if not exists room_target integer default 15;
alter table public.lockin_programs add column if not exists wake_target time default '08:00';
alter table public.lockin_programs add column if not exists bed_target time default '23:00';

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
    study_minutes integer not null default 0,
    business_minutes integer not null default 0,
    art_minutes integer not null default 0,
    room_tidy boolean not null default false,
    bed_by_23 boolean not null default false,
    sleep_hours numeric(4,2) not null default 0,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id, log_date)
);

alter table public.daily_lockin add column if not exists calories_actual integer default 0;
alter table public.daily_lockin add column if not exists protein_actual integer default 0;

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

create table if not exists public.lockin_inbox (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    content text not null,
    category text not null default 'General',
    status text not null default 'open',
    created_at timestamptz not null default now()
);

create table if not exists public.weekly_reviews (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    week_start date not null,
    biggest_win text,
    friction text,
    next_focus text,
    rating integer check (rating between 1 and 10),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id, week_start)
);

create index if not exists idx_programs_user on public.lockin_programs(user_id);
create index if not exists idx_daily_user_date on public.daily_lockin(user_id, log_date);
create index if not exists idx_tasks_user_date on public.lockin_tasks(user_id, task_date);
create index if not exists idx_workouts_user_date on public.workouts(user_id, workout_date);
create index if not exists idx_focus_user_date on public.focus_sessions(user_id, session_date);
create index if not exists idx_inbox_user_status on public.lockin_inbox(user_id, status);
create index if not exists idx_weekly_reviews_user_week on public.weekly_reviews(user_id, week_start);

-- PRIVATE MODE FOR NOW
alter table public.lockin_programs disable row level security;
alter table public.daily_lockin disable row level security;
alter table public.lockin_tasks disable row level security;
alter table public.workouts disable row level security;
alter table public.focus_sessions disable row level security;
alter table public.lockin_inbox disable row level security;
alter table public.weekly_reviews disable row level security;


-- =========================================================
-- LOCKZILLA SHARED DATA ADDITIONS
-- iPhone + Streamlit compatibility
-- =========================================================

alter table public.lockin_tasks
add column if not exists task_end_time time null;

create table if not exists public.body_weights (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    log_date date not null,
    weight_kg numeric(6,2) not null check (weight_kg > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id, log_date)
);

create index if not exists idx_body_weights_user_date
on public.body_weights(user_id, log_date);

alter table public.focus_sessions
add column if not exists block_title text;

alter table public.focus_sessions
add column if not exists duration_minutes integer;

alter table public.focus_sessions
add column if not exists completed_at timestamptz;

alter table public.daily_lockin
add column if not exists daily_score integer
check (daily_score between 0 and 100);

create index if not exists idx_daily_lockin_score
on public.daily_lockin(user_id, log_date, daily_score);

-- Current private/no-login mode.
alter table public.body_weights disable row level security;
