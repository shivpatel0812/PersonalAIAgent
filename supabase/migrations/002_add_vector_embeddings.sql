-- Enable pgvector extension for vector similarity search
create extension if not exists vector;

-- Add embedding column (1536 dimensions for text-embedding-3-small)
alter table public.agent_runs add column embedding vector(1536);

-- Add metadata columns for tracking embedding generation
alter table public.agent_runs
  add column embedding_model text,
  add column embedding_generated_at timestamptz;

-- Create HNSW index for fast vector similarity search using cosine distance
-- HNSW (Hierarchical Navigable Small World) provides fast approximate nearest neighbor search
create index agent_runs_embedding_idx
  on public.agent_runs using hnsw (embedding vector_cosine_ops);

-- Add index for fallback queries (sorted by creation time)
create index agent_runs_created_at_idx
  on public.agent_runs(created_at desc);
