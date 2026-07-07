"""Gmail helpers for the email recap agent."""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pydantic import BaseModel


class RecapEmail(BaseModel):
    account_email: str
    id: str
    subject: str
    from_email: str
    date: str
    snippet: str
    is_unread: bool
    is_important: bool


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

        emails.append(
            RecapEmail(
                account_email=account_email,
                id=message["id"],
                subject=headers.get("Subject", "(No subject)"),
                from_email=headers.get("From", "Unknown"),
                date=headers.get("Date", ""),
                snippet=message.get("snippet", ""),
                is_unread="UNREAD" in labels,
                is_important="IMPORTANT" in labels,
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
