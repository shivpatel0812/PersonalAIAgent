"""Format Gmail thread context for Email Agent prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.attachments import format_attachment_lines
from app.ai.tools.gmail_tool import EmailThreadConversation, ThreadMessage


@dataclass
class ThreadSelection:
    selected: list[ThreadMessage]
    omitted_middle: bool
    middle_messages: list[ThreadMessage]
    middle_start_index: int
    middle_end_index: int


def _normalize_email(email: str) -> str:
    email = email.strip().lower()
    match = re.search(r"<([^>]+)>", email)
    if match:
        return match.group(1).strip().lower()
    return email


def _is_user_message(from_email: str, account_email: str) -> bool:
    return _normalize_email(account_email) in _normalize_email(from_email)


def _message_char_weight(message: ThreadMessage, per_message_limit: int) -> int:
    body_len = min(len(message.body.strip()), per_message_limit)
    attachment_len = sum(
        len(line) for line in format_attachment_lines(message)
    )
    return body_len + attachment_len + 200


def _trim_body(body: str, limit: int) -> str:
    body = body.strip()
    if len(body) <= limit:
        return body
    return body[:limit] + "\n...[truncated]"


def select_messages_for_prompt(
    messages: list[ThreadMessage],
    *,
    max_prompt_chars: int | None = None,
    per_message_limit: int | None = None,
) -> ThreadSelection:
    """Return messages to include and any omitted middle slice."""
    max_prompt_chars = max_prompt_chars or agent_settings.MAX_PROMPT_CHARS
    per_message_limit = per_message_limit or agent_settings.PER_MESSAGE_BODY_CHARS

    if not messages:
        return ThreadSelection([], False, [], 0, 0)

    total = sum(_message_char_weight(message, per_message_limit) for message in messages)
    if total <= max_prompt_chars or len(messages) <= 12:
        return ThreadSelection(messages, False, [], 0, 0)

    head = messages[:2]
    tail = messages[-10:]
    middle = messages[2:-10]
    if not middle:
        return ThreadSelection(messages, False, [], 0, 0)

    return ThreadSelection(
        selected=head + tail,
        omitted_middle=True,
        middle_messages=middle,
        middle_start_index=3,
        middle_end_index=len(messages) - 10,
    )


def format_messages_compact(messages: list[ThreadMessage]) -> str:
    lines: list[str] = []
    for index, message in enumerate(messages, start=1):
        attachment_text = "\n".join(format_attachment_lines(message))
        lines.append(
            f"[Email {index}]\n"
            f"From: {message.from_email}\n"
            f"Date: {message.date}\n"
            f"Subject: {message.subject}\n"
            f"{_trim_body(message.body, 1500)}\n"
            f"{attachment_text}\n"
        )
    return "\n---\n".join(lines)


def _resolve_middle_summary(
    selection: ThreadSelection,
    cached_summary: str | None,
) -> str | None:
    if not selection.omitted_middle:
        return None
    if cached_summary:
        return cached_summary
    if not agent_settings.MIDDLE_SUMMARY_ENABLED or not selection.middle_messages:
        skipped = len(selection.middle_messages)
        return (
            f"[Note: {skipped} older middle messages omitted for length — "
            "key opening messages and recent replies are included below.]"
        )
    from app.agents.email_agent.thread_summarizer import summarize_omitted_messages

    return summarize_omitted_messages(
        selection.middle_messages,
        start_index=selection.middle_start_index,
        end_index=selection.middle_end_index,
    )


def format_thread_for_reply(
    conversation: EmailThreadConversation,
    *,
    account_email: str,
    reply_to_message_id: str | None = None,
    max_prompt_chars: int | None = None,
    per_message_limit: int | None = None,
    include_attachment_text: bool = True,
    cached_middle_summary: str | None = None,
    sender_history_block: str = "",
) -> tuple[str, str | None]:
    """
    Build chronological thread context for drafting.

    Returns (prompt_text, middle_summary_for_cache).
    """
    per_message_limit = per_message_limit or agent_settings.PER_MESSAGE_BODY_CHARS
    selection = select_messages_for_prompt(
        conversation.messages,
        max_prompt_chars=max_prompt_chars,
        per_message_limit=per_message_limit,
    )
    middle_summary = _resolve_middle_summary(selection, cached_middle_summary)

    lines: list[str] = []
    if sender_history_block:
        lines.append(sender_history_block)
        lines.append("")

    if middle_summary:
        lines.append(middle_summary)
        lines.append("")

    total_messages = len(conversation.messages)
    head_count = 2 if selection.omitted_middle else 0
    tail_start = total_messages - (len(selection.selected) - head_count) + 1 if selection.omitted_middle else 1

    for position, message in enumerate(selection.selected):
        if selection.omitted_middle and position < head_count:
            index = position + 1
        elif selection.omitted_middle:
            index = tail_start + (position - head_count)
        else:
            index = position + 1

        role = "YOUR PRIOR MESSAGE" if _is_user_message(message.from_email, account_email) else "INBOUND"
        target_marker = ""
        if reply_to_message_id and message.email_id == reply_to_message_id:
            target_marker = " <<< REPLY TO THIS MESSAGE >>>"

        attachment_lines = format_attachment_lines(message) if include_attachment_text else []
        attachment_block = ""
        if attachment_lines:
            attachment_block = "\n" + "\n".join(attachment_lines)

        lines.append(
            f"[Email {index} | {role}{target_marker}]\n"
            f"From: {message.from_email}\n"
            f"To: {message.to_email or ''}\n"
            f"Date: {message.date}\n"
            f"Subject: {message.subject}\n\n"
            f"{_trim_body(message.body, per_message_limit)}"
            f"{attachment_block}\n"
        )

    summary_to_cache = middle_summary if selection.omitted_middle and not cached_middle_summary else None
    return "\n---\n".join(lines), summary_to_cache


DRAFT_SYSTEM_PROMPT = """You draft email replies for the user to review before sending.

