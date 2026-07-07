"""Detect inbound emails that need a human reply."""

from __future__ import annotations

import logging
import re

from googleapiclient.discovery import build

from app.agents.email_agent import settings as agent_settings
from app.agents.email_recap.gmail import RecapEmail
from app.agents.email_agent.filters import is_likely_automated
from app.agents.email_agent.json_utils import parse_json_response
from app.ai.openai_client import chat_messages
from app.ai.tools.gmail_tool import _fetch_thread_conversation
from app.google.oauth import load_credentials

logger = logging.getLogger(__name__)


def _parse_sender(from_header: str) -> tuple[str, str]:
    match = re.match(r'^"?([^"<]+)"?\s*<(.+)>$', from_header)
    if match:
        return match.group(1).strip(), match.group(2).strip().lower()
    return from_header.strip(), from_header.strip().lower()


def _is_from_user(from_email: str, account_email: str) -> bool:
    return _parse_sender(from_email)[1] == account_email.lower()


def list_reply_candidates(
    credentials,
    *,
    account_email: str,
    max_results: int | None = None,
) -> list[RecapEmail]:
    """Unread inbox messages that might need a reply."""
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    results = service.users().messages().list(
        userId="me",
        q=agent_settings.SCAN_QUERY,
        maxResults=max_results or agent_settings.MAX_CANDIDATES_PER_ACCOUNT,
    ).execute()

    emails: list[RecapEmail] = []
    for msg in results.get("messages", []):
        message = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()

        headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
        labels = message.get("labelIds", [])
        from_header = headers.get("From", "Unknown")
        from_name, from_email = _parse_sender(from_header)

        if is_likely_automated(
            from_email=from_email,
            subject=headers.get("Subject", "(No subject)"),
            snippet=message.get("snippet", ""),
        )[0]:
            continue

        emails.append(
            RecapEmail(
                account_email=account_email,
                id=message["id"],
                message_id=message["id"],
                subject=headers.get("Subject", "(No subject)"),
                from_email=from_email,
                from_name=from_name,
                date=headers.get("Date", ""),
                snippet=message.get("snippet", ""),
                is_unread="UNREAD" in labels,
                is_important="IMPORTANT" in labels,
            )
        )

    return emails


def email_needs_reply(
    *,
    account_email: str,
    subject: str,
    from_email: str,
    snippet: str,
    thread_summary: str,
) -> tuple[bool, str]:
    """Use AI to decide if this email needs a human-written reply."""
    system_prompt = """You decide whether an email needs a reply from the user.

Reply YES only when:
- A real person asked a question or requested action from the user
- A meeting, deadline, or decision clearly needs the user's response
- A personal or professional follow-up is expected

Reply NO for:
- Login alerts, security notices, verification codes, password resets
- GitHub/Vercel/deployment/CI notifications, receipts, shipping updates
- Newsletters, marketing, digests, automated system mail, FYI-only messages
- Anything where replying would go to a no-reply address or is not expected

When unsure, reply NO.

Return ONLY valid JSON:
{"needs_reply": true, "summary": "1-2 sentence summary of what they want"}
or
{"needs_reply": false, "summary": ""}
"""

    user_prompt = json.dumps(
        {
            "account_email": account_email,
            "from": from_email,
            "subject": subject,
            "snippet": snippet,
            "thread_excerpt": thread_summary[:3000],
        },
        indent=2,
    )

    try:
        response = chat_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=400,
        )
        result = parse_json_response(response)
        return bool(result.get("needs_reply")), str(result.get("summary", "")).strip()
    except Exception as exc:
        logger.warning("needs_reply classification failed: %s", exc)
        return False, ""


def build_thread_excerpt(credentials, thread_id: str) -> str:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    conversation = _fetch_thread_conversation(service, thread_id)
    lines = []
    for message in conversation.messages[-6:]:
        lines.append(
            f"From: {message.from_email}\n"
            f"Date: {message.date}\n"
            f"Subject: {message.subject}\n"
            f"{message.body[:1200]}\n"
        )
    return "\n---\n".join(lines)


def get_message_thread_id(credentials, message_id: str) -> str | None:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    message = service.users().messages().get(userId="me", id=message_id, format="minimal").execute()
    return message.get("threadId")


def latest_inbound_message_id(credentials, thread_id: str, account_email: str) -> str | None:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    conversation = _fetch_thread_conversation(service, thread_id)
    for message in reversed(conversation.messages):
        if not _is_from_user(message.from_email, account_email):
            return message.email_id
    return None
