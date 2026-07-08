"""Hardcoded settings for the Email Agent."""

ENABLED = True

# How often to scan inboxes for emails needing a reply (minutes)
SCAN_INTERVAL_MINUTES = 15

# Only queue emails received within this many days
REPLY_MAX_AGE_DAYS = 14

# Gmail search query for candidate messages
SCAN_QUERY = (
    "is:inbox is:unread -from:me "
    "-category:promotions -category:social -category:updates "
    "-from:noreply -from:no-reply -from:notifications -from:verify "
    f"newer_than:{REPLY_MAX_AGE_DAYS}d"
)

MAX_CANDIDATES_PER_ACCOUNT = 15
MAX_ACTIVE_QUEUE_SIZE = 20

# Retry drafting for items stuck in needs_draft longer than this (minutes)
STUCK_DRAFT_RETRY_MINUTES = 2

# After this many failed draft attempts, discard the queue item
MAX_DRAFT_ATTEMPTS = 2

# Thread / prompt context limits
MAX_BODY_CHARS = 10_000
PER_MESSAGE_BODY_CHARS = 10_000
MAX_PROMPT_CHARS = 80_000
CLASSIFY_MAX_PROMPT_CHARS = 40_000

# Attachment / PDF extraction
MAX_PDFS_PER_MESSAGE = 3
MAX_PDF_PAGES = 20
MAX_PDF_BYTES = 50 * 1024
MAX_PDF_TEXT_CHARS = 8_000

# Middle-thread AI summarization (Phase 2)
MIDDLE_SUMMARY_ENABLED = True

# Cross-thread sender history (Phase 3)
SENDER_HISTORY_ENABLED = True
SENDER_HISTORY_MAX_THREADS = 5
SENDER_HISTORY_DAYS = 180
SENDER_HISTORY_MAX_CHARS = 12_000
SENDER_HISTORY_FULL_THREAD_ENABLED = True
SENDER_HISTORY_SUBJECT_MATCH_MIN_SCORE = 0.35
SENDER_HISTORY_MAX_FULL_THREADS = 2
SENDER_HISTORY_FULL_THREAD_MAX_CHARS = 6_000
SENDER_HISTORY_FULL_THREAD_MAX_MESSAGES = 8

# User profile, scheduling, sender intelligence (Phase 5–7)
SCHEDULING_DETECTION_ENABLED = True
SENDER_INTELLIGENCE_ENABLED = True
CALENDAR_AVAILABILITY_DAYS = 7
CALENDAR_BLOCK_MAX_CHARS = 1_500

WELCOME_CHAT_MESSAGE = (
    "I've drafted a reply based on the email thread. Tell me what to change — "
    "tone, length, or details to add — and I'll update the response below. "
    "Nothing sends until you approve."
)
