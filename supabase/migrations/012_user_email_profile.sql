-- Global user profile for Email Agent reply preferences
CREATE TABLE IF NOT EXISTS user_email_profiles (
    user_id TEXT PRIMARY KEY DEFAULT 'default',
    display_name TEXT,
    role_title TEXT,
    communication_style TEXT,
    default_sign_off TEXT,
    expertise_areas TEXT[],
    timezone TEXT DEFAULT 'America/Los_Angeles',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE email_agent_items
    ADD COLUMN IF NOT EXISTS draft_context_meta JSONB;
