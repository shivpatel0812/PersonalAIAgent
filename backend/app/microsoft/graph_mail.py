"""Microsoft Graph mail operations for Email Agent."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.agents.email_agent import settings as agent_settings
from app.ai.tools.gmail_tool import (
    AttachmentInfo,
    EmailThreadConversation,
    ThreadMessage,
    _html_to_text,
    _truncate_body,
)

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MAX_THREAD_MESSAGES = 50


def _graph_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _email_address(value: dict[str, Any] | None) -> str:
    if not value:
        return "unknown@unknown"
    return (value.get("address") or "unknown@unknown").strip().lower()


def _parse_address(value: dict[str, Any] | None) -> str:
    if not value:
        return "Unknown"
    name = (value.get("name") or "").strip()
    address = (value.get("address") or "").strip()
    if name and address:
        return f"{name} <{address}>"
    return address or name or "Unknown"


def _message_body_text(message: dict[str, Any]) -> str:
    body = message.get("body") or {}
    content = body.get("content") or ""
    if body.get("contentType", "").lower() == "html":
        return _html_to_text(content)
    return content


def _attachments_from_message(message: dict[str, Any]) -> list[AttachmentInfo]:
    attachments: list[AttachmentInfo] = []
    for item in message.get("attachments") or []:
        if item.get("@odata.type") == "#microsoft.graph.itemAttachment":
            continue
        filename = (item.get("name") or "").strip()
        if not filename:
            continue
        attachments.append(
            AttachmentInfo(
                filename=filename,
                mime_type=item.get("contentType") or "application/octet-stream",
                size_bytes=int(item.get("size") or 0),
                attachment_id=item.get("id") or "",
            )
        )
    return attachments


def fetch_thread_conversation(
    access_token: str,
    conversation_id: str,
) -> EmailThreadConversation:
    params = {
        "$filter": f"conversationId eq '{conversation_id}'",
        "$orderby": "receivedDateTime asc",
        "$top": str(MAX_THREAD_MESSAGES),
        "$expand": "attachments",
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(
            f"{GRAPH_BASE}/me/messages",
            headers=_graph_headers(access_token),
            params=params,
        )
        response.raise_for_status()
        raw_messages = response.json().get("value", [])

    if len(raw_messages) > MAX_THREAD_MESSAGES:
        raw_messages = raw_messages[-MAX_THREAD_MESSAGES:]

    messages: list[ThreadMessage] = []
    subject = "(No subject)"
    for msg in raw_messages:
        msg_subject = msg.get("subject") or "(No subject)"
        if subject == "(No subject)":
            subject = msg_subject
        from_email = _parse_address((msg.get("from") or {}).get("emailAddress"))
        to_recipients = msg.get("toRecipients") or []
        to_email = ", ".join(
            _parse_address(recipient.get("emailAddress")) for recipient in to_recipients
        )
        messages.append(
            ThreadMessage(
                email_id=msg["id"],
                from_email=from_email,
                to_email=to_email or None,
                date=msg.get("receivedDateTime") or msg.get("sentDateTime") or "",
                subject=msg_subject,
                body=_truncate_body(_message_body_text(msg)),
                snippet=(msg.get("bodyPreview") or "")[:200],
                attachments=_attachments_from_message(msg),
            )
        )

    return EmailThreadConversation(
        thread_id=conversation_id,
        subject=subject,
        message_count=len(messages),
        messages=messages,
    )


def list_unread_inbox_candidates(
    access_token: str,
    *,
    account_email: str,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    max_results = max_results or agent_settings.MAX_CANDIDATES_PER_ACCOUNT
    params = {
        "$filter": "isRead eq false",
        "$orderby": "receivedDateTime desc",
        "$top": str(max_results),
        "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,conversationId,isRead",
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.get(
            f"{GRAPH_BASE}/me/mailFolders/inbox/messages",
            headers=_graph_headers(access_token),
            params=params,
        )
        response.raise_for_status()
        items = response.json().get("value", [])

    candidates: list[dict[str, Any]] = []
    account_lower = account_email.lower()
    for item in items:
        from_email = _email_address((item.get("from") or {}).get("emailAddress"))
        from_display = _parse_address((item.get("from") or {}).get("emailAddress"))
        from_lower = from_email
        if account_lower in from_lower:
            continue
        candidates.append(
            {
                "message_id": item["id"],
                "thread_id": item.get("conversationId") or item["id"],
                "subject": item.get("subject") or "(No subject)",
                "from_email": from_email,
                "from_name": (item.get("from") or {}).get("emailAddress", {}).get("name")
                or from_display,
                "snippet": item.get("bodyPreview") or "",
                "date": item.get("receivedDateTime") or "",
            }
        )
    return candidates


def get_message_metadata(access_token: str, message_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{GRAPH_BASE}/me/messages/{message_id}",
            headers=_graph_headers(access_token),
            params={"$select": "id,conversationId,from,isRead"},
        )
        response.raise_for_status()
        return response.json()


def latest_inbound_message_id(
    access_token: str,
    conversation_id: str,
    account_email: str,
) -> str | None:
    conversation = fetch_thread_conversation(access_token, conversation_id)
    account_lower = account_email.lower()
    for message in reversed(conversation.messages):
        if account_lower not in message.from_email.lower():
            return message.email_id
    return None


def thread_participant_emails(access_token: str, conversation_id: str) -> set[str]:
    conversation = fetch_thread_conversation(access_token, conversation_id)
    participants: set[str] = set()

    def normalize(address: str) -> str:
        address = address.strip()
        match = re.search(r"<([^>]+)>", address)
        if match:
            return match.group(1).lower().strip()
        return address.lower().strip()

    for message in conversation.messages:
        if message.from_email:
            participants.add(normalize(message.from_email))
        if message.to_email:
            for part in message.to_email.split(","):
                if part.strip():
                    participants.add(normalize(part))
    return participants


def send_thread_reply(
    access_token: str,
    *,
    to: str,
    subject: str,
    body: str,
    reply_to_message_id: str,
    allowed_recipients: set[str] | None = None,
) -> dict[str, Any]:
    from app.google.email_safety import validate_outbound_email

    allowed, error = validate_outbound_email(
        to=to,
        allowed_extra_recipients=allowed_recipients,
    )
    if not allowed:
        raise ValueError(error)

    headers = {
        **_graph_headers(access_token),
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60.0) as client:
        create_response = client.post(
            f"{GRAPH_BASE}/me/messages/{reply_to_message_id}/createReply",
            headers=headers,
            json={},
        )
        create_response.raise_for_status()
        draft = create_response.json()
        draft_id = draft["id"]

        patch_response = client.patch(
            f"{GRAPH_BASE}/me/messages/{draft_id}",
            headers=headers,
            json={
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to.strip().strip("<>").split("<")[-1].rstrip(">"),
                        }
                    }
                ],
            },
        )
        patch_response.raise_for_status()

        send_response = client.post(
            f"{GRAPH_BASE}/me/messages/{draft_id}/send",
            headers=headers,
        )
        send_response.raise_for_status()

    return {"id": draft_id}


def outlook_message_url(message_id: str) -> str:
    return f"https://outlook.office.com/mail/deeplink/read/{message_id}"
