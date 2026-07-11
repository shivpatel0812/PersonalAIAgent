-- Scope agent runs (research history / memory) per authenticated user

ALTER TABLE public.agent_runs
  ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default';

CREATE INDEX IF NOT EXISTS agent_runs_user_created_idx
  ON public.agent_runs (user_id, created_at DESC);

-- Vector similarity search scoped to a single user
CREATE OR REPLACE FUNCTION find_similar_runs(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.3,
  match_count int DEFAULT 3,
  filter_user_id text DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  question text,
  status text,
  final_answer text,
  created_at timestamptz,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    agent_runs.id,
    agent_runs.question,
    agent_runs.status,
    agent_runs.final_answer,
    agent_runs.created_at,
    1 - (agent_runs.embedding <=> query_embedding) AS similarity
  FROM agent_runs
  WHERE
    agent_runs.embedding IS NOT NULL
    AND agent_runs.status = 'completed'
    AND agent_runs.final_answer IS NOT NULL
    AND (filter_user_id IS NULL OR agent_runs.user_id = filter_user_id)
    AND 1 - (agent_runs.embedding <=> query_embedding) > match_threshold
  ORDER BY agent_runs.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
