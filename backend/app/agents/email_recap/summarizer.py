"""AI summarization for email recaps."""

from __future__ import annotations

import json

from app.agents.email_recap.gmail import RecapEmail
from app.ai.openai_client import chat_messages


def _format_emails_for_prompt(emails: list[RecapEmail]) -> str:
    payload = [
        {
            "account": e.account_email,
            "from": e.from_email,
            "subject": e.subject,
            "date": e.date,
            "snippet": e.snippet,
            "unread": e.is_unread,
            "important": e.is_important,
        }
        for e in emails
    ]
    return json.dumps(payload, indent=2)


def summarize_email_recap(
    *,
    slot: str,
    emails: list[RecapEmail],
    account_emails: list[str],
) -> str:
    """Turn raw email metadata into a readable recap email body."""
    slot_labels = {
        "morning": "morning",
        "noon": "afternoon",
        "evening": "evening",
        "night": "evening",
    }
    greeting = slot_labels.get(slot, "day")

    if not emails:
        accounts = ", ".join(account_emails) if account_emails else "your inbox"
        return (
            f"Good {greeting}!\n\n"
            f"No notable new emails in {accounts} since the last check.\n\n"
            "You're all caught up."
        )

    display_labels = {
        "morning": "Morning",
        "noon": "Midday",
        "evening": "Evening",
        "night": "Night",
    }
    slot_label = display_labels.get(slot, "Email")
    system_prompt = f"""You are a personal executive assistant writing a {slot_label.lower()} email recap.

Review the JSON list of recent emails and write a concise plain-text email body for the user.

Rules:
- Lead with emails that need a reply, decision, or time-sensitive action
- Group into sections: "Needs attention", "Worth reading", "FYI" (skip empty sections)
- Use bullet points with sender, subject, and a one-line why-it-matters note
- Ignore obvious newsletters, receipts, and automated notifications unless urgent
- Keep the whole recap under 400 words
- Do not invent emails — only use what is in the data
- End with a short encouraging sign-off"""

    user_prompt = (
        f"Connected accounts: {', '.join(account_emails)}\n"
        f"Recap slot: {slot_label}\n"
        f"Email count: {len(emails)}\n\n"
        f"Emails:\n{_format_emails_for_prompt(emails)}"
    )

    return chat_messages(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1200,
    )
