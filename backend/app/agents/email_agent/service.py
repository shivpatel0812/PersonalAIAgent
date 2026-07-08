"""Email Agent orchestration — scan, draft, adjust, approve."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from googleapiclient.discovery import build

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.attachments import attachments_to_api
from app.agents.email_agent.detector import (
    get_message_thread_id,
    is_likely_automated,
    latest_inbound_message_id as gmail_latest_inbound,
    list_browse_candidates,
)
from app.agents.email_agent.date_utils import is_within_reply_window
from app.agents.email_agent.drafter import classify_needs_reply, generate_initial_draft, revise_draft
from app.agents.email_agent.mail_context import (
    MailSession,
    enrich_item_attachments,
    fetch_item_conversation,
    fetch_sender_history,
    load_mail_session,
    send_item_reply,
    thread_participants,
)
from app.agents.email_agent.scheduling import (
    build_calendar_availability_block,
    detect_scheduling,
)
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
    PRIORITY_STATUSES,
    EmailAgentItem,
    add_chat_message,
    count_active_items,
    count_browse_items,
    count_priority_items,
    create_item,
    get_item,
    get_item_by_message_id,
    list_active_items,
    list_chat_messages,
    list_items_by_status,
    update_item,
)
from app.db.google_accounts import get_account as get_google_account
from app.db.google_accounts import list_accounts as list_google_accounts
from app.db.microsoft_accounts import get_account as get_microsoft_account
from app.db.microsoft_accounts import list_accounts as list_microsoft_accounts
from app.google.oauth import get_granted_services, load_credentials
from app.microsoft.graph_mail import (
    fetch_thread_conversation as outlook_fetch_thread,
)
from app.microsoft.graph_mail import (
    latest_inbound_message_id as outlook_latest_inbound,
)
from app.microsoft.graph_mail import (
    list_browse_inbox_candidates,
)
from app.microsoft.oauth import get_access_token

logger = logging.getLogger(__name__)


@dataclass
class ScanCandidate:
    message_id: str
    thread_id: str
    subject: str
    from_email: str
    from_name: str | None
    snippet: str
    date: str = ""
    is_unread: bool = True


_STATUS_SORT_ORDER = {
    "needs_draft": 0,
    "waiting_on_you": 1,
    "draft_ready": 2,
    "listed": 3,
}


def _reply_subject(subject: str) -> str:
    subject = subject or "(No subject)"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


async def _get_account_email(item: EmailAgentItem) -> str:
    if item.mail_provider == "microsoft":
        account = await get_microsoft_account(item.microsoft_account_id)
    else:
        account = await get_google_account(item.google_account_id)
    return account.email if account else ""


async def _sort_candidates_by_sender_priority(candidates: list[ScanCandidate]) -> list[ScanCandidate]:
    enriched: list[tuple[ScanCandidate, object]] = []
    for candidate in candidates:
        context = await get_sender_context(candidate.from_email)
        enriched.append((candidate, context))
    enriched.sort(key=lambda pair: candidate_sort_key(pair[1]), reverse=True)
    return [candidate for candidate, _ in enriched]


async def _build_draft_prompt_context(
    *,
    item: EmailAgentItem,
    conversation,
    session: MailSession,
) -> tuple[str, str, str, dict]:
    profile_block = await get_profile_block_with_defaults(item.user_id)

    sender_context = await get_sender_context(item.sender_email, user_id=item.user_id)
    sender_context_block = format_sender_context_block(sender_context)

    from app.db.user_email_profile import get_profile

    profile = await get_profile(item.user_id)
    timezone = profile.timezone if profile else "America/Los_Angeles"

    scheduling = detect_scheduling(
        subject=item.subject or conversation.subject,
        conversation=conversation,
        reply_to_message_id=item.gmail_message_id,
    )

    if session.provider == "google":
        credentials = load_credentials(item.google_account_id)
        granted = get_granted_services(item.google_account_id)
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


async def _queue_candidate(
    *,
    mail_provider: str,
    account_id: str,
    candidate: ScanCandidate,
    account_email: str,
    conversation,
) -> tuple[int, int, int]:
    """Queue a candidate. Returns (priority_queued, drafted, browse_queued)."""
    sender_context = await get_sender_context(candidate.from_email)
    always_urgent = bool(sender_context and sender_context.always_urgent)
    summary = candidate.snippet
    should_priority = False

    if candidate.is_unread:
        if always_urgent:
            should_priority = True
        else:
            needs_reply, classified_summary = classify_needs_reply(
                account_email=account_email,
                subject=candidate.subject,
                from_email=candidate.from_email,
                snippet=candidate.snippet,
                conversation=conversation,
                reply_to_message_id=candidate.message_id,
            )
            summary = classified_summary or summary
            should_priority = needs_reply

    create_kwargs: dict = {
        "mail_provider": mail_provider,
        "gmail_thread_id": candidate.thread_id,
        "gmail_message_id": candidate.message_id,
        "sender_name": candidate.from_name,
        "sender_email": candidate.from_email,
        "subject": candidate.subject,
        "summary": summary or candidate.snippet,
    }
    if mail_provider == "microsoft":
        create_kwargs["microsoft_account_id"] = account_id
    else:
        create_kwargs["google_account_id"] = account_id

    if should_priority and await count_priority_items() < agent_settings.MAX_PRIORITY_QUEUE_SIZE:
        create_kwargs["status"] = "needs_draft"
        item = await create_item(**create_kwargs)
        try:
            await draft_item(item.id)
            return 1, 1, 0
        except Exception as exc:
            logger.exception("Failed to draft item %s: %s", item.id, exc)
            await _discard_failed_item(item.id, str(exc))
            return 1, 0, 0

    if await count_browse_items() >= agent_settings.MAX_BROWSE_QUEUE_SIZE:
        return 0, 0, 0

    create_kwargs["status"] = "listed"
    create_kwargs["summary"] = summary or candidate.snippet
    await create_item(**create_kwargs)
    return 0, 0, 1


async def _process_scan_candidate(
    candidate: ScanCandidate,
    *,
    account_email: str,
) -> tuple[bool, str | None]:
    """Returns (should_continue_scanning, skip_reason_if_any)."""
    if await count_active_items() >= agent_settings.MAX_ACTIVE_QUEUE_SIZE:
        return False, None

    if await get_item_by_message_id(candidate.message_id):
        return True, None

    should_skip, skip_reason = is_likely_automated(
        from_email=candidate.from_email,
        subject=candidate.subject,
        snippet=candidate.snippet,
    )
    if should_skip:
        return True, skip_reason

    if not is_within_reply_window(candidate.date):
        return True, f"older than {agent_settings.REPLY_MAX_AGE_DAYS} days"

    sender_context = await get_sender_context(candidate.from_email)
    if should_auto_archive(sender_context):
        return True, "auto-archive sender"

    return True, None


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


async def cleanup_old_queue_items() -> dict:
    """Discard active queue items whose target email is older than the reply window."""
    removed = 0
    for item in await list_active_items():
        try:
            session = load_mail_session(item)
            conversation = fetch_item_conversation(item, session)
            target = next(
                (message for message in conversation.messages if message.email_id == item.gmail_message_id),
                None,
            )
            if not target:
                continue
            if is_within_reply_window(target.date):
                continue
            await _discard_failed_item(
                item.id,
                f"older than {agent_settings.REPLY_MAX_AGE_DAYS} days",
            )
            removed += 1
        except Exception as exc:
            logger.warning("Could not check email age for item %s: %s", item.id, exc)
    return {"removed": removed}


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

    google_accounts = await list_google_accounts()
    microsoft_accounts = await list_microsoft_accounts()
    if not google_accounts and not microsoft_accounts:
        return {"status": "skipped", "reason": "no mail accounts connected"}

    active_count = await count_active_items()
    if active_count >= agent_settings.MAX_ACTIVE_QUEUE_SIZE:
        return {
            "status": "skipped",
            "reason": "queue full",
            "active_count": active_count,
        }

    cleanup_result = await cleanup_bad_queue_items()
    old_cleanup_result = await cleanup_old_queue_items()
    recovery_result = await recover_stuck_drafts()

    scanned = 0
    queued_priority = 0
    queued_browse = 0
    drafted = 0
    skipped_automated = 0

    for account in google_accounts:
        credentials = load_credentials(account.id)
        if not credentials:
            continue

        gmail_candidates = list_browse_candidates(
            credentials,
            account_email=account.email,
        )
        scan_candidates = [
            ScanCandidate(
                message_id=c.message_id,
                thread_id="",
                subject=c.subject,
                from_email=c.from_email,
                from_name=c.from_name,
                snippet=c.snippet,
                date=c.date,
                is_unread=c.is_unread,
            )
            for c in gmail_candidates
        ]
        scan_candidates = await _sort_candidates_by_sender_priority(scan_candidates)

        for candidate in scan_candidates:
            if await count_active_items() >= agent_settings.MAX_ACTIVE_QUEUE_SIZE:
                break

            scanned += 1
            should_continue, skip_reason = await _process_scan_candidate(
                candidate,
                account_email=account.email,
            )
            if not should_continue:
                break
            if skip_reason:
                skipped_automated += 1
                logger.info(
                    "Skipping email %s: %s",
                    candidate.message_id,
                    skip_reason,
                )
                continue

            thread_id = get_message_thread_id(credentials, candidate.message_id)
            if not thread_id:
                continue
            candidate.thread_id = thread_id

            inbound_id = gmail_latest_inbound(credentials, thread_id, account.email)
            if inbound_id != candidate.message_id:
                continue

            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
            conversation = _fetch_thread_conversation(service, thread_id)

            q_pri, d, q_browse = await _queue_candidate(
                mail_provider="google",
                account_id=account.id,
                candidate=candidate,
                account_email=account.email,
                conversation=conversation,
            )
            queued_priority += q_pri
            drafted += d
            queued_browse += q_browse

    for account in microsoft_accounts:
        token = get_access_token(account.id)
        if not token:
            continue

        raw_candidates = list_browse_inbox_candidates(
            token,
            account_email=account.email,
        )
        scan_candidates = [
            ScanCandidate(
                message_id=c["message_id"],
                thread_id=c["thread_id"],
                subject=c["subject"],
                from_email=c["from_email"],
                from_name=c.get("from_name"),
                snippet=c["snippet"],
                date=c.get("date", ""),
                is_unread=c.get("is_unread", True),
            )
            for c in raw_candidates
        ]
        scan_candidates = await _sort_candidates_by_sender_priority(scan_candidates)

        for candidate in scan_candidates:
            if await count_active_items() >= agent_settings.MAX_ACTIVE_QUEUE_SIZE:
                break

            scanned += 1
            should_continue, skip_reason = await _process_scan_candidate(
                candidate,
                account_email=account.email,
            )
            if not should_continue:
                break
            if skip_reason:
                skipped_automated += 1
                logger.info(
                    "Skipping email %s: %s",
                    candidate.message_id,
                    skip_reason,
                )
                continue

            inbound_id = outlook_latest_inbound(token, candidate.thread_id, account.email)
            if inbound_id != candidate.message_id:
                continue

            conversation = outlook_fetch_thread(token, candidate.thread_id)

            q_pri, d, q_browse = await _queue_candidate(
                mail_provider="microsoft",
                account_id=account.id,
                candidate=candidate,
                account_email=account.email,
                conversation=conversation,
            )
            queued_priority += q_pri
            drafted += d
            queued_browse += q_browse

    return {
        "status": "ok",
        "scanned": scanned,
        "queued": queued_priority + queued_browse,
        "queued_priority": queued_priority,
        "queued_browse": queued_browse,
        "drafted": drafted,
        "skipped_automated": skipped_automated,
        "cleanup": cleanup_result,
        "old_cleanup": old_cleanup_result,
        "recovery": recovery_result,
    }


async def generate_draft_for_item(item_id: str) -> EmailAgentItem:
    """Generate a draft on demand for a browse-tier email."""
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")
    if item.status != "listed":
        raise ValueError("Draft can only be generated for browse-tier emails")

    return await draft_item(item_id)


async def draft_item(item_id: str) -> EmailAgentItem:
    """Generate initial draft and welcome chat for a queued item."""
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")

    session = load_mail_session(item)
    conversation = fetch_item_conversation(item, session)
    enrich_item_attachments(session, conversation)

    account_email = await _get_account_email(item)

    sender_history = fetch_sender_history(
        item,
        session,
        account_email=account_email,
        subject=item.subject or conversation.subject,
    )

    profile_block, sender_context_block, calendar_block, draft_meta = (
        await _build_draft_prompt_context(
            item=item,
            conversation=conversation,
            session=session,
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

    session = load_mail_session(item)
    conversation = fetch_item_conversation(item, session)
    enrich_item_attachments(session, conversation)

    account_email = await _get_account_email(item)

    sender_history = fetch_sender_history(
        item,
        session,
        account_email=account_email,
        subject=item.subject or conversation.subject,
    )

    profile_block, sender_context_block, calendar_block, draft_meta = (
        await _build_draft_prompt_context(
            item=item,
            conversation=conversation,
            session=session,
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

    session = load_mail_session(item)
    participants = thread_participants(item, session)
    body = draft_response.strip()
    if not body:
        raise ValueError("Draft is empty")

    await update_item(item_id, draft_response=body, status="approved")

    sent = send_item_reply(
        item,
        session,
        to=item.sender_email,
        subject=_reply_subject(item.subject or ""),
        body=body,
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
    """Load the full mail thread for a queue item."""
    item = await get_item(item_id)
    if not item:
        raise ValueError("Item not found")

    session = load_mail_session(item)
    conversation = fetch_item_conversation(item, session)
    enrich_item_attachments(session, conversation)

    account_email = (await _get_account_email(item)).lower()

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
    await cleanup_old_queue_items()
    items = await list_active_items()
    items.sort(
        key=lambda item: (
            0 if item.status in PRIORITY_STATUSES else 1,
            _STATUS_SORT_ORDER.get(item.status, 9),
        )
    )
    result: list[dict] = []
    for item in items:
        context = await get_sender_context(item.sender_email, user_id=item.user_id)
        always_urgent = bool(context and context.always_urgent)
        result.append(item.to_api_dict(always_urgent=always_urgent))
    return result
