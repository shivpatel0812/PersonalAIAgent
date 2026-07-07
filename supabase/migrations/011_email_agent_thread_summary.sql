-- Cache AI summary of omitted middle messages in long threads
ALTER TABLE email_agent_items
    ADD COLUMN IF NOT EXISTS thread_context_summary TEXT;
