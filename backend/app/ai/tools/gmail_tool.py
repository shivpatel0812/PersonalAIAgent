"""Gmail tools - allows the agent to read and send emails via Gmail API."""

from __future__ import annotations

import base64
import re
from email.mime.text import MIMEText
from typing import Any

from googleapiclient.discovery import build
from pydantic import BaseModel, Field

from app.ai.tools.base import Tool, ToolParameter
from app.google.email_safety import validate_outbound_email
from app.google.oauth import load_credentials

MAX_BODY_CHARS = 6000
MAX_THREAD_MESSAGES = 50


def _extract_body_from_payload(payload: dict[str, Any]) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    if mime_type == "text/html" and body_data and not payload.get("parts"):
        html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", " ", html)

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            text = _extract_body_from_payload(part)
            if text.strip():
                return text

    for part in payload.get("parts", []):
        text = _extract_body_from_payload(part)
        if text.strip():
            return text

    if body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    return ""


def _truncate_body(body: str) -> str:
    if len(body) <= MAX_BODY_CHARS:
        return body
    return body[:MAX_BODY_CHARS] + "\n...[truncated]"


def _headers_from_message(message: dict[str, Any]) -> dict[str, str]:
    return {h["name"]: h["value"] for h in message["payload"]["headers"]}


def _build_person_query(person: str) -> str:
    person = person.strip()
    if "@" in person:
        return f"(from:{person} OR to:{person})"
    return f'(from:"{person}" OR to:"{person}")'


def _get_gmail_service():
    credentials = load_credentials()
    if not credentials:
        return None
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


class ThreadMessage(BaseModel):
    email_id: str
    from_email: str
    to_email: str | None = None
    date: str
    subject: str
    body: str
    snippet: str = ""


class EmailThreadConversation(BaseModel):
    thread_id: str
    subject: str
    message_count: int
    messages: list[ThreadMessage] = Field(default_factory=list)


def _fetch_thread_conversation(service, thread_id: str) -> EmailThreadConversation:
    thread = (
        service.users()
        .threads()
        .get(userId="me", id=thread_id, format="full")
        .execute()
    )

    raw_messages = thread.get("messages", [])
    raw_messages.sort(key=lambda msg: int(msg.get("internalDate", 0)))

    if len(raw_messages) > MAX_THREAD_MESSAGES:
        raw_messages = raw_messages[-MAX_THREAD_MESSAGES:]

    messages: list[ThreadMessage] = []
    subject = "(No subject)"

    for msg in raw_messages:
        headers = _headers_from_message(msg)
        if not messages:
            subject = headers.get("Subject", "(No subject)")

        messages.append(
            ThreadMessage(
                email_id=msg["id"],
                from_email=headers.get("From", "Unknown"),
                to_email=headers.get("To"),
                date=headers.get("Date", ""),
                subject=headers.get("Subject", subject),
                body=_truncate_body(_extract_body_from_payload(msg["payload"])),
                snippet=msg.get("snippet", ""),
            )
        )

    return EmailThreadConversation(
        thread_id=thread_id,
        subject=subject,
        message_count=len(messages),
        messages=messages,
    )


class EmailMessage(BaseModel):
    """Represents an email message."""
    id: str
    thread_id: str
    subject: str
    from_email: str
    to_email: str | None = None
    date: str
    snippet: str
    is_unread: bool
    labels: list[str] = []


class ListEmailsResult(BaseModel):
    """Result of listing emails."""
    success: bool
    emails: list[EmailMessage] = []
    count: int
    message: str


