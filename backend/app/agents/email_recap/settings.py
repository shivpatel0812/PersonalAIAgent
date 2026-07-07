"""Hardcoded settings for the email recap agent."""

# Master switch
ENABLED = True

# Schedule (America/New_York) — (hour, minute, slot name)
SCHEDULE = [
    (9, 0, "morning"),   # 9:00 AM
    (12, 0, "noon"),     # 12:00 PM
    (17, 0, "evening"),  # 5:00 PM
    (23, 0, "night"),    # 11:00 PM
]
TIMEZONE = "America/New_York"

# How many recent inbox emails to scan per connected account
MAX_EMAILS_PER_ACCOUNT = 25

# Leave empty to send recap to the primary connected Gmail address
RECIPIENT_OVERRIDE = ""
