"""Heuristics to skip automated / notification emails before AI classification."""

from __future__ import annotations

import re

# Local-parts that almost never expect a human reply
AUTOMATED_LOCALPARTS = (
    "noreply",
    "no-reply",
    "no_reply",
    "donotreply",
    "do-not-reply",
    "notifications",
    "notification",
    "notify",
    "verify",
    "verification",
    "security",
    "alert",
    "alerts",
    "mailer-daemon",
    "postmaster",
    "bounce",
    "newsletter",
    "news",
    "updates",
    "info",
)

# Sender domains that are typically automated for this product
AUTOMATED_DOMAINS = (
    "github.com",
    "vercel.com",
    "google.com",
    "googlemail.com",
    "fitbit.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "facebookmail.com",
    "amazonses.com",
    "sendgrid.net",
    "mailchimp.com",
    "stripe.com",
    "slack.com",
    "notion.so",
    "atlassian.com",
    "jira.com",
    "linear.app",
    "supabase.com",
    "railway.app",
    "sentry.io",
    "datadoghq.com",
)

# Subject/snippet phrases that indicate FYI / security / transactional mail
AUTOMATED_SUBJECT_PATTERNS = re.compile(
    r"\b("
    r"new login|logged in|sign[- ]in|security alert|verify your|verification code|"
    r"confirm your email|password reset|two[- ]factor|2fa|"
    r"deployment (ready|failed|succeeded)|build (failed|succeeded)|"
    r"pull request|merged pull request|issue opened|workflow run|"
    r"receipt|order confirmation|shipping confirmation|"
    r"unsubscribe|newsletter|digest|"
    r"no[- ]reply|do not reply"
    r")\b",
    re.IGNORECASE,
)


def _normalize_email(email: str) -> str:
    email = email.strip().lower()
    match = re.search(r"<([^>]+)>", email)
    if match:
        email = match.group(1).strip().lower()
    return email


def is_likely_automated(
    *,
    from_email: str,
    subject: str,
    snippet: str = "",
) -> tuple[bool, str]:
    """
    Return (should_skip, reason).

    Fast pre-filter before Gmail thread loads and OpenAI calls.
    """
    email = _normalize_email(from_email)
    if "@" not in email:
        return False, ""

    local, domain = email.rsplit("@", 1)

    if local in AUTOMATED_LOCALPARTS or local.startswith("noreply"):
        return True, f"automated sender local-part: {local}"

    for blocked_domain in AUTOMATED_DOMAINS:
        if domain == blocked_domain or domain.endswith(f".{blocked_domain}"):
            return True, f"automated sender domain: {domain}"

    combined = f"{subject} {snippet}"
    if AUTOMATED_SUBJECT_PATTERNS.search(combined):
        return True, "automated subject/snippet pattern"

    return False, ""
