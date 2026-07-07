-- Email Agent: human-in-the-loop reply queue

CREATE TABLE IF NOT EXISTS email_agent_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT DEFAULT 'default',
    google_account_id UUID REFERENCES google_accounts(id) ON DELETE SET NULL,
    gmail_thread_id TEXT NOT NULL,
    gmail_message_id TEXT NOT NULL UNIQUE,
    sender_name TEXT,
    sender_email TEXT NOT NULL,
    subject TEXT,
    summary TEXT,
    draft_response TEXT,
    status TEXT NOT NULL DEFAULT 'needs_draft'
        CHECK (status IN ('needs_draft', 'draft_ready', 'waiting_on_you', 'approved', 'sent', 'discarded')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    sent_gmail_message_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_agent_items_status
    ON email_agent_items(status);

CREATE INDEX IF NOT EXISTS idx_email_agent_items_created
    ON email_agent_items(created_at DESC);

CREATE TABLE IF NOT EXISTS email_agent_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES email_agent_items(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_agent_chat_item
    ON email_agent_chat_messages(item_id, created_at);

CREATE OR REPLACE FUNCTION update_email_agent_items_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_email_agent_items_updated_at
    BEFORE UPDATE ON email_agent_items
    FOR EACH ROW
    EXECUTE FUNCTION update_email_agent_items_updated_at();