Critical rules:
- Read the ENTIRE thread chronologically before writing
- The user may have already answered questions or sent documents in earlier emails — do not ask for them again
- Reference specific facts, attachments, amounts, dates, and commitments from earlier messages when relevant
- Reply only to the latest inbound message marked "REPLY TO THIS MESSAGE", using earlier emails for context
- Write a complete, send-ready plain-text reply
- Match a professional but natural tone
- Do not invent facts; if unsure, keep the reply appropriately vague
- Sign off with the user's configured sign-off from the profile block; match their communication style
- When a calendar availability block is present, use only those times — do not invent availability

Return ONLY valid JSON: {"summary": "...", "draft": "..."}
"""

REVISE_SYSTEM_PROMPT = """You revise an email draft based on user feedback.

Use the full thread history — especially the user's earlier messages — so the reply stays consistent with what was already said or sent.

Return ONLY valid JSON:
{
  "draft": "full revised plain-text email ready to send",
  "assistant_message": "brief note to the user about what you changed"
}
"""

CLASSIFY_SYSTEM_PROMPT = """You decide whether an email needs a reply from the user.

Read the full thread excerpt chronologically. Earlier emails may contain context for what the latest message is asking about.

Reply YES only when:
- A real person asked a question or requested action from the user in the latest inbound message
- A meeting, deadline, or decision clearly needs the user's response
- A personal or professional follow-up is expected

Reply NO for:
- Login alerts, security notices, verification codes, password resets
- GitHub/Vercel/deployment/CI notifications, receipts, shipping updates
- Newsletters, marketing, digests, automated system mail, FYI-only messages
- Threads where the user already sent the information being requested in a prior message
- Anything where replying would go to a no-reply address or is not expected

When unsure, reply NO.

Return ONLY valid JSON:
{"needs_reply": true, "summary": "1-2 sentence summary referencing thread context"}
or
{"needs_reply": false, "summary": ""}
"""
