"""Detect inbound emails that need a human reply."""

from __future__ import annotations

import logging
import re

from googleapiclient.discovery import build

from app.agents.email_agent import settings as agent_settings
from app.agents.email_recap.gmail import RecapEmail
from app.agents.email_agent.filters import is_likely_automated
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
    return _list_candidates(
        credentials,
        account_email=account_email,
        query=agent_settings.SCAN_QUERY,
        max_results=max_results,
    )


def list_browse_candidates(
    credentials,
    *,
    account_email: str,
    max_results: int | None = None,
) -> list[RecapEmail]:
    """Recent inbox messages for the browse tier (read + unread)."""
    return _list_candidates(
        credentials,
        account_email=account_email,
        query=agent_settings.BROWSE_SCAN_QUERY,
        max_results=max_results,
    )


def _list_candidates(
    credentials,
    *,
    account_email: str,
    query: str,
    max_results: int | None = None,
) -> list[RecapEmail]:
    """Inbox messages matching a Gmail search query."""
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    results = service.users().messages().list(
        userId="me",
        q=query,
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