class ListEmailsTool(Tool):
    """Tool for listing recent emails from Gmail."""

    @property
    def name(self) -> str:
        return "list_emails"

    @property
    def description(self) -> str:
        return "list recent emails from Gmail with optional filters (unread only, max results, search query)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of emails to return (default: 10)",
                "required": False,
            },
            {
                "name": "unread_only",
                "type": "boolean",
                "description": "only show unread emails (default: false)",
                "required": False,
            },
            {
                "name": "query",
                "type": "string",
                "description": "Gmail search query (e.g., 'from:john@example.com', 'subject:meeting', 'is:important')",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ListEmailsResult:
        """
        List recent emails from Gmail.

        Args:
            max_results: Maximum number of emails (default 10)
            unread_only: Only unread emails (default false)
            query: Gmail search query (optional)

        Returns:
            ListEmailsResult with list of emails
        """
        max_results = kwargs.get("max_results", 10)
        unread_only = kwargs.get("unread_only", False)
        query = kwargs.get("query", "").strip()

        credentials = load_credentials()
        if not credentials:
            return ListEmailsResult(
                success=False,
                count=0,
                message="Gmail is not connected. Please connect your Google account first."
            )

        try:
            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

            # Build query
            search_query = query if query else ""
            if unread_only:
                search_query = f"{search_query} is:unread".strip()

            # List messages
            results = service.users().messages().list(
                userId='me',
                q=search_query if search_query else None,
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])

            email_list = []
            for msg in messages:
                # Get full message details
                message = service.users().messages().get(userId='me', id=msg['id'], format='metadata',
                                                         metadataHeaders=['From', 'To', 'Subject', 'Date']).execute()

                headers = {h['name']: h['value'] for h in message['payload']['headers']}

                email_list.append(EmailMessage(
                    id=message['id'],
                    thread_id=message['threadId'],
                    subject=headers.get('Subject', '(No subject)'),
                    from_email=headers.get('From', 'Unknown'),
                    to_email=headers.get('To'),
                    date=headers.get('Date', ''),
                    snippet=message.get('snippet', ''),
                    is_unread='UNREAD' in message.get('labelIds', []),
                    labels=message.get('labelIds', [])
                ))

            msg_text = f"Found {len(email_list)} email(s)"
            if unread_only:
                msg_text += " (unread only)"
            if query:
                msg_text += f" matching '{query}'"

            return ListEmailsResult(
                success=True,
                emails=email_list,
                count=len(email_list),
                message=msg_text
            )

        except Exception as e:
            return ListEmailsResult(
                success=False,
                count=0,
                message=f"Failed to list emails: {str(e)}"
            )


class ReadEmailResult(BaseModel):
    """Result of reading an email."""
    success: bool
    email_id: str | None = None
    subject: str | None = None
    from_email: str | None = None
    to_email: str | None = None
    date: str | None = None
    body: str | None = None
    message: str


class ReadEmailTool(Tool):
    """Tool for reading full email content."""

    @property
    def name(self) -> str:
        return "read_email"

    @property
    def description(self) -> str:
        return "read the full content of a specific email by its ID (get ID from list_emails)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "email_id",
                "type": "string",
                "description": "the ID of the email to read (get from list_emails)",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> ReadEmailResult:
        """
        Read full email content.

        Args:
            email_id: The ID of the email to read

        Returns:
            ReadEmailResult with full email content
        """
        email_id = kwargs.get("email_id", "").strip()

        if not email_id:
            raise ValueError("Email ID is required")

        credentials = load_credentials()
        if not credentials:
            return ReadEmailResult(
                success=False,
                message="Gmail is not connected. Please connect your Google account first."
            )

        try:
            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

            message = service.users().messages().get(userId='me', id=email_id, format='full').execute()
            headers = _headers_from_message(message)
            body = _truncate_body(_extract_body_from_payload(message["payload"]))

            return ReadEmailResult(
                success=True,
                email_id=email_id,
                subject=headers.get('Subject', '(No subject)'),
                from_email=headers.get('From', 'Unknown'),
                to_email=headers.get('To'),
                date=headers.get('Date', ''),
                body=body,
                message="✅ Email read successfully"
            )

        except Exception as e:
            return ReadEmailResult(
                success=False,
                email_id=email_id,
                message=f"Failed to read email: {str(e)}"
            )


class ReadEmailThreadResult(BaseModel):
    success: bool
    thread_id: str | None = None
    subject: str | None = None
    message_count: int = 0
    messages: list[ThreadMessage] = Field(default_factory=list)
    message: str


