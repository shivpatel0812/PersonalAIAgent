"""Database operations for the Email Agent reply queue."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from app.supabase_client import get_supabase_client

EmailAgentStatus = Literal[
    "needs_draft",
    "draft_ready",
    "waiting_on_you",
    "approved",
    "sent",
    "discarded",
]

ACTIVE_STATUSES = ("needs_draft", "draft_ready", "waiting_on_you")


class EmailAgentItem:
    def __init__(self, row: dict[str, Any]):
        self.id = row["id"]
        self.user_id = row.get("user_id", "default")
        self.google_account_id = row.get("google_account_id")
        self.gmail_thread_id = row["gmail_thread_id"]
        self.gmail_message_id = row["gmail_message_id"]
        self.sender_name = row.get("sender_name")
        self.sender_email = row["sender_email"]
        self.subject = row.get("subject")
        self.summary = row.get("summary")
        self.draft_response = row.get("draft_response")
        self.status: EmailAgentStatus = row["status"]
        self.created_at = row.get("created_at")
        self.updated_at = row.get("updated_at")
        self.sent_at = row.get("sent_at")
        self.sent_gmail_message_id = row.get("sent_gmail_message_id")

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "senderName": self.sender_name or self.sender_email,
            "senderEmail": self.sender_email,
            "subject": self.subject or "(No subject)",
            "summary": self.summary or "",
            "gmailUrl": f"https://mail.google.com/mail/u/0/#inbox/{self.gmail_message_id}",
            "draftResponse": self.draft_response or "",
            "status": self.status,
        }


class EmailAgentChatMessage:
    def __init__(self, row: dict[str, Any]):
        self.id = row["id"]
        self.item_id = row["item_id"]
        self.role = row["role"]
        self.content = row["content"]
        self.created_at = row.get("created_at")

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "role": self.role,
            "content": self.content,
        }


def _row_to_item(row: dict[str, Any]) -> EmailAgentItem:
    return EmailAgentItem(row)


async def list_active_items(user_id: str = "default") -> list[EmailAgentItem]:
    supabase = get_supabase_client()
    result = (
        supabase.table("email_agent_items")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", list(ACTIVE_STATUSES))
        .order("created_at", desc=True)
        .execute()
    )
    return [_row_to_item(row) for row in result.data]


async def get_item(item_id: str) -> EmailAgentItem | None:
    supabase = get_supabase_client()
    result = supabase.table("email_agent_items").select("*").eq("id", item_id).execute()
    if not result.data:
        return None
    return _row_to_item(result.data[0])


async def get_item_by_message_id(gmail_message_id: str) -> EmailAgentItem | None:
    supabase = get_supabase_client()
    result = (
        supabase.table("email_agent_items")
        .select("*")
        .eq("gmail_message_id", gmail_message_id)
        .execute()
    )
    if not result.data:
        return None
    return _row_to_item(result.data[0])


async def create_item(
    *,
    google_account_id: str,
    gmail_thread_id: str,
    gmail_message_id: str,
    sender_name: str | None,
    sender_email: str,
    subject: str | None,
    summary: str | None = None,
    draft_response: str | None = None,
    status: EmailAgentStatus = "needs_draft",
    user_id: str = "default",
) -> EmailAgentItem:
    supabase = get_supabase_client()
    payload: dict[str, Any] = {
        "user_id": user_id,
        "google_account_id": google_account_id,
        "gmail_thread_id": gmail_thread_id,
        "gmail_message_id": gmail_message_id,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "subject": subject,
        "summary": summary,
        "draft_response": draft_response,
        "status": status,
    }
    result = supabase.table("email_agent_items").insert(payload).execute()
    return _row_to_item(result.data[0])


async def update_item(item_id: str, **fields: Any) -> EmailAgentItem | None:
    if not fields:
        return await get_item(item_id)

    supabase = get_supabase_client()
    result = supabase.table("email_agent_items").update(fields).eq("id", item_id).execute()
    if not result.data:
        return None
    return _row_to_item(result.data[0])


async def list_chat_messages(item_id: str) -> list[EmailAgentChatMessage]:
    supabase = get_supabase_client()
    result = (
        supabase.table("email_agent_chat_messages")
        .select("*")
        .eq("item_id", item_id)
        .order("created_at")
        .execute()
    )
    return [EmailAgentChatMessage(row) for row in result.data]


async def add_chat_message(
    item_id: str,
    *,
    role: Literal["user", "assistant"],
    content: str,
) -> EmailAgentChatMessage:
    supabase = get_supabase_client()
    result = (
        supabase.table("email_agent_chat_messages")
        .insert({"item_id": item_id, "role": role, "content": content})
        .execute()
    )
    return EmailAgentChatMessage(result.data[0])


async def count_active_items(user_id: str = "default") -> int:
    items = await list_active_items(user_id=user_id)
    return len(items)
