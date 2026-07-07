"""Gmail send helpers for Email Agent replies."""

from __future__ import annotations

import base64
import re
from email.mime.text import MIMEText
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.ai.tools.gmail_tool import _fetch_thread_conversation, _headers_from_message
from app.google.email_safety import validate_outbound_email


def _normalize_email(address: str) -> str:
    address = address.strip()
    match = re.search(r"<([^>]+)>", address)
    if match:
        return match.group(1).lower().strip()
    return address.lower().strip()


def thread_participant_emails(thread_id: str, credentials: Credentials) -> set[str]:
    """Collect normalized emails from everyone in a Gmail thread."""
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    conversation = _fetch_thread_conversation(service, thread_id)
    participants: set[str] = set()

    for message in conversation.messages:
        if message.from_email:
            participants.add(_normalize_email(message.from_email))
        if message.to_email:
            for part in message.to_email.split(","):
                if part.strip():
                    participants.add(_normalize_email(part))

    return participants


def send_thread_reply(
    credentials: Credentials,
    *,
    to: str,
    subject: str,
    body: str,
    thread_id: str,
    reply_to_email_id: str,
    cc: str = "",
    allowed_recipients: set[str] | None = None,
) -> dict[str, Any]:
    """Send a reply in an existing Gmail thread."""
    allowed, error = validate_outbound_email(
        to=to,
        cc=cc,
        allowed_extra_recipients=allowed_recipients,
    )
    if not allowed:
        raise ValueError(error)

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    if cc:
        message["cc"] = cc

    original = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=reply_to_email_id,
            format="metadata",
            metadataHeaders=["Message-ID", "References", "Subject"],
        )
        .execute()
    )
    orig_headers = _headers_from_message(original)
    message_id = orig_headers.get("Message-ID")
    if message_id:
        message["In-Reply-To"] = message_id
        references = orig_headers.get("References", "")
        message["References"] = f"{references} {message_id}".strip()

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = (
        service.users()
        .messages()
        .send(
            userId="me",
            body={"raw": raw_message, "threadId": thread_id},
        )
        .execute()
    )
    return sent
