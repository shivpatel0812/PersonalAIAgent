"""Email Agent orchestration — scan, draft, adjust, approve."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.attachments import attachments_to_api, enrich_conversation_attachments
from app.agents.email_agent.detector import (
    get_message_thread_id,
    is_likely_automated,
    latest_inbound_message_id,
    list_reply_candidates,
)
from app.agents.email_agent.drafter import classify_needs_reply, generate_initial_draft, revise_draft
from app.agents.email_agent.gmail import send_thread_reply, thread_participant_emails
from app.agents.email_agent.scheduling import (
    build_calendar_availability_block,
    detect_scheduling,
)
from app.agents.email_agent.sender_history import fetch_sender_history_block
from app.agents.email_agent.sender_intelligence import (
    candidate_sort_key,
    format_sender_context_block,
    get_sender_context,
    maybe_refresh_sender_priorities,
    should_auto_archive,
)
from app.agents.email_agent.user_profile import get_profile_block_with_defaults
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
    list_items_by_status,
    update_item,
)
from app.db.google_accounts import list_accounts
from app.google.oauth import get_granted_services, load_credentials

logger = logging.getLogger(__name__)


def _reply_subject(subject: str) -> str:
    subject = subject or "(No subject)"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


async def _sort_candidates_by_sender_priority(candidates: list) -> list:
    enriched: list[tuple] = []
    for candidate in candidates:
        context = await get_sender_context(candidate.from_email)
        enriched.append((candidate, context))
    enriched.sort(key=lambda pair: candidate_sort_key(pair[1]), reverse=True)
    return [candidate for candidate, _ in enriched]


async def _build_draft_prompt_context(
    *,
    item: EmailAgentItem,
    conversation,
    credentials,
    account,
) -> tuple[str, str, str, dict]:
    profile_block = await get_profile_block_with_defaults(item.user_id)

    sender_context = await get_sender_context(item.sender_email, user_id=item.user_id)
    sender_context_block = format_sender_context_block(sender_context)

    from app.db.user_email_profile import get_profile

    profile = await get_profile(item.user_id)
    timezone = profile.timezone if profile else "America/Los_Angeles"

    granted = get_granted_services(item.google_account_id)
    scheduling = detect_scheduling(
        subject=item.subject or conversation.subject,
        conversation=conversation,
        reply_to_message_id=item.gmail_message_id,
    )
    scheduling = build_calendar_availability_block(
        credentials,
        scheduling,
        granted_scopes=granted,
        timezone=timezone,
    )

    calendar_block = scheduling.availability_block if scheduling.is_scheduling else ""
    draft_meta = {
        "schedulingDetected": scheduling.detected and scheduling.is_scheduling,
        "calendarChecked": scheduling.calendar_checked,
        "calendarConnected": scheduling.calendar_connected,
    }

    return profile_block, sender_context_block, calendar_block, draft_meta


async def _discard_failed_item(item_id: str, reason: str) -> None:
    logger.warning("Discarding email agent item %s: %s", item_id, reason)
    await update_item(item_id, status="discarded")


async def recover_stuck_drafts() -> dict:
    """Retry or remove queue items stuck in needs_draft."""
    stuck = await list_items_by_status("needs_draft")
    retried = 0
    recovered = 0
    discarded = 0

    for item in stuck:
        retried += 1
        try:
            await draft_item(item.id)
            recovered += 1
        except Exception as exc:
            logger.exception("Retry draft failed for %s: %s", item.id, exc)
            await _discard_failed_item(item.id, str(exc))
            discarded += 1

    return {
        "stuck_found": len(stuck),
        "retried": retried,
        "recovered": recovered,
        "discarded": discarded,
    }


async def cleanup_bad_queue_items() -> dict:
    """Discard active items that are clearly automated notifications."""
    removed = 0
    for item in await list_active_items():
        should_skip, reason = is_likely_automated(
            from_email=item.sender_email,
            subject=item.subject or "",
            snippet=item.summary or "",
        )
        if should_skip:
            await _discard_failed_item(item.id, reason)
            removed += 1
    return {"removed": removed}


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

    cleanup_result = await cleanup_bad_queue_items()
    recovery_result = await recover_stuck_drafts()

    scanned = 0
    queued = 0
    drafted = 0
    skipped_automated = 0

    for account in accounts:
        credentials = load_credentials(account.id)
        if not credentials:
            continue

        candidates = list_reply_candidates(
            credentials,
            account_email=account.email,
        )
        candidates = await _sort_candidates_by_sender_priority(candidates)

        for candidate in candidates:
            if await count_active_items() >= agent_settings.MAX_ACTIVE_QUEUE_SIZE:
                break

            scanned += 1

            if await get_item_by_message_id(candidate.message_id):
                continue

            should_skip, skip_reason = is_likely_automated(
                from_email=candidate.from_email,
                subject=candidate.subject,
                snippet=candidate.snippet,
            )
            if should_skip:
                skipped_automated += 1
                logger.info(
                    "Skipping automated email %s: %s",
                    candidate.message_id,
                    skip_reason,
                )
                continue

            sender_context = await get_sender_context(candidate.from_email)
            if should_auto_archive(sender_context):
                skipped_automated += 1
                logger.info(
                    "Skipping auto-archive sender %s for message %s",
                    candidate.from_email,
                    candidate.message_id,
                )
                continue

            thread_id = get_message_thread_id(credentials, candidate.message_id)
            if not thread_id:
                continue

            inbound_id = latest_inbound_message_id(credentials, thread_id, account.email)
            if inbound_id != candidate.message_id:
                continue

            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
            conversation = _fetch_thread_conversation(service, thread_id)

            needs_reply, summary = classify_needs_reply(
                account_email=account.email,
                subject=candidate.subject,
                from_email=candidate.from_email,
                snippet=candidate.snippet,
                conversation=conversation,
                reply_to_message_id=candidate.message_id,
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
                await _discard_failed_item(item.id, str(exc))

    return {
        "status": "ok",
        "scanned": scanned,
        "queued": queued,
        "drafted": drafted,
        "skipped_automated": skipped_automated,
        "cleanup": cleanup_result,
        "recovery": recovery_result,
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
    enrich_conversation_attachments(service, conversation)

    from app.db.google_accounts import get_account

    account = await get_account(item.google_account_id)
    account_email = account.email if account else ""

    sender_history = fetch_sender_history_block(
        service,
        sender_email=item.sender_email,
        exclude_thread_id=item.gmail_thread_id,
        current_subject=item.subject or conversation.subject,
    )

    profile_block, sender_context_block, calendar_block, draft_meta = (
        await _build_draft_prompt_context(
            item=item,
            conversation=conversation,
            credentials=credentials,
            account=account,
        )
    )

    summary, draft, middle_summary = generate_initial_draft(
        conversation=conversation,
        account_email=account_email,
        sender_name=item.sender_name or item.sender_email,
        sender_email=item.sender_email,
        reply_to_message_id=item.gmail_message_id,
        cached_middle_summary=item.thread_context_summary,
        sender_history_block=sender_history,
        profile_block=profile_block,
        sender_context_block=sender_context_block,
        calendar_block=calendar_block,
    )

    update_fields: dict = {
        "summary": summary or item.summary,
        "draft_response": draft,
        "status": "draft_ready",
        "draft_context_meta": draft_meta,
    }
    if middle_summary:
        update_fields["thread_context_summary"] = middle_summary

    updated = await update_item(item_id, **update_fields)
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
    enrich_conversation_attachments(service, conversation)

    from app.db.google_accounts import get_account

    account = await get_account(item.google_account_id)
    account_email = account.email if account else ""

    sender_history = fetch_sender_history_block(
        service,
        sender_email=item.sender_email,
        exclude_thread_id=item.gmail_thread_id,
        current_subject=item.subject or conversation.subject,
    )

    profile_block, sender_context_block, calendar_block, draft_meta = (
        await _build_draft_prompt_context(
            item=item,
            conversation=conversation,
            credentials=credentials,
            account=account,
        )
    )

    await add_chat_message(item_id, role="user", content=message)
    chat_rows = await list_chat_messages(item_id)
    chat_history = [{"role": row.role, "content": row.content} for row in chat_rows]

    revised_draft, assistant_message = revise_draft(
        conversation=conversation,
        account_email=account_email,
        current_draft=item.draft_response or "",
        chat_history=chat_history,
        user_message=message,
        reply_to_message_id=item.gmail_message_id,
        cached_middle_summary=item.thread_context_summary,
        sender_history_block=sender_history,
        profile_block=profile_block,
        sender_context_block=sender_context_block,
        calendar_block=calendar_block,
    )

    await update_item(
        item_id,
        draft_response=revised_draft,
        status="draft_ready",
        draft_context_meta=draft_meta,
    )
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

    await maybe_refresh_sender_priorities()

    return {"success": True, "messageId": sent.get("id")}


async def discard_item(item_id: str) -> EmailAgentItem:
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")

    updated = await update_item(item_id, status="discarded")
    if not updated:
        raise ValueError("Failed to discard item")
    return updated


async def get_item_thread(item_id: str) -> dict:
    """Load the full Gmail thread for a queue item."""
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")

    credentials = load_credentials(item.google_account_id)
    if not credentials:
        raise ValueError("Could not load Gmail credentials")

    from app.db.google_accounts import get_account

    account = await get_account(item.google_account_id)
    account_email = (account.email if account else "").lower()

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    conversation = _fetch_thread_conversation(service, item.gmail_thread_id)
    enrich_conversation_attachments(service, conversation)

    messages = []
    for message in conversation.messages:
        from_lower = message.from_email.lower()
        is_inbound = account_email not in from_lower
        messages.append(
            {
                "id": message.email_id,
                "fromEmail": message.from_email,
                "toEmail": message.to_email,
                "date": message.date,
                "subject": message.subject,
                "body": message.body,
                "isInbound": is_inbound,
                "isTarget": message.email_id == item.gmail_message_id,
                "attachments": attachments_to_api(message),
            }
        )

    return {
        "threadId": conversation.thread_id,
        "subject": conversation.subject,
        "messages": messages,
    }


async def get_item_detail(item_id: str) -> dict:
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")

    chat_rows = await list_chat_messages(item_id)
    sender_context = await get_sender_context(item.sender_email, user_id=item.user_id)
    return {
        "item": item.to_api_dict(
            always_urgent=bool(sender_context and sender_context.always_urgent)
        ),
        "chatMessages": [row.to_api_dict() for row in chat_rows],
    }


async def list_items() -> list[dict]:
    await cleanup_bad_queue_items()
    items = await list_active_items()
    result: list[dict] = []
    for item in items:
        context = await get_sender_context(item.sender_email, user_id=item.user_id)
        always_urgent = bool(context and context.always_urgent)
        result.append(item.to_api_dict(always_urgent=always_urgent))
    return result
