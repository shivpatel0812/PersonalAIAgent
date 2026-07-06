-- Persistent conversation threads, one per research page type.

create table if not exists public.conversation_threads (
  id uuid primary key default gen_random_uuid(),
  page_type text not null unique,
  title text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.conversation_messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references public.conversation_threads(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  steps jsonb not null default '[]'::jsonb,
  run_id uuid references public.agent_runs(id) on delete set null,
  source text not null default 'user' check (source in ('user', 'agent', 'automation')),
  created_at timestamptz not null default now()
);

create index if not exists conversation_messages_thread_id_idx
  on public.conversation_messages(thread_id);

create index if not exists conversation_messages_created_at_idx
  on public.conversation_messages(thread_id, created_at);

alter table public.conversation_threads enable row level security;
alter table public.conversation_messages enable row level security;

create policy "Allow anon read conversation_threads"
  on public.conversation_threads for select
  to anon, authenticated
  using (true);

create policy "Allow anon insert conversation_threads"
  on public.conversation_threads for insert
  to anon, authenticated
  with check (true);

create policy "Allow anon update conversation_threads"
  on public.conversation_threads for update
  to anon, authenticated
  using (true);

create policy "Allow anon read conversation_messages"
  on public.conversation_messages for select
  to anon, authenticated
  using (true);

create policy "Allow anon insert conversation_messages"
  on public.conversation_messages for insert
  to anon, authenticated
  with check (true);

-- Seed one thread per page type.
insert into public.conversation_threads (page_type, title)
values
  ('stocks', 'Stock Research'),
  ('personal', 'Personal Assistant'),
  ('general', 'General Research')
on conflict (page_type) do nothing;
