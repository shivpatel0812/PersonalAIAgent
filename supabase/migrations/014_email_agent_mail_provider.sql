-- Support Microsoft Outlook alongside Gmail in Email Agent
ALTER TABLE email_agent_items
    ADD COLUMN IF NOT EXISTS mail_provider TEXT DEFAULT 'google'
        CHECK (mail_provider IN ('google', 'microsoft'));

ALTER TABLE email_agent_items
    ADD COLUMN IF NOT EXISTS microsoft_account_id UUID
        REFERENCES microsoft_accounts(id) ON DELETE SET NULL;
