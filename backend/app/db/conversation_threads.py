from datetime import datetime

from app.ai.agent.loop import AgentStep
from app.supabase_client import get_supabase_client

VALID_PAGE_TYPES = {"stocks", "personal", "general"}

PAGE_TITLES = {
    "stocks": "Stock Research",
    "personal": "Personal Assistant",
    "general": "General Research",
}

PAGE_CONTEXT = {
    "stocks": (
        "You are on the Stock Research page. Help with portfolio analysis, "
        "market news, company research, and investment decisions."
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


def validate_page_type(page_type: str) -> str:
    if page_type not in VALID_PAGE_TYPES:
        raise ValueError(f"Invalid page_type: {page_type}")
    return page_type


def get_or_create_thread(page_type: str) -> dict:
    client = get_supabase_client()
    if client is None:
        raise ValueError("Supabase is not configured")

    page_type = validate_page_type(page_type)

    existing = (
        client.table("conversation_threads")
        .select("id, page_type, title, created_at, updated_at")
        .eq("page_type", page_type)
        .limit(1)
        .execute()
    )

    if existing.data:
        return existing.data[0]

    created = (
        client.table("conversation_threads")
        .insert({"page_type": page_type, "title": PAGE_TITLES[page_type]})
        .execute()
    )

    if not created.data:
        raise ValueError(f"Failed to create thread for page_type: {page_type}")

    return created.data[0]


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


def get_conversation(page_type: str) -> dict:
    thread = get_or_create_thread(page_type)
    messages = get_thread_messages(thread["id"])
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
