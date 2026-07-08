-- Microsoft / Outlook OAuth accounts
CREATE TABLE IF NOT EXISTS microsoft_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    account_label TEXT,
    tokens JSONB NOT NULL,
    granted_scopes TEXT[],
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_microsoft_accounts_primary
    ON microsoft_accounts (is_primary)
    WHERE is_primary = TRUE;
