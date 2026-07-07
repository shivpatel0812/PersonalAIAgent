"""Email Agent orchestration — scan, draft, adjust, approve."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.detector import (
    build_thread_excerpt,
    email_needs_reply,
    get_message_thread_id,
    latest_inbound_message_id,
    list_reply_candidates,
)
from app.agents.email_agent.drafter import generate_initial_draft, revise_draft
from app.agents.email_agent.gmail import send_thread_reply, thread_participant_emails
from app.ai.config import settings as ai_settings
from app.ai.tools.gmail_tool import _fetch_thread_conversation
from app.db.email_agent import (
    ACTIVE_STATUSES,
    EmailAgentItem,
    add_chat_message,
    count_active_items,
    create_item,
    get_item,
    get_item_by_message_id,
    list_active_items,
    list_chat_messages,
    update_item,
)
from app.db.google_accounts import list_accounts
from app.google.oauth import load_credentials

logger = logging.getLogger(__name__)


def _reply_subject(subject: str) -> str:
    subject = subject or "(No subject)"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


async def scan_for_reply_candidates() -> dict:
    """Scan connected accounts and queue emails that need a reply."""
    if not agent_settings.ENABLED:
        return {"status": "skipped", "reason": "email agent disabled"}

    if not ai_settings.openai_configured:
        return {"status": "skipped", "reason": "OpenAI not configured"}

    accounts = await list_accounts()
    if not accounts:
        return {"status": "skipped", "reason": "no Google accounts connected"}

    active_count = await count_active_items()
    if active_count >= agent_settings.MAX_ACTIVE_QUEUE_SIZE:
        return {
            "status": "skipped",
            "reason": "queue full",
            "active_count": active_count,
        }

    scanned = 0
    queued = 0
    drafted = 0

    for account in accounts:
        credentials = load_credentials(account.id)
        if not credentials:
            continue

        candidates = list_reply_candidates(
            credentials,
            account_email=account.email,
        )

        for candidate in candidates:
            if await count_active_items() >= agent_settings.MAX_ACTIVE_QUEUE_SIZE:
                break

            scanned += 1

            if await get_item_by_message_id(candidate.message_id):
                continue

            thread_id = get_message_thread_id(credentials, candidate.message_id)
            if not thread_id:
                continue

            inbound_id = latest_inbound_message_id(credentials, thread_id, account.email)
            if inbound_id != candidate.message_id:
                continue

            excerpt = build_thread_excerpt(credentials, thread_id)
            needs_reply, summary = email_needs_reply(
                account_email=account.email,
                subject=candidate.subject,
                from_email=candidate.from_email,
                snippet=candidate.snippet,
                thread_summary=excerpt,
            )
            if not needs_reply:
                continue

            item = await create_item(
                google_account_id=account.id,
                gmail_thread_id=thread_id,
                gmail_message_id=candidate.message_id,
                sender_name=candidate.from_name,
                sender_email=candidate.from_email,
                subject=candidate.subject,
                summary=summary or candidate.snippet,
                status="needs_draft",
            )
            queued += 1

            try:
                await draft_item(item.id)
                drafted += 1
            except Exception as exc:
                logger.exception("Failed to draft item %s: %s", item.id, exc)

    return {
        "status": "ok",
        "scanned": scanned,
        "queued": queued,
        "drafted": drafted,
    }


async def draft_item(item_id: str) -> EmailAgentItem:
    """Generate initial draft and welcome chat for a queued item."""
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")

    credentials = load_credentials(item.google_account_id)
    if not credentials:
        raise ValueError("Could not load Gmail credentials")

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    conversation = _fetch_thread_conversation(service, item.gmail_thread_id)

    from app.db.google_accounts import get_account

    account = await get_account(item.google_account_id)
    account_email = account.email if account else ""

    summary, draft = generate_initial_draft(
        conversation=conversation,
        account_email=account_email,
        sender_name=item.sender_name or item.sender_email,
        sender_email=item.sender_email,
    )

    updated = await update_item(
        item_id,
        summary=summary or item.summary,
        draft_response=draft,
        status="draft_ready",
    )
    if not updated:
        raise ValueError("Failed to update item")

    existing_chat = await list_chat_messages(item_id)
    if not existing_chat:
        await add_chat_message(
            item_id,
            role="assistant",
            content=agent_settings.WELCOME_CHAT_MESSAGE,
        )

    return updated


async def adjust_item_draft(item_id: str, message: str) -> dict:
    """Revise draft from user chat feedback."""
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")
    if item.status not in ACTIVE_STATUSES:
        raise ValueError("Item is no longer active")

    credentials = load_credentials(item.google_account_id)
    if not credentials:
        raise ValueError("Could not load Gmail credentials")

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    conversation = _fetch_thread_conversation(service, item.gmail_thread_id)

    from app.db.google_accounts import get_account

    account = await get_account(item.google_account_id)
    account_email = account.email if account else ""

    await add_chat_message(item_id, role="user", content=message)
    chat_rows = await list_chat_messages(item_id)
    chat_history = [{"role": row.role, "content": row.content} for row in chat_rows]

    revised_draft, assistant_message = revise_draft(
        conversation=conversation,
        account_email=account_email,
        current_draft=item.draft_response or "",
        chat_history=chat_history,
        user_message=message,
    )

    await update_item(item_id, draft_response=revised_draft, status="draft_ready")
    assistant_row = await add_chat_message(
        item_id,
        role="assistant",
        content=assistant_message,
    )

    return {
        "draftResponse": revised_draft,
        "assistantMessage": assistant_row.to_api_dict(),
    }


async def approve_and_send_item(item_id: str, draft_response: str) -> dict:
    """Send approved draft and mark item sent."""
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")
    if item.status == "sent":
        return {"success": True, "messageId": item.sent_gmail_message_id}
    if item.status == "discarded":
        raise ValueError("Item was discarded")

    credentials = load_credentials(item.google_account_id)
    if not credentials:
        raise ValueError("Could not load Gmail credentials")

    participants = thread_participant_emails(item.gmail_thread_id, credentials)
    body = draft_response.strip()
    if not body:
        raise ValueError("Draft is empty")

    await update_item(item_id, draft_response=body, status="approved")

    sent = send_thread_reply(
        credentials,
        to=item.sender_email,
        subject=_reply_subject(item.subject or ""),
        body=body,
        thread_id=item.gmail_thread_id,
        reply_to_email_id=item.gmail_message_id,
        allowed_recipients=participants,
    )

    now = datetime.now(timezone.utc).isoformat()
    await update_item(
        item_id,
        status="sent",
        sent_at=now,
        sent_gmail_message_id=sent.get("id"),
    )

    await add_chat_message(
        item_id,
        role="assistant",
        content=f"Sent your reply to {item.sender_email}.",
    )

    try:
        from app.supabase_client import get_supabase_client

        supabase = get_supabase_client()
        supabase.table("email_events").insert(
            {
                "user_id": item.user_id,
                "email_id": item.gmail_message_id,
                "gmail_message_id": item.gmail_message_id,
                "sender": item.sender_email,
                "subject": item.subject,
                "event_type": "replied",
            }
        ).execute()
    except Exception as exc:
        logger.warning("Failed to log email event: %s", exc)

    return {"success": True, "messageId": sent.get("id")}


async def discard_item(item_id: str) -> EmailAgentItem:
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")

    updated = await update_item(item_id, status="discarded")
    if not updated:
        raise ValueError("Failed to discard item")
    return updated


async def get_item_detail(item_id: str) -> dict:
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")

    chat_rows = await list_chat_messages(item_id)
    return {
        "item": item.to_api_dict(),
        "chatMessages": [row.to_api_dict() for row in chat_rows],
    }


async def list_items() -> list[dict]:
    items = await list_active_items()
    return [item.to_api_dict() for item in items]
