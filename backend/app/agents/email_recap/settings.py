"""Hardcoded settings for the email recap agent."""

# Master switch
ENABLED = True

# Schedule (America/New_York)
TIMEZONE = "America/New_York"
MORNING_HOUR = 0
MORNING_MINUTE = 39
EVENING_HOUR = 17
EVENING_MINUTE = 0

# How many recent inbox emails to scan per connected account
MAX_EMAILS_PER_ACCOUNT = 25

# Leave empty to send recap to the primary connected Gmail address
RECIPIENT_OVERRIDE = ""
