"""Fetch recent email threads with the same sender for draft context."""

from __future__ import annotations

import logging
import re

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.filters import is_likely_automated
from app.agents.email_agent.thread_context import format_messages_compact
from app.ai.tools.gmail_tool import _fetch_thread_conversation, _headers_from_message

logger = logging.getLogger(__name__)

_SUBJECT_PREFIX_RE = re.compile(r"^(re|fw|fwd)\s*:\s*", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "hi",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "re",
        "the",
        "to",
        "was",
        "we",
        "with",
        "you",
        "your",
    }
)


def _normalize_email(email: str) -> str:
    email = email.strip().lower()
    match = re.search(r"<([^>]+)>", email)
    if match:
        return match.group(1).strip().lower()
    return email


def _subject_tokens(subject: str) -> set[str]:
    subject = _SUBJECT_PREFIX_RE.sub("", subject.strip().lower())
    while _SUBJECT_PREFIX_RE.match(subject):
        subject = _SUBJECT_PREFIX_RE.sub("", subject.strip().lower())
    tokens = {
        token
        for token in _TOKEN_RE.findall(subject)
        if len(token) >= 3 and token not in _STOP_WORDS
    }
    return tokens


def subject_relevance_score(current_subject: str, other_subject: str) -> float:
    """Return 0–1 score for whether two subjects refer to the same topic."""
    current_tokens = _subject_tokens(current_subject)
    other_tokens = _subject_tokens(other_subject)
    if not current_tokens or not other_tokens:
        return 0.0

    intersection = current_tokens & other_tokens
    union = current_tokens | other_tokens
    jaccard = len(intersection) / len(union)

    current_norm = _SUBJECT_PREFIX_RE.sub("", current_subject.strip().lower())
    other_norm = _SUBJECT_PREFIX_RE.sub("", other_subject.strip().lower())
    substring_boost = 0.0
    if current_norm and other_norm and (current_norm in other_norm or other_norm in current_norm):
        substring_boost = 0.25

    shared_boost = 0.15 if len(intersection) >= 2 else 0.0
    return min(1.0, jaccard + substring_boost + shared_boost)


def should_load_full_thread(current_subject: str, other_subject: str) -> bool:
    if not agent_settings.SENDER_HISTORY_FULL_THREAD_ENABLED:
        return False
    if not current_subject.strip():
        return False
    score = subject_relevance_score(current_subject, other_subject)
    return score >= agent_settings.SENDER_HISTORY_SUBJECT_MATCH_MIN_SCORE


def _format_full_related_thread(
    service,
    thread_id: str,
    *,
    subject: str,
    date: str,
) -> str:
    try:
        conversation = _fetch_thread_conversation(service, thread_id)
    except Exception as exc:
        logger.warning("Failed to load related thread %s: %s", thread_id, exc)
        return ""

    messages = conversation.messages
    max_messages = agent_settings.SENDER_HISTORY_FULL_THREAD_MAX_MESSAGES
    if len(messages) > max_messages:
        messages = messages[-max_messages:]

    body = format_messages_compact(messages)
    per_thread_cap = agent_settings.SENDER_HISTORY_FULL_THREAD_MAX_CHARS
    if len(body) > per_thread_cap:
        body = body[:per_thread_cap] + "\n...[truncated]"

    return (
        f"[Related thread — full context (subject match): {subject} | {date}]\n"
        f"{body}"
    )


def fetch_sender_history_block(
    service,
    *,
    sender_email: str,
    exclude_thread_id: str,
    current_subject: str = "",
) -> str:
    """Return a capped text block of recent threads with this sender."""
    if not agent_settings.SENDER_HISTORY_ENABLED:
        return ""

    sender = _normalize_email(sender_email)
    if not sender or "@" not in sender:
        return ""

    should_skip, _ = is_likely_automated(from_email=sender, subject="", snippet="")
    if should_skip:
        return ""

    query = (
        f"(from:{sender} OR to:{sender}) "
        f"newer_than:{agent_settings.SENDER_HISTORY_DAYS}d"
    )

    try:
        results = (
            service.users()
            .threads()
            .list(
                userId="me",
                q=query,
                maxResults=agent_settings.SENDER_HISTORY_MAX_THREADS + 3,
            )
            .execute()
        )
    except Exception as exc:
        logger.warning("Sender history search failed for %s: %s", sender, exc)
        return ""

    lines: list[str] = [f"Recent history with {sender} (other threads):"]
    count = 0
    full_thread_count = 0

    for thread_ref in results.get("threads") or []:
        thread_id = thread_ref.get("id")
        if not thread_id or thread_id == exclude_thread_id:
            continue

        try:
            thread = (
                service.users()
                .threads()
                .get(userId="me", id=thread_id, format="metadata")
                .execute()
            )
        except Exception:
            continue

        raw_messages = thread.get("messages") or []
        if not raw_messages:
            continue

        latest = raw_messages[-1]
        headers = _headers_from_message(latest)
        subject = headers.get("Subject", "(No subject)")
        date = headers.get("Date", "")
        snippet = latest.get("snippet", "")

        load_full = (
            full_thread_count < agent_settings.SENDER_HISTORY_MAX_FULL_THREADS
            and should_load_full_thread(current_subject, subject)
        )

        if load_full:
            full_block = _format_full_related_thread(
                service,
                thread_id,
                subject=subject,
                date=date,
            )
            if full_block:
                lines.append(full_block)
                full_thread_count += 1
                count += 1
                if count >= agent_settings.SENDER_HISTORY_MAX_THREADS:
                    break
                continue

        lines.append(f"- {date}: {subject} — {snippet}")
        count += 1
        if count >= agent_settings.SENDER_HISTORY_MAX_THREADS:
            break

    if count == 0:
        return ""

    block = "\n".join(lines)
    if len(block) > agent_settings.SENDER_HISTORY_MAX_CHARS:
        block = block[: agent_settings.SENDER_HISTORY_MAX_CHARS] + "\n...[truncated]"
    return block
