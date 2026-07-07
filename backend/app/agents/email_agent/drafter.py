"""Generate and revise email reply drafts."""

from __future__ import annotations

import logging

from app.agents.email_agent.json_utils import parse_json_response
from app.ai.openai_client import chat_messages
from app.ai.tools.gmail_tool import EmailThreadConversation

logger = logging.getLogger(__name__)


def _format_thread(conversation: EmailThreadConversation) -> str:
    lines = []
    for message in conversation.messages:
        lines.append(
            f"From: {message.from_email}\n"
            f"To: {message.to_email or ''}\n"
            f"Date: {message.date}\n"
            f"Subject: {message.subject}\n\n"
            f"{message.body}\n"
        )
    return "\n---\n".join(lines)


def generate_initial_draft(
    *,
    conversation: EmailThreadConversation,
    account_email: str,
    sender_name: str,
    sender_email: str,
) -> tuple[str, str]:
    """Return (summary, draft_response)."""
    system_prompt = """You draft email replies for the user to review before sending.

Rules:
- Write a complete, send-ready plain-text reply
- Match a professional but natural tone
- Do not invent facts; if unsure, keep the reply appropriately vague
- Sign off with the user's first name if you can infer it from their email, otherwise "Best,"
- Return ONLY valid JSON: {"summary": "...", "draft": "..."}
"""

    user_prompt = (
        f"The user is replying from {account_email}.\n"
        f"Reply to: {sender_name} <{sender_email}>\n"
        f"Subject: {conversation.subject}\n\n"
        f"Thread:\n{_format_thread(conversation)}"
    )

    response = chat_messages(
        [
            {"role": "system", "content": system_prompt},
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
) -> tuple[str, str]:
    """Return (revised_draft, assistant_acknowledgment)."""
    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-10:]
    )

    system_prompt = """You revise an email draft based on user feedback.

Return ONLY valid JSON:
{
  "draft": "full revised plain-text email ready to send",
  "assistant_message": "brief note to the user about what you changed"
}
"""

    user_prompt = (
        f"Account: {account_email}\n"
        f"Subject: {conversation.subject}\n\n"
        f"Thread context:\n{_format_thread(conversation)[-4000:]}\n\n"
        f"Current draft:\n{current_draft}\n\n"
        f"Adjustment chat:\n{history_text}\n\n"
        f"Latest user request:\n{user_message}"
    )

    response = chat_messages(
        [
            {"role": "system", "content": system_prompt},
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
