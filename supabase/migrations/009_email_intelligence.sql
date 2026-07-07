-- Email Intelligence System
-- Tracks user interactions with emails and learns preferences

-- Store email ratings from digest
CREATE TABLE IF NOT EXISTS email_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    email_id TEXT NOT NULL,
    gmail_message_id TEXT,
    sender TEXT NOT NULL,
    subject TEXT,
    stars INTEGER NOT NULL CHECK (stars >= 1 AND stars <= 5),
    rated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Help identify patterns
    email_category TEXT,
    keywords TEXT[]
);

-- Store email interaction events (opens, replies, archives)
CREATE TABLE IF NOT EXISTS email_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    email_id TEXT NOT NULL,
    gmail_message_id TEXT,
    sender TEXT NOT NULL,
    subject TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN ('received', 'opened', 'replied', 'archived', 'starred', 'deleted')),
    event_timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Additional context
    response_time_minutes INTEGER,
    in_digest BOOLEAN DEFAULT false
);

-- Computed sender priorities (updated weekly)
CREATE TABLE IF NOT EXISTS sender_priorities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    sender TEXT NOT NULL,

    -- Metrics
    avg_star_rating DECIMAL(3,2),
    total_ratings INTEGER DEFAULT 0,
    reply_rate DECIMAL(5,4),
    open_rate DECIMAL(5,4),
    avg_response_time_minutes INTEGER,

    -- Computed priority score (-1 to 1)
    priority_score DECIMAL(3,2) DEFAULT 0,

    -- Auto-actions
    auto_archive BOOLEAN DEFAULT false,
    always_urgent BOOLEAN DEFAULT false,

    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, sender)
);

-- Store digest history
CREATE TABLE IF NOT EXISTS email_digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    total_emails_processed INTEGER,
    urgent_count INTEGER,
    medium_count INTEGER,
    low_count INTEGER,
    auto_archived_count INTEGER,
    opened BOOLEAN DEFAULT false,
    opened_at TIMESTAMPTZ
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_email_ratings_sender ON email_ratings(sender);
CREATE INDEX IF NOT EXISTS idx_email_ratings_stars ON email_ratings(stars);
CREATE INDEX IF NOT EXISTS idx_email_ratings_user ON email_ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_email_events_sender ON email_events(sender);
CREATE INDEX IF NOT EXISTS idx_email_events_type ON email_events(event_type);
CREATE INDEX IF NOT EXISTS idx_email_events_user ON email_events(user_id);
CREATE INDEX IF NOT EXISTS idx_sender_priorities_user ON sender_priorities(user_id);
CREATE INDEX IF NOT EXISTS idx_sender_priorities_score ON sender_priorities(priority_score DESC);

-- Function to update sender priorities (called weekly)
CREATE OR REPLACE FUNCTION update_sender_priorities()
RETURNS void AS $$
BEGIN
    INSERT INTO sender_priorities (user_id, sender, avg_star_rating, total_ratings, reply_rate, open_rate, priority_score)
    SELECT
        r.user_id,
        r.sender,
        AVG(r.stars) as avg_star_rating,
        COUNT(*) as total_ratings,
        -- Reply rate from events
        COALESCE(
            (SELECT COUNT(*)::DECIMAL / NULLIF(COUNT(DISTINCT e1.email_id), 0)
             FROM email_events e1
             WHERE e1.sender = r.sender
             AND e1.event_type = 'replied'
             AND e1.user_id = r.user_id),
            0
        ) as reply_rate,
        -- Open rate from events
        COALESCE(
            (SELECT COUNT(*)::DECIMAL / NULLIF(COUNT(DISTINCT e2.email_id), 0)
             FROM email_events e2
             WHERE e2.sender = r.sender
             AND e2.event_type = 'opened'
             AND e2.user_id = r.user_id),
            0
        ) as open_rate,
        -- Priority score: (avg_stars - 3) / 2 + reply_rate
        -- Range: -1 (never read, 1 star) to +1 (always reply, 5 stars)
        ((AVG(r.stars) - 3) / 2.0) +
        COALESCE(
            (SELECT COUNT(*)::DECIMAL / NULLIF(COUNT(DISTINCT e3.email_id), 0)
             FROM email_events e3
             WHERE e3.sender = r.sender
             AND e3.event_type = 'replied'
             AND e3.user_id = r.user_id) * 0.3,
            0
        ) as priority_score
    FROM email_ratings r
    GROUP BY r.user_id, r.sender
    ON CONFLICT (user_id, sender)
    DO UPDATE SET
        avg_star_rating = EXCLUDED.avg_star_rating,
        total_ratings = EXCLUDED.total_ratings,
        reply_rate = EXCLUDED.reply_rate,
        open_rate = EXCLUDED.open_rate,
        priority_score = EXCLUDED.priority_score,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;
