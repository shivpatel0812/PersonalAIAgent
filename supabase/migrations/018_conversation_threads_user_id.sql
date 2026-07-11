-- Scope conversation threads per authenticated Supabase user

ALTER TABLE public.conversation_threads
  ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default';

CREATE INDEX IF NOT EXISTS conversation_threads_user_page_updated_idx
  ON public.conversation_threads (user_id, page_type, updated_at DESC);
