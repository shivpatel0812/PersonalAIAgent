-- Universal Find: sessions, messages, and feedback events

CREATE TABLE IF NOT EXISTS find_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL DEFAULT 'default',
    title TEXT,
    state JSONB NOT NULL DEFAULT '{}',
    clarification_rounds INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_find_sessions_user
    ON find_sessions(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS find_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES find_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_find_messages_session
    ON find_messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS find_feedback_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES find_sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    user_message TEXT,
    request_before JSONB,
    request_after JSONB,
    results_shown JSONB,
    search_query TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_find_feedback_session
    ON find_feedback_events(session_id, created_at DESC);

CREATE OR REPLACE FUNCTION update_find_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS find_sessions_updated_at ON find_sessions;
CREATE TRIGGER find_sessions_updated_at
    BEFORE UPDATE ON find_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_find_sessions_updated_at();
