-- Create function for vector similarity search
-- Returns agent runs similar to the query embedding based on cosine similarity
create or replace function find_similar_runs(
  query_embedding vector(1536),
  match_threshold float default 0.3,
  match_count int default 3
)
returns table (
  id uuid,
  question text,
  status text,
  final_answer text,
  created_at timestamptz,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    agent_runs.id,
    agent_runs.question,
    agent_runs.status,
    agent_runs.final_answer,
    agent_runs.created_at,
    1 - (agent_runs.embedding <=> query_embedding) as similarity
  from agent_runs
  where
    agent_runs.embedding is not null
    and agent_runs.status = 'completed'
    and agent_runs.final_answer is not null
    and 1 - (agent_runs.embedding <=> query_embedding) > match_threshold
  order by agent_runs.embedding <=> query_embedding
  limit match_count;
end;
$$;