class ReadEmailThreadTool(Tool):
    """Read every message in a Gmail thread from start to finish."""

    @property
    def name(self) -> str:
        return "read_email_thread"

    @property
    def description(self) -> str:
        return (
            "read the full email thread (all back-and-forth messages in order). "
            "Provide thread_id from list_emails/get_email_conversation, or email_id "
            "from any message in the thread"
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "thread_id",
                "type": "string",
                "description": "Gmail thread ID (preferred)",
                "required": False,
            },
            {
                "name": "email_id",
                "type": "string",
                "description": "any message ID in the thread (used if thread_id not provided)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ReadEmailThreadResult:
        thread_id = kwargs.get("thread_id", "").strip()
        email_id = kwargs.get("email_id", "").strip()

        if not thread_id and not email_id:
            raise ValueError("thread_id or email_id is required")

        service = _get_gmail_service()
        if not service:
            return ReadEmailThreadResult(
                success=False,
                message="Gmail is not connected. Please connect your Google account first.",
            )

        try:
            if not thread_id:
                msg = service.users().messages().get(
                    userId="me", id=email_id, format="metadata"
                ).execute()
                thread_id = msg["threadId"]

            conversation = _fetch_thread_conversation(service, thread_id)
            return ReadEmailThreadResult(
                success=True,
                thread_id=conversation.thread_id,
                subject=conversation.subject,
                message_count=conversation.message_count,
                messages=conversation.messages,
                message=f"Read full thread with {conversation.message_count} message(s)",
            )
        except Exception as exc:
            return ReadEmailThreadResult(
                success=False,
                thread_id=thread_id or None,
                message=f"Failed to read email thread: {exc}",
            )


class GetEmailConversationResult(BaseModel):
    success: bool
    person_query: str = ""
    threads: list[EmailThreadConversation] = Field(default_factory=list)
    message: str


class GetEmailConversationTool(Tool):
    """Find recent threads with a person and load each thread through to the end."""

    @property
    def name(self) -> str:
        return "get_email_conversation"

    @property
    def description(self) -> str:
        return (
            "find recent email threads with a person and read each full thread in order. "
            "Use before drafting a reply. person can be an email address or a name"
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "person",
                "type": "string",
                "description": "email address or display name to search (e.g. 'john@company.com' or 'John Smith')",
                "required": True,
            },
            {
                "name": "max_threads",
                "type": "integer",
                "description": "how many recent threads to load fully (default: 2)",
                "required": False,
            },
            {
                "name": "search_limit",
                "type": "integer",
                "description": "how many recent matching emails to scan when finding threads (default: 15)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> GetEmailConversationResult:
        person = kwargs.get("person", "").strip()
        max_threads = int(kwargs.get("max_threads", 2))
        search_limit = int(kwargs.get("search_limit", 15))

        if not person:
            raise ValueError("person is required")

        service = _get_gmail_service()
        if not service:
            return GetEmailConversationResult(
                success=False,
                person_query=person,
                message="Gmail is not connected. Please connect your Google account first.",
            )

        try:
            search_query = _build_person_query(person)
            results = service.users().messages().list(
                userId="me",
                q=search_query,
                maxResults=search_limit,
            ).execute()

            thread_ids: list[str] = []
            seen: set[str] = set()
            for msg in results.get("messages", []):
                tid = msg["threadId"]
                if tid in seen:
                    continue
                seen.add(tid)
                thread_ids.append(tid)
                if len(thread_ids) >= max_threads:
                    break

            if not thread_ids:
                return GetEmailConversationResult(
                    success=True,
                    person_query=person,
                    threads=[],
                    message=f"No recent email threads found for {person}",
                )

            threads = [_fetch_thread_conversation(service, tid) for tid in thread_ids]
            total_messages = sum(t.message_count for t in threads)

            return GetEmailConversationResult(
                success=True,
                person_query=person,
                threads=threads,
                message=(
                    f"Loaded {len(threads)} thread(s) with {total_messages} total message(s) "
                    f"for {person}"
                ),
            )
        except Exception as exc:
            return GetEmailConversationResult(
                success=False,
                person_query=person,
                message=f"Failed to load conversation: {exc}",
            )


class SendEmailResult(BaseModel):
    """Result of sending an email."""
    success: bool
    email_id: str | None = None
    thread_id: str | None = None
    message: str


class SendEmailTool(Tool):
    """Tool for sending emails via Gmail."""

    @property
    def name(self) -> str:
        return "send_email"

    @property
    def description(self) -> str:
        return (
            "send an email via Gmail. For replies, pass thread_id and reply_to_email_id "
            "from get_email_conversation/read_email_thread so the response stays in the thread"
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "to",
                "type": "string",
                "description": "recipient email address or comma-separated list (e.g., 'john@example.com,sarah@example.com')",
                "required": True,
            },
            {
                "name": "subject",
                "type": "string",
                "description": "email subject line (use Re: <original subject> for replies)",
                "required": True,
            },
            {
                "name": "body",
                "type": "string",
                "description": "email body/content (plain text)",
                "required": True,
            },
            {
                "name": "cc",
                "type": "string",
                "description": "CC recipients (comma-separated, optional)",
                "required": False,
            },
            {
                "name": "thread_id",
                "type": "string",
                "description": "Gmail thread ID when replying in an existing conversation",
                "required": False,
            },
            {
                "name": "reply_to_email_id",
                "type": "string",
                "description": "message ID being replied to (sets In-Reply-To headers)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> SendEmailResult:
        """
        Send an email via Gmail.

        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Email body
            cc: CC recipients (optional)

        Returns:
            SendEmailResult with sent message details
        """
        to = kwargs.get("to", "").strip()
        subject = kwargs.get("subject", "").strip()
        body = kwargs.get("body", "").strip()
        cc = kwargs.get("cc", "").strip()
        thread_id = kwargs.get("thread_id", "").strip()
        reply_to_email_id = kwargs.get("reply_to_email_id", "").strip()

        if not to:
            raise ValueError("Recipient email (to) is required")
        if not subject:
            raise ValueError("Email subject is required")
        if not body:
            raise ValueError("Email body is required")

        allowed, error = validate_outbound_email(to=to, cc=cc)
        if not allowed:
            return SendEmailResult(success=False, message=error)

        credentials = load_credentials()
        if not credentials:
            return SendEmailResult(
                success=False,
                message="Gmail is not connected. Please connect your Google account first."
            )

        try:
            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

            # Create message
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            if cc:
                message["cc"] = cc

            if reply_to_email_id:
                original = service.users().messages().get(
                    userId="me",
                    id=reply_to_email_id,
                    format="metadata",
                    metadataHeaders=["Message-ID", "References", "Subject"],
                ).execute()
                orig_headers = _headers_from_message(original)
                message_id = orig_headers.get("Message-ID")
                if message_id:
                    message["In-Reply-To"] = message_id
                    references = orig_headers.get("References", "")
                    message["References"] = f"{references} {message_id}".strip()

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            send_message: dict[str, Any] = {"raw": raw_message}
            if thread_id:
                send_message["threadId"] = thread_id

            sent = service.users().messages().send(userId="me", body=send_message).execute()

            return SendEmailResult(
                success=True,
                email_id=sent.get("id"),
                thread_id=sent.get("threadId"),
                message=f"✅ Email sent successfully to {to}"
            )

        except Exception as e:
            return SendEmailResult(
                success=False,
                message=f"Failed to send email: {str(e)}"
            )


class MarkEmailResult(BaseModel):
    """Result of marking email as read/unread."""
    success: bool
    email_id: str | None = None
    message: str


class MarkEmailAsReadTool(Tool):
    """Tool for marking emails as read or unread."""

    @property
    def name(self) -> str:
        return "mark_email_read"

    @property
    def description(self) -> str:
        return "mark an email as read or unread"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "email_id",
                "type": "string",
                "description": "the ID of the email to mark (get from list_emails)",
                "required": True,
            },
            {
                "name": "mark_as_read",
                "type": "boolean",
                "description": "true to mark as read, false to mark as unread (default: true)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> MarkEmailResult:
        """
        Mark email as read or unread.

        Args:
            email_id: The ID of the email
            mark_as_read: True to mark read, False for unread (default true)

        Returns:
            MarkEmailResult with status
        """
        email_id = kwargs.get("email_id", "").strip()
        mark_as_read = kwargs.get("mark_as_read", True)

        if not email_id:
            raise ValueError("Email ID is required")

        credentials = load_credentials()
        if not credentials:
            return MarkEmailResult(
                success=False,
                message="Gmail is not connected. Please connect your Google account first."
            )

        try:
            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

            if mark_as_read:
                # Remove UNREAD label
                service.users().messages().modify(
                    userId='me',
                    id=email_id,
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
                msg = "✅ Email marked as read"
            else:
                # Add UNREAD label
                service.users().messages().modify(
                    userId='me',
                    id=email_id,
                    body={'addLabelIds': ['UNREAD']}
                ).execute()
                msg = "✅ Email marked as unread"

            return MarkEmailResult(
                success=True,
                email_id=email_id,
                message=msg
            )

        except Exception as e:
            return MarkEmailResult(
                success=False,
                email_id=email_id,
                message=f"Failed to mark email: {str(e)}"
            )
