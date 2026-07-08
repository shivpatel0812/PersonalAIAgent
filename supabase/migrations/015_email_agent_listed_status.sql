-- Allow browse-tier emails without a pre-generated draft
ALTER TABLE email_agent_items DROP CONSTRAINT IF EXISTS email_agent_items_status_check;

ALTER TABLE email_agent_items
    ADD CONSTRAINT email_agent_items_status_check
    CHECK (status IN (
        'needs_draft',
        'draft_ready',
        'waiting_on_you',
        'listed',
        'approved',
        'sent',
        'discarded'
    ));
