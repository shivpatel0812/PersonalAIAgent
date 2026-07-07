"""AI summarization of omitted middle messages in long email threads."""

from __future__ import annotations

import logging

from app.agents.email_agent.json_utils import parse_json_response
from app.agents.email_agent.thread_context import format_messages_compact
from app.ai.openai_client import chat_messages
from app.ai.tools.gmail_tool import ThreadMessage

logger = logging.getLogger(__name__)

SUMMARIZE_SYSTEM_PROMPT = """You summarize omitted middle messages from an email thread.

Extract only facts explicitly stated in the messages:
- Dates, amounts, decisions, commitments
- Documents or attachments mentioned or sent
- Open questions and who asked them
- What the user already provided vs what is still being requested

Do not invent details. Be concise (3-6 sentences max).

Return ONLY valid JSON:
{"summary": "Messages N-M summary: ..."}
"""


def summarize_omitted_messages(
    messages: list[ThreadMessage],
    *,
    start_index: int,
    end_index: int,
) -> str:
    if not messages:
        return ""

    compact = format_messages_compact(messages)
    user_prompt = (
        f"Summarize emails {start_index} through {end_index} in the thread:\n\n{compact}"
    )

    try:
        response = chat_messages(
            [
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
        )
        result = parse_json_response(response)
        summary = str(result.get("summary", "")).strip()
        if summary:
            return summary
    except Exception as exc:
        logger.warning("Middle thread summarization failed: %s", exc)

    return (
        f"[Messages {start_index}–{end_index} summary: "
        f"{len(messages)} middle messages omitted — see opening and recent emails below.]"
    )
