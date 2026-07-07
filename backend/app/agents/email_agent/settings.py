"""Hardcoded settings for the Email Agent."""

ENABLED = True

# How often to scan inboxes for emails needing a reply (minutes)
SCAN_INTERVAL_MINUTES = 15

# Gmail search query for candidate messages
SCAN_QUERY = (
    "is:inbox is:unread -from:me "
    "-category:promotions -category:social -category:updates"
)

MAX_CANDIDATES_PER_ACCOUNT = 15
MAX_ACTIVE_QUEUE_SIZE = 20

WELCOME_CHAT_MESSAGE = (
    "I've drafted a reply based on the email thread. Tell me what to change — "
    "tone, length, or details to add — and I'll update the response below. "
    "Nothing sends until you approve."
)
