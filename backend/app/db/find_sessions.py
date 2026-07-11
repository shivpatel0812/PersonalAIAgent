"""Database operations for Find sessions and messages."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.supabase_client import get_supabase_client
from app.universal.find.models import FindMessageRecord, FindSessionState


def _client():
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")
    return client


def create_session(*, user_id: str = "default", title: str | None = None) -> dict[str, Any]:
    row = {
        "user_id": user_id,
        "title": title,
        "state": FindSessionState().model_dump(),
        "clarification_rounds": 0,
    }
    response = _client().table("find_sessions").insert(row).execute()
    if not response.data:
        raise ValueError("Failed to create find session")
    return response.data[0]


def get_session(session_id: str, *, user_id: str | None = None) -> dict[str, Any] | None:
    query = (
        _client()
        .table("find_sessions")
        .select("*")
        .eq("id", session_id)
    )
    if user_id is not None:
        query = query.eq("user_id", user_id)
    response = query.limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def load_session_state(session_id: str, *, user_id: str | None = None) -> FindSessionState:
    row = get_session(session_id, user_id=user_id)
    if row is None:
        raise ValueError(f"Session not found: {session_id}")
    raw = row.get("state") or {}
    return FindSessionState.model_validate(raw)


def save_session_state(
    session_id: str,
    state: FindSessionState,
    *,
    title: str | None = None,
    clarification_rounds: int | None = None,
) -> None:
    payload: dict[str, Any] = {"state": state.model_dump()}
    if title is not None:
        payload["title"] = title
    if clarification_rounds is not None:
        payload["clarification_rounds"] = clarification_rounds
    _client().table("find_sessions").update(payload).eq("id", session_id).execute()


def reset_session(session_id: str) -> FindSessionState:
    state = FindSessionState()
    save_session_state(session_id, state, clarification_rounds=0)
    return state


def list_messages(session_id: str) -> list[FindMessageRecord]:
    response = (
        _client()
        .table("find_messages")
        .select("id, role, content, payload, created_at")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    records: list[FindMessageRecord] = []
    for row in response.data or []:
        created = row.get("created_at")
        records.append(
            FindMessageRecord(
                id=str(row["id"]),
                role=row["role"],
                content=row["content"],
                payload=row.get("payload"),
                created_at=created if isinstance(created, str) else None,
            )
        )
    return records


def append_message(
    session_id: str,
    *,
    role: str,
    content: str,
    payload: dict[str, Any] | None = None,
) -> FindMessageRecord:
    row = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "payload": payload,
    }
    response = _client().table("find_messages").insert(row).execute()
    if not response.data:
        raise ValueError("Failed to append find message")
    created = response.data[0]
    created_at = created.get("created_at")
    return FindMessageRecord(
        id=str(created["id"]),
        role=created["role"],
        content=created["content"],
        payload=created.get("payload"),
        created_at=created_at if isinstance(created_at, str) else None,
    )


def derive_title(subject: str, max_chars: int = 56) -> str:
    cleaned = " ".join(subject.split())
    if not cleaned:
        return "New find"
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def touch_session_title(session_id: str, subject: str) -> None:
    row = get_session(session_id)
    if row is None:
        return
    if row.get("title") and row["title"] != "New find":
        return
    save_session_state(session_id, load_session_state(session_id), title=derive_title(subject))
