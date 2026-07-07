-- Allow multiple conversation threads per page type (chat tabs).

alter table public.conversation_threads
  drop constraint if exists conversation_threads_page_type_key;

create index if not exists conversation_threads_page_type_updated_idx
  on public.conversation_threads (page_type, updated_at desc);

create policy "Allow anon delete conversation_threads"
  on public.conversation_threads for delete
  to anon, authenticated
  using (true);
