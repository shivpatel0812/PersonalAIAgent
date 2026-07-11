from datetime import datetime

from app.ai.agent.loop import AgentStep
from app.supabase_client import get_supabase_client

VALID_PAGE_TYPES = {"stocks", "personal", "general"}

PAGE_TITLES = {
    "stocks": "Stock Research",
    "personal": "Personal Assistant",
    "general": "General Research",
}

DEFAULT_THREAD_TITLE = "New chat"

PAGE_CONTEXT = {
    "stocks": (
        "You are on the Stock Research page. Help with portfolio analysis, "
        "market news, company research, and investment decisions. "
        "If Robinhood MCP is connected, use robinhood_* tools for live portfolio data and quotes."
    ),
    "personal": (
        "You are on the Personal Assistant page. Help with personal planning, "
        "decisions, research, and day-to-day questions tailored to the user."
    ),
    "general": (
        "You are on the General Research page. Help with any open-ended "
        "research topic."
    ),
}

MAX_HISTORY_TURNS = 10
MAX_MESSAGE_CHARS = 2000
MAX_TITLE_CHARS = 56

GENERIC_THREAD_TITLES = set(PAGE_TITLES.values()) | {DEFAULT_THREAD_TITLE}


def validate_page_type(page_type: str) -> str:
    if page_type not in VALID_PAGE_TYPES:
        raise ValueError(f"Invalid page_type: {page_type}")
    return page_type


def _derive_title(content: str, max_chars: int = MAX_TITLE_CHARS) -> str:
    cleaned = " ".join(content.split())
    if not cleaned:
        return DEFAULT_THREAD_TITLE
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def list_threads(page_type: str, limit: int = 50, *, user_id: str = "default") -> list[dict]:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    page_type = validate_page_type(page_type)

    response = (
        client.table("conversation_threads")
        .select("id, page_type, title, created_at, updated_at, user_id")
        .eq("page_type", page_type)
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def create_thread(
    page_type: str,
    title: str | None = None,
    *,
    user_id: str = "default",
) -> dict:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    page_type = validate_page_type(page_type)
    thread_title = title.strip() if title and title.strip() else DEFAULT_THREAD_TITLE

    created = (
        client.table("conversation_threads")
        .insert({"page_type": page_type, "title": thread_title, "user_id": user_id})
        .execute()
    )

    if not created.data:
        raise ValueError(f"Failed to create thread for page_type: {page_type}")

    return created.data[0]


def get_thread_by_id(thread_id: str, *, user_id: str | None = None) -> dict | None:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    query = (
        client.table("conversation_threads")
        .select("id, page_type, title, created_at, updated_at, user_id")
        .eq("id", thread_id)
    )
    if user_id is not None:
        query = query.eq("user_id", user_id)
    response = query.limit(1).execute()
    if not response.data:
        return None
    return response.data[0]


def get_most_recent_thread(page_type: str, *, user_id: str = "default") -> dict | None:
    threads = list_threads(page_type, limit=1, user_id=user_id)
    return threads[0] if threads else None


def get_or_create_thread(page_type: str, *, user_id: str = "default") -> dict:
    """Return the most recent thread for a page, creating one if none exist."""
    existing = get_most_recent_thread(page_type, user_id=user_id)
    if existing:
        return existing
    return create_thread(
        page_type,
        title=PAGE_TITLES.get(page_type, DEFAULT_THREAD_TITLE),
        user_id=user_id,
    )


def delete_thread(thread_id: str, *, user_id: str | None = None) -> None:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    query = client.table("conversation_threads").delete().eq("id", thread_id)
    if user_id is not None:
        query = query.eq("user_id", user_id)
    query.execute()


def get_thread_messages(thread_id: str) -> list[dict]:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    response = (
        client.table("conversation_messages")
        .select("id, role, content, steps, run_id, source, created_at")
        .eq("thread_id", thread_id)
        .order("created_at")
        .execute()
    )
    return response.data or []


def get_conversation(page_type: str, *, user_id: str = "default") -> dict:
    """Backward-compatible: returns the most recent thread for a page."""
    thread = get_or_create_thread(page_type, user_id=user_id)
    return get_conversation_by_thread_id(thread["id"], user_id=user_id)


def get_conversation_by_thread_id(thread_id: str, *, user_id: str | None = None) -> dict:
    thread = get_thread_by_id(thread_id, user_id=user_id)
    if thread is None:
        raise ValueError(f"Thread not found: {thread_id}")

    messages = get_thread_messages(thread_id)
    return {
        "thread_id": thread["id"],
        "page_type": thread["page_type"],
        "title": thread["title"],
        "updated_at": thread["updated_at"],
        "messages": messages,
    }


def format_history_for_agent(messages: list[dict]) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []

    for message in messages:
        if message.get("role") not in ("user", "assistant"):
            continue

        content = message.get("content", "")
        if len(content) > MAX_MESSAGE_CHARS:
            content = content[: MAX_MESSAGE_CHARS - 1].rstrip() + "…"

        history.append({"role": message["role"], "content": content})

    max_messages = MAX_HISTORY_TURNS * 2
    return history[-max_messages:]


def _maybe_update_thread_title(thread_id: str, user_content: str) -> None:
    thread = get_thread_by_id(thread_id)
    if thread is None:
        return

    if thread["title"] not in GENERIC_THREAD_TITLES:
        return

    client = get_supabase_client()
    if client is None:
        return

    client.table("conversation_threads").update(
        {
            "title": _derive_title(user_content),
            "updated_at": datetime.utcnow().isoformat(),
        }
    ).eq("id", thread_id).execute()


def append_conversation_turn(
    thread_id: str,
    user_content: str,
    assistant_content: str,
    steps: list[AgentStep] | None = None,
    run_id: str | None = None,
) -> None:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    step_payload = [step.model_dump() for step in (steps or [])]

    client.table("conversation_messages").insert(
        [
            {
                "thread_id": thread_id,
                "role": "user",
                "content": user_content,
                "steps": [],
                "source": "user",
            },
            {
                "thread_id": thread_id,
                "role": "assistant",
                "content": assistant_content,
                "steps": step_payload,
                "run_id": run_id,
                "source": "agent",
            },
        ]
    ).execute()

    client.table("conversation_threads").update(
        {"updated_at": datetime.utcnow().isoformat()}
    ).eq("id", thread_id).execute()

    _maybe_update_thread_title(thread_id, user_content)
