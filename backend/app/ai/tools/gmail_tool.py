"""Gmail tools - allows the agent to read and send emails via Gmail API."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.ai.tools.base import Tool, ToolParameter
from app.google.oauth import load_credentials
from googleapiclient.discovery import build


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

            # Get full message
            message = service.users().messages().get(userId='me', id=email_id, format='full').execute()

            headers = {h['name']: h['value'] for h in message['payload']['headers']}

            # Extract body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            elif 'body' in message['payload'] and 'data' in message['payload']['body']:
                body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')

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
        return "send an email via Gmail to specified recipients"

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
                "description": "email subject line",
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

        if not to:
            raise ValueError("Recipient email (to) is required")
        if not subject:
            raise ValueError("Email subject is required")
        if not body:
            raise ValueError("Email body is required")

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
            message['to'] = to
            message['subject'] = subject
            if cc:
                message['cc'] = cc

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            send_message = {'raw': raw_message}

            # Send
            sent = service.users().messages().send(userId='me', body=send_message).execute()

            return SendEmailResult(
                success=True,
                email_id=sent.get('id'),
                thread_id=sent.get('threadId'),
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
