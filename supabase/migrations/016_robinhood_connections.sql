-- Robinhood Agentic Trading MCP connection (OAuth tokens)

CREATE TABLE IF NOT EXISTS robinhood_oauth_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT DEFAULT 'default',
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, redirect_uri)
);

CREATE TABLE IF NOT EXISTS robinhood_oauth_states (
    state TEXT PRIMARY KEY,
    user_id TEXT DEFAULT 'default',
    code_verifier TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS robinhood_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT DEFAULT 'default',
    client_id TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ,
    scopes TEXT[] DEFAULT ARRAY['internal'],
    account_label TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_robinhood_connections_user
    ON robinhood_connections (user_id);
