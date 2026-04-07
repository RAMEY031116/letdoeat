create table if not exists public.tasks (
    id bigint generated always as identity primary key,
    title text not null,
    notes text,
    priority text not null default 'Medium',
    task_date date not null,
    task_time time,
    is_work boolean not null default false,
    is_personal boolean not null default true,
    completed boolean not null default false,
    created_at timestamp with time zone not null default now()
);

alter table public.tasks
drop constraint if exists tasks_priority_check;

alter table public.tasks
add constraint tasks_priority_check
check (priority in ('High', 'Medium', 'Low'));
