"""Generate and revise email reply drafts."""

from __future__ import annotations

import logging

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


def generate_initial_draft(
    *,
    conversation: EmailThreadConversation,
    account_email: str,
    sender_name: str,
    sender_email: str,
    reply_to_message_id: str | None = None,
) -> tuple[str, str]:
    """Return (summary, draft_response)."""
    thread_text = format_thread_for_reply(
        conversation,
        account_email=account_email,
        reply_to_message_id=reply_to_message_id,
    )

    user_prompt = (
        f"The user is replying from {account_email}.\n"
        f"Reply to: {sender_name} <{sender_email}>\n"
        f"Subject: {conversation.subject}\n"
        f"Messages in thread: {conversation.message_count}\n\n"
        f"Full conversation (oldest to newest):\n{thread_text}"
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
    return summary, draft


def revise_draft(
    *,
    conversation: EmailThreadConversation,
    account_email: str,
    current_draft: str,
    chat_history: list[dict[str, str]],
    user_message: str,
    reply_to_message_id: str | None = None,
) -> tuple[str, str]:
    """Return (revised_draft, assistant_acknowledgment)."""
    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-10:]
    )

    thread_text = format_thread_for_reply(
        conversation,
        account_email=account_email,
        reply_to_message_id=reply_to_message_id,
    )

    user_prompt = (
        f"Account: {account_email}\n"
        f"Subject: {conversation.subject}\n"
        f"Messages in thread: {conversation.message_count}\n\n"
        f"Full conversation (oldest to newest):\n{thread_text}\n\n"
        f"Current draft:\n{current_draft}\n\n"
        f"Adjustment chat:\n{history_text}\n\n"
        f"Latest user request:\n{user_message}"
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
    thread_text = format_thread_for_reply(
        conversation,
        account_email=account_email,
        reply_to_message_id=reply_to_message_id,
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
