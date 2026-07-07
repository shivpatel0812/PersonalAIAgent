"""Intelligent email summarization with prioritization and HTML generation."""

import json
from typing import Any

from app.agents.email_recap.gmail import RecapEmail
from app.agents.email_recap.html_template import generate_email_digest_html
from app.ai.openai_client import chat_messages
from app.config import settings as app_settings


async def get_sender_priority(sender: str, user_id: str = "default") -> float:
    """Get learned priority score for a sender (-1 to 1)."""
    try:
        from app.supabase_client import get_supabase_client

        supabase = get_supabase_client()
        result = supabase.table("sender_priorities")\
            .select("priority_score")\
            .eq("user_id", user_id)\
            .eq("sender", sender)\
            .execute()

        if result.data:
            return float(result.data[0].get("priority_score", 0))
    except Exception:
        pass

    return 0.0


def categorize_emails_with_ai(emails: list[RecapEmail]) -> dict[str, list[dict]]:
    """
    Use AI to categorize emails into urgent, medium, low priority
    and generate summaries.
    """
    if not emails:
        return {"urgent": [], "medium": [], "low": []}

    # Format emails for AI
    email_data = []
    for e in emails:
        email_data.append({
            "id": e.message_id,
            "from": e.from_email,
            "from_name": e.from_name,
            "subject": e.subject,
            "snippet": e.snippet,
            "unread": e.is_unread,
            "important": e.is_important,
        })

    system_prompt = """You are an intelligent email prioritization assistant.

Analyze the provided emails and categorize each one into:
- urgent: Needs immediate attention, reply expected today, time-sensitive
- medium: Should read when you have time, not urgent
- low: FYI only, no action needed, can be skipped

For each email, provide:
- category: "urgent", "medium", or "low"
- summary: 1-2 sentences explaining what it's about and why it matters
- sender_name: Extract a clean name from the email address

Return ONLY valid JSON in this exact format:
{
  "categorized": [
    {
      "id": "email_id",
      "category": "urgent",
      "summary": "Brief summary",
      "sender_name": "Clean Name"
    }
  ]
}

Rules:
- Be concise but informative in summaries
- Focus on actionable information
- Ignore obvious spam, newsletters unless they contain urgent info
- Extract clean sender names (e.g., "John Doe" from "john.doe@example.com")
"""

    user_prompt = f"Emails to categorize:\n{json.dumps(email_data, indent=2)}"

    try:
        response = chat_messages([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], max_tokens=2000)

        # Parse AI response
        result = json.loads(response)
        categorized = result.get("categorized", [])

        # Build category maps
        urgent = []
        medium = []
        low = []

        # Create lookup dict for emails
        email_lookup = {e.message_id: e for e in emails}

        for item in categorized:
            email_id = item.get("id")
            category = item.get("category", "medium")
            summary = item.get("summary", "No summary")
            sender_name = item.get("sender_name", "")

            original_email = email_lookup.get(email_id)
            if not original_email:
                continue

            email_dict = {
                "id": email_id,
                "sender": original_email.from_email,
                "sender_name": sender_name or original_email.from_name or original_email.from_email,
                "subject": original_email.subject,
                "summary": summary,
                "message_link": f"https://mail.google.com/mail/u/0/#inbox/{email_id}",
            }

            if category == "urgent":
                urgent.append(email_dict)
            elif category == "low":
                low.append(email_dict)
            else:
                medium.append(email_dict)

        return {
            "urgent": urgent,
            "medium": medium,
            "low": low,
        }

    except Exception as e:
        print(f"AI categorization failed: {e}")
        # Fallback: put all in medium priority
        return {
            "urgent": [],
            "medium": [
                {
                    "id": e.message_id,
                    "sender": e.from_email,
                    "sender_name": e.from_name or e.from_email,
                    "subject": e.subject,
                    "summary": e.snippet or "No preview available",
                    "message_link": f"https://mail.google.com/mail/u/0/#inbox/{e.message_id}",
                }
                for e in emails
            ],
            "low": [],
        }


def generate_intelligent_recap_html(
    *,
    slot: str,
    emails: list[RecapEmail],
    account_emails: list[str],
) -> str:
    """Generate beautiful HTML email digest with intelligent prioritization."""

    slot_greetings = {
        "morning": "Good morning",
        "noon": "Good afternoon",
        "evening": "Good evening",
        "night": "Good evening",
    }
    greeting = slot_greetings.get(slot, "Hello")

    if not emails:
        # Simple HTML for no emails
        return generate_email_digest_html(
            greeting=greeting,
            urgent_emails=[],
            medium_emails=[],
            low_emails=[],
            stats={
                "total": 0,
                "important": 0,
                "archived": 0,
                "tip": "No new emails since last check. You're all caught up! 🎉"
            },
            base_url=app_settings.backend_url or "https://personalaiagent-production.up.railway.app",
        )

    # Use AI to categorize emails
    categorized = categorize_emails_with_ai(emails)

    # Calculate stats
    total_emails = len(emails)
    important_count = len(categorized["urgent"]) + len(categorized["medium"])
    archived_count = total_emails - important_count

    stats = {
        "total": total_emails,
        "important": important_count,
        "archived": archived_count,
    }

    # Generate HTML
    return generate_email_digest_html(
        greeting=greeting,
        urgent_emails=categorized["urgent"],
        medium_emails=categorized["medium"],
        low_emails=categorized["low"],
        stats=stats,
        base_url=app_settings.backend_url or "https://personalaiagent-production.up.railway.app",
    )
