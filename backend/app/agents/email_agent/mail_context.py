"""Load mail threads and send replies across Gmail and Outlook."""

from __future__ import annotations

from googleapiclient.discovery import build

from app.agents.email_agent.attachments import enrich_conversation_attachments
from app.agents.email_agent.gmail import send_thread_reply as gmail_send_thread_reply
from app.agents.email_agent.gmail import thread_participant_emails as gmail_thread_participants
from app.agents.email_agent.sender_history import fetch_sender_history_block
from app.ai.tools.gmail_tool import EmailThreadConversation, _fetch_thread_conversation
from app.db.email_agent import EmailAgentItem
from app.google.oauth import load_credentials
from app.microsoft.graph_mail import (
    fetch_thread_conversation as outlook_fetch_thread,
)
from app.microsoft.graph_mail import (
    send_thread_reply as outlook_send_thread_reply,
)
from app.microsoft.graph_mail import (
    thread_participant_emails as outlook_thread_participants,
)
from app.microsoft.oauth import get_access_token


class MailSession:
    def __init__(self, *, provider: str, google_service=None, outlook_token: str | None = None):
        self.provider = provider
        self.google_service = google_service
        self.outlook_token = outlook_token


def load_mail_session(item: EmailAgentItem) -> MailSession:
    if item.mail_provider == "microsoft":
        token = get_access_token(item.microsoft_account_id)
        if not token:
            raise ValueError("Could not load Microsoft credentials")
        return MailSession(provider="microsoft", outlook_token=token)

    credentials = load_credentials(item.google_account_id)
    if not credentials:
        raise ValueError("Could not load Gmail credentials")
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    return MailSession(provider="google", google_service=service)


def fetch_item_conversation(
    item: EmailAgentItem,
    session: MailSession,
) -> EmailThreadConversation:
    if session.provider == "microsoft":
        assert session.outlook_token
        return outlook_fetch_thread(session.outlook_token, item.gmail_thread_id)
    assert session.google_service
    return _fetch_thread_conversation(session.google_service, item.gmail_thread_id)


def enrich_item_attachments(session: MailSession, conversation: EmailThreadConversation) -> None:
    if session.provider != "google" or not session.google_service:
        return
    enrich_conversation_attachments(session.google_service, conversation)


def fetch_sender_history(
    item: EmailAgentItem,
    session: MailSession,
    *,
    account_email: str,
    subject: str,
) -> str:
    if session.provider != "google" or not session.google_service:
        return ""
    return fetch_sender_history_block(
        session.google_service,
        sender_email=item.sender_email,
        exclude_thread_id=item.gmail_thread_id,
        current_subject=subject,
    )


def thread_participants(item: EmailAgentItem, session: MailSession) -> set[str]:
    if session.provider == "microsoft":
        assert session.outlook_token
        return outlook_thread_participants(session.outlook_token, item.gmail_thread_id)
    credentials = load_credentials(item.google_account_id)
    assert credentials
    return gmail_thread_participants(item.gmail_thread_id, credentials)


def send_item_reply(
    item: EmailAgentItem,
    session: MailSession,
    *,
    to: str,
    subject: str,
    body: str,
    allowed_recipients: set[str],
) -> dict:
    if session.provider == "microsoft":
        assert session.outlook_token
        return outlook_send_thread_reply(
            session.outlook_token,
            to=to,
            subject=subject,
            body=body,
            reply_to_message_id=item.gmail_message_id,
            allowed_recipients=allowed_recipients,
        )
    credentials = load_credentials(item.google_account_id)
    return gmail_send_thread_reply(
        credentials,
        to=to,
        subject=subject,
        body=body,
        thread_id=item.gmail_thread_id,
        reply_to_email_id=item.gmail_message_id,
        allowed_recipients=allowed_recipients,
    )
