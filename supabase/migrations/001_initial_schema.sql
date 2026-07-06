-- Run this in the Supabase SQL editor to create the initial schema.

create table if not exists public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  question text not null,
  status text not null default 'pending',
  final_answer text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agent_steps (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.agent_runs(id) on delete cascade,
  step_number integer not null,
  step_type text not null,
  content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists agent_steps_run_id_idx on public.agent_steps(run_id);

alter table public.agent_runs enable row level security;
alter table public.agent_steps enable row level security;

-- Dev-friendly policies: tighten these before production.
create policy "Allow anon read agent_runs"
  on public.agent_runs for select
  to anon, authenticated
  using (true);

create policy "Allow anon insert agent_runs"
  on public.agent_runs for insert
  to anon, authenticated
  with check (true);

create policy "Allow anon read agent_steps"
  on public.agent_steps for select
  to anon, authenticated
  using (true);

create policy "Allow anon insert agent_steps"
  on public.agent_steps for insert
  to anon, authenticated
  with check (true);
