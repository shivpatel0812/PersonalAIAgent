"""Generate and revise email reply drafts."""

from __future__ import annotations

import logging

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.json_utils import parse_json_response
from app.agents.email_agent.thread_context import (
    CLASSIFY_SYSTEM_PROMPT,
    DRAFT_SYSTEM_PROMPT,
    REVISE_SYSTEM_PROMPT,
    format_thread_for_reply,
)
from app.ai.openai_client import chat_messages
from app.ai.tools.gmail_tool import EmailThreadConversation

logger = logging.getLogger(__name__)


def _prepend_context_blocks(
    *,
    profile_block: str,
    sender_context_block: str,
    calendar_block: str,
    body: str,
) -> str:
    prefix_parts = [
        block.strip()
        for block in (profile_block, sender_context_block, calendar_block)
        if block and block.strip()
    ]
    if not prefix_parts:
        return body
    return "\n\n".join(prefix_parts) + "\n\n" + body


def generate_initial_draft(
    *,
    conversation: EmailThreadConversation,
    account_email: str,
    sender_name: str,
    sender_email: str,
    reply_to_message_id: str | None = None,
    cached_middle_summary: str | None = None,
    sender_history_block: str = "",
    profile_block: str = "",
    sender_context_block: str = "",
    calendar_block: str = "",
) -> tuple[str, str, str | None]:
    """Return (summary, draft_response, middle_summary_to_cache)."""
    thread_text, summary_to_cache = format_thread_for_reply(
        conversation,
        account_email=account_email,
        reply_to_message_id=reply_to_message_id,
        cached_middle_summary=cached_middle_summary,
        sender_history_block=sender_history_block,
    )

    user_prompt = _prepend_context_blocks(
        profile_block=profile_block,
        sender_context_block=sender_context_block,
        calendar_block=calendar_block,
        body=(
            f"The user is replying from {account_email}.\n"
            f"Reply to: {sender_name} <{sender_email}>\n"
            f"Subject: {conversation.subject}\n"
            f"Messages in thread: {conversation.message_count}\n\n"
            f"Full conversation (oldest to newest):\n{thread_text}"
        ),
    )

    response = chat_messages(
        [
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1200,
    )
    result = parse_json_response(response)
    summary = str(result.get("summary", "")).strip()
    draft = str(result.get("draft", "")).strip()
    if not draft:
        raise ValueError("Model returned an empty draft")
    return summary, draft, summary_to_cache


def revise_draft(
    *,
    conversation: EmailThreadConversation,
    account_email: str,
    current_draft: str,
    chat_history: list[dict[str, str]],
    user_message: str,
    reply_to_message_id: str | None = None,
    cached_middle_summary: str | None = None,
    sender_history_block: str = "",
    profile_block: str = "",
    sender_context_block: str = "",
    calendar_block: str = "",
) -> tuple[str, str]:
    """Return (revised_draft, assistant_acknowledgment)."""
    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-10:]
    )

    thread_text, _ = format_thread_for_reply(
        conversation,
        account_email=account_email,
        reply_to_message_id=reply_to_message_id,
        cached_middle_summary=cached_middle_summary,
        sender_history_block=sender_history_block,
    )

    user_prompt = _prepend_context_blocks(
        profile_block=profile_block,
        sender_context_block=sender_context_block,
        calendar_block=calendar_block,
        body=(
            f"Account: {account_email}\n"
            f"Subject: {conversation.subject}\n"
            f"Messages in thread: {conversation.message_count}\n\n"
            f"Full conversation (oldest to newest):\n{thread_text}\n\n"
            f"Current draft:\n{current_draft}\n\n"
            f"Adjustment chat:\n{history_text}\n\n"
            f"Latest user request:\n{user_message}"
        ),
    )

    response = chat_messages(
        [
            {"role": "system", "content": REVISE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1200,
    )
    result = parse_json_response(response)
    revised = str(result.get("draft", current_draft)).strip()
    if not revised:
        raise ValueError("Model returned an empty draft")
    return (
        revised,
        str(
            result.get(
                "assistant_message",
                "I've updated the draft with your feedback. Review it on the left.",
            )
        ).strip(),
    )


def classify_needs_reply(
    *,
    account_email: str,
    subject: str,
    from_email: str,
    snippet: str,
    conversation: EmailThreadConversation,
    reply_to_message_id: str | None = None,
) -> tuple[bool, str]:
    """Use AI to decide if this email needs a human-written reply."""
    thread_text, _ = format_thread_for_reply(
        conversation,
        account_email=account_email,
        reply_to_message_id=reply_to_message_id,
        max_prompt_chars=agent_settings.CLASSIFY_MAX_PROMPT_CHARS,
        include_attachment_text=False,
    )

    user_prompt = (
        f"Account: {account_email}\n"
        f"Latest inbound from: {from_email}\n"
        f"Subject: {subject}\n"
        f"Snippet: {snippet}\n"
        f"Messages in thread: {conversation.message_count}\n\n"
        f"Thread excerpt:\n{thread_text}"
    )

    response = chat_messages(
        [
            {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=400,
    )
    result = parse_json_response(response)
    return bool(result.get("needs_reply")), str(result.get("summary", "")).strip()
