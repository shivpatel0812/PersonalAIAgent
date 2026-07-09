"""Append-only feedback events for the Find feature."""

from __future__ import annotations

from typing import Any

from app.supabase_client import get_supabase_client


def log_feedback_event(
    *,
    session_id: str,
    event_type: str,
    user_message: str | None = None,
    request_before: dict[str, Any] | None = None,
    request_after: dict[str, Any] | None = None,
    results_shown: list[dict[str, Any]] | None = None,
    search_query: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    row = {
        "session_id": session_id,
        "event_type": event_type,
        "user_message": user_message,
        "request_before": request_before,
        "request_after": request_after,
        "results_shown": results_shown,
        "search_query": search_query,
        "metadata": metadata or {},
    }
    client.table("find_feedback_events").insert(row).execute()
