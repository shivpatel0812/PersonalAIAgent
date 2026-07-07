"""Detect scheduling intent and build calendar availability blocks."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.json_utils import parse_json_response
from app.ai.openai_client import chat_messages
from app.ai.tools.gmail_tool import EmailThreadConversation
from app.google.calendar_service import check_slot, find_free_slots_text, has_calendar_scope

logger = logging.getLogger(__name__)

_SCHEDULING_KEYWORDS = re.compile(
    r"\b("
    r"meet(?:ing)?|call|schedule|scheduling|availability|available|calendar|"
    r"time works|free to|catch up|zoom|teams|google meet|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"tomorrow|next week|this week"
    r")\b",
    re.IGNORECASE,
)
_TIME_PATTERN = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", re.IGNORECASE)

EXTRACT_SYSTEM_PROMPT = """Extract scheduling details from an email thread excerpt.

Return ONLY valid JSON:
{
  "is_scheduling": true,
  "proposed_times": ["Tuesday 3pm", "2026-07-10T15:00:00"],
  "duration_minutes": 60
}

Rules:
- is_scheduling: true only if someone is asking to meet, call, or coordinate times
- proposed_times: list of natural-language or ISO datetime strings mentioned
- duration_minutes: inferred meeting length (default 60)
- Do not invent times not mentioned in the email
"""


@dataclass
class SchedulingContext:
    detected: bool = False
    is_scheduling: bool = False
    proposed_times: list[str] = field(default_factory=list)
    duration_minutes: int = 60
    calendar_connected: bool = False
    calendar_checked: bool = False
    availability_block: str = ""


def _collect_thread_text(
    subject: str,
    conversation: EmailThreadConversation,
    reply_to_message_id: str | None,
) -> str:
    parts = [subject]
    for message in conversation.messages:
        if reply_to_message_id and message.email_id != reply_to_message_id:
            continue
        parts.append(message.body)
    if len(parts) == 1:
        for message in conversation.messages[-3:]:
            parts.append(message.body)
    return "\n".join(parts)


def heuristic_might_be_scheduling(subject: str, text: str) -> bool:
    combined = f"{subject}\n{text}"
    if _SCHEDULING_KEYWORDS.search(combined):
        return True
    return bool(_TIME_PATTERN.search(combined))


def extract_scheduling_details(subject: str, text: str) -> SchedulingContext:
    if not agent_settings.SCHEDULING_DETECTION_ENABLED:
        return SchedulingContext()

    if not heuristic_might_be_scheduling(subject, text):
        return SchedulingContext()

    user_prompt = f"Subject: {subject}\n\nEmail content:\n{text[:6000]}"

    try:
        response = chat_messages(
            [
                {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
        )
        result = parse_json_response(response)
        is_scheduling = bool(result.get("is_scheduling"))
        proposed = result.get("proposed_times") or []
        if isinstance(proposed, str):
            proposed = [proposed]
        proposed_times = [str(item).strip() for item in proposed if str(item).strip()]
        duration = int(result.get("duration_minutes") or 60)
        return SchedulingContext(
            detected=True,
            is_scheduling=is_scheduling,
            proposed_times=proposed_times,
            duration_minutes=max(15, duration),
        )
    except Exception as exc:
        logger.warning("Scheduling extraction failed: %s", exc)
        return SchedulingContext(
            detected=True,
            is_scheduling=heuristic_might_be_scheduling(subject, text),
        )


def detect_scheduling(
    *,
    subject: str,
    conversation: EmailThreadConversation,
    reply_to_message_id: str | None = None,
) -> SchedulingContext:
    text = _collect_thread_text(subject, conversation, reply_to_message_id)
    return extract_scheduling_details(subject, text)


def build_calendar_availability_block(
    credentials,
    scheduling: SchedulingContext,
    *,
    granted_scopes: list[str],
    timezone: str,
) -> SchedulingContext:
    if not scheduling.is_scheduling:
        return scheduling

    scheduling.calendar_connected = has_calendar_scope(granted_scopes)

    if not scheduling.calendar_connected:
        scheduling.availability_block = (
            "Calendar not connected — draft a generic scheduling reply asking for times."
        )
        return scheduling

    lines = [f"Calendar availability ({timezone}):"]

    free_slots = find_free_slots_text(
        credentials,
        days=agent_settings.CALENDAR_AVAILABILITY_DAYS,
        duration_minutes=scheduling.duration_minutes,
        timezone=timezone,
    )
    lines.append(free_slots)

    for proposed in scheduling.proposed_times[:5]:
        iso_candidate = proposed
        if "T" not in proposed:
            lines.append(f'- Mentioned time "{proposed}" (verify against free slots above)')
            continue
        lines.append(
            check_slot(
                credentials,
                iso_candidate,
                duration_minutes=scheduling.duration_minutes,
                timezone=timezone,
            )
        )

    block = "\n".join(line for line in lines if line)
    max_chars = agent_settings.CALENDAR_BLOCK_MAX_CHARS
    if len(block) > max_chars:
        block = block[:max_chars] + "\n...[truncated]"

    scheduling.calendar_checked = True
    scheduling.availability_block = block
    return scheduling
