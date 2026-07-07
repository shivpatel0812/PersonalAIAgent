-- Create google_accounts table for multi-account support
CREATE TABLE IF NOT EXISTS google_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    account_label TEXT,
    tokens JSONB NOT NULL,
    granted_scopes TEXT[] DEFAULT '{}',
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_google_accounts_email ON google_accounts(email);

-- Create index on is_primary to quickly find primary account
CREATE INDEX IF NOT EXISTS idx_google_accounts_primary ON google_accounts(is_primary) WHERE is_primary = true;

-- Ensure only one primary account at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_google_accounts_one_primary ON google_accounts(is_primary) WHERE is_primary = true;

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_google_accounts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_google_accounts_updated_at
    BEFORE UPDATE ON google_accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_google_accounts_updated_at();
