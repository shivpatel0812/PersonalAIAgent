"""Format Gmail thread context for Email Agent prompts."""

from __future__ import annotations

import re

from app.ai.tools.gmail_tool import EmailThreadConversation, ThreadMessage

MAX_PROMPT_CHARS = 28_000
PER_MESSAGE_BODY_CHARS = 4_000


def _normalize_email(email: str) -> str:
    email = email.strip().lower()
    match = re.search(r"<([^>]+)>", email)
    if match:
        return match.group(1).strip().lower()
    return email


def _is_user_message(from_email: str, account_email: str) -> bool:
    return _normalize_email(account_email) in _normalize_email(from_email)


def _trim_body(body: str, limit: int = PER_MESSAGE_BODY_CHARS) -> str:
    body = body.strip()
    if len(body) <= limit:
        return body
    return body[:limit] + "\n...[truncated]"


def _select_messages_for_prompt(
    messages: list[ThreadMessage],
) -> tuple[list[ThreadMessage], bool]:
    """Return messages to include, and whether middle messages were omitted."""
    if not messages:
        return [], False

    chunks: list[str] = []
    for message in messages:
        chunks.append(_trim_body(message.body))

    total = sum(len(chunk) for chunk in chunks)
    if total <= MAX_PROMPT_CHARS:
        return messages, False

    # Long thread: keep opening context + recent back-and-forth
    if len(messages) <= 12:
        return messages, False

    head = messages[:2]
    tail = messages[-10:]
    omitted = len(messages) - len(head) - len(tail)
    if omitted <= 0:
        return messages, False

    return head + tail, True


def format_thread_for_reply(
    conversation: EmailThreadConversation,
    *,
    account_email: str,
    reply_to_message_id: str | None = None,
) -> str:
    """
    Build chronological thread context for drafting.

    Labels the user's prior messages and the specific inbound message being replied to.
    """
    selected, omitted_middle = _select_messages_for_prompt(conversation.messages)
    lines: list[str] = []

    if omitted_middle:
        skipped = len(conversation.messages) - len(selected)
        lines.append(
            f"[Note: {skipped} older middle messages omitted for length — "
            "key opening messages and recent replies are included below.]\n"
        )

    for index, message in enumerate(selected, start=1):
        role = "YOUR PRIOR MESSAGE" if _is_user_message(message.from_email, account_email) else "INBOUND"
        target_marker = ""
        if reply_to_message_id and message.email_id == reply_to_message_id:
            target_marker = " <<< REPLY TO THIS MESSAGE >>>"

        lines.append(
            f"[Email {index} | {role}{target_marker}]\n"
            f"From: {message.from_email}\n"
            f"To: {message.to_email or ''}\n"
            f"Date: {message.date}\n"
            f"Subject: {message.subject}\n\n"
            f"{_trim_body(message.body)}\n"
        )

    return "\n---\n".join(lines)


DRAFT_SYSTEM_PROMPT = """You draft email replies for the user to review before sending.

Critical rules:
- Read the ENTIRE thread chronologically before writing
- The user may have already answered questions or sent documents in earlier emails — do not ask for them again
- Reference specific facts, attachments, amounts, dates, and commitments from earlier messages when relevant
- Reply only to the latest inbound message marked "REPLY TO THIS MESSAGE", using earlier emails for context
- Write a complete, send-ready plain-text reply
- Match a professional but natural tone
- Do not invent facts; if unsure, keep the reply appropriately vague
- Sign off with the user's first name if you can infer it from their email, otherwise "Best,"

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
