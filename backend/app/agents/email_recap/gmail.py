"""Gmail helpers for the email recap agent."""

from __future__ import annotations

import base64
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pydantic import BaseModel

from app.google.email_safety import validate_outbound_email


class RecapEmail(BaseModel):
    account_email: str
    id: str
    message_id: str  # Gmail message ID
    thread_id: str  # Gmail thread ID for deduplication
    subject: str
    from_email: str
    from_name: str | None = None  # Extracted sender name
    date: str
    snippet: str
    is_unread: bool
    is_important: bool
    has_attachments: bool = False  # Whether email has attachments


def list_recap_candidates(
    credentials: Credentials,
    *,
    account_email: str,
    hours: int,
    max_results: int = 25,
) -> list[RecapEmail]:
    """Fetch recent inbox emails worth reviewing for a recap."""
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    query = (
        f"is:inbox newer_than:{hours}h "
        "-category:promotions -category:social -category:updates"
    )

    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results,
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

        # Extract sender name from "Name <email@domain.com>" format
        from_header = headers.get("From", "Unknown")
        from_name = None
        from_email = from_header

        # Try to parse "Name <email>" format
        match = re.match(r'^"?([^"<]+)"?\s*<(.+)>$', from_header)
        if match:
            from_name = match.group(1).strip()
            from_email = match.group(2).strip()
        else:
            # Just an email address
            from_email = from_header.strip()

        # Check for attachments
        has_attachments = False
        payload = message.get("payload", {})
        if "parts" in payload:
            for part in payload.get("parts", []):
                if part.get("filename"):
                    has_attachments = True
                    break

        emails.append(
            RecapEmail(
                account_email=account_email,
                id=message["id"],
                message_id=message["id"],
                thread_id=message.get("threadId", message["id"]),
                subject=headers.get("Subject", "(No subject)"),
                from_email=from_email,
                from_name=from_name,
                date=headers.get("Date", ""),
                snippet=message.get("snippet", ""),
                is_unread="UNREAD" in labels,
                is_important="IMPORTANT" in labels,
                has_attachments=has_attachments,
            )
        )

    return emails


def send_recap_email(
    credentials: Credentials,
    *,
    to: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send a plain-text recap email via Gmail."""
    allowed, error = validate_outbound_email(to=to)
    if not allowed:
        raise ValueError(error)

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = service.users().messages().send(
        userId="me",
        body={"raw": raw_message},
    ).execute()

    return sent


def send_html_recap_email(
    credentials: Credentials,
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> dict[str, Any]:
    """Send an HTML recap email via Gmail with plain text fallback."""
    allowed, error = validate_outbound_email(to=to)
    if not allowed:
        raise ValueError(error)

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    # Create multipart message
    message = MIMEMultipart("alternative")
    message["to"] = to
    message["subject"] = subject

    # Plain text fallback
    if text_body:
        part1 = MIMEText(text_body, "plain")
        message.attach(part1)

    # HTML content
    part2 = MIMEText(html_body, "html")
    message.attach(part2)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = service.users().messages().send(
        userId="me",
        body={"raw": raw_message},
    ).execute()

    return sent
