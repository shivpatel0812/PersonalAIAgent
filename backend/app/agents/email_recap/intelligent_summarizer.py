"""Intelligent email summarization with prioritization and HTML generation."""

import json
import re
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


async def get_full_sender_context(sender: str, user_id: str = "default") -> dict | None:
    """Get full sender intelligence context including ratings, priority, urgency flags."""
    try:
        from app.supabase_client import get_supabase_client

        supabase = get_supabase_client()
        result = supabase.table("sender_priorities")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("sender", sender)\
            .execute()

        if result.data:
            row = result.data[0]
            return {
                "priority_score": float(row.get("priority_score", 0)),
                "avg_star_rating": float(row["avg_star_rating"]) if row.get("avg_star_rating") else None,
                "total_ratings": int(row.get("total_ratings", 0)),
                "always_urgent": bool(row.get("always_urgent", False)),
                "reply_rate": float(row["reply_rate"]) if row.get("reply_rate") else None,
            }
    except Exception:
        pass

    return None


def deduplicate_by_thread(emails: list[RecapEmail]) -> list[RecapEmail]:
    """
    Group emails by thread_id, keep only latest per thread.
    Reduces duplicate emails from same conversation.
    """
    threads: dict[str, RecapEmail] = {}
    for email in emails:
        thread_id = email.thread_id
        # Keep the email if it's the first in thread or newer than existing
        if thread_id not in threads:
            threads[thread_id] = email
        # Gmail message IDs are chronological, so compare them
        elif email.message_id > threads[thread_id].message_id:
            threads[thread_id] = email

    return list(threads.values())


def extract_deadline_from_text(text: str) -> str | None:
    """
    Extract deadline/date mentions from email text.
    Returns normalized deadline string if found, None otherwise.
    """
    if not text:
        return None

    # Common deadline patterns
    patterns = [
        r"(?:by|before|due|deadline|until)\s+(?:EOD\s+)?(\w+day|\w+\s+\d{1,2})",
        r"(?:by|before|due)\s+(\d{1,2}/\d{1,2})",
        r"(?:by|before|due)\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?)",
        r"ASAP",
        r"urgent",
        r"today|tomorrow",
    ]

    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            if pattern == r"ASAP":
                return "ASAP"
            elif pattern == r"urgent":
                return "urgent"
            elif pattern == r"today|tomorrow":
                return match.group(0).capitalize()
            else:
                return match.group(1) if match.lastindex else match.group(0)

    return None


async def categorize_emails_with_ai(emails: list[RecapEmail], user_id: str = "default") -> dict[str, list[dict]]:
    """
    Use AI to categorize emails into urgent, medium, low priority
    and generate detailed, actionable summaries.

    Improvements:
    - Thread deduplication
    - Sender intelligence integration
    - Context signals (deadlines, attachments, reply detection)
    - Enhanced prompt for specific, actionable summaries
    """
    if not emails:
        return {"urgent": [], "medium": [], "low": []}

    # PRIORITY 3: Thread deduplication - keep only latest email per thread
    emails = deduplicate_by_thread(emails)

    # Format emails for AI with full context
    email_data = []
    for e in emails:
        # PRIORITY 2: Get sender intelligence
        sender_context = await get_full_sender_context(e.from_email, user_id)

        # PRIORITY 4: Extract context signals
        detected_deadline = extract_deadline_from_text(e.snippet)
        is_reply = "re:" in e.subject.lower() or "fwd:" in e.subject.lower()

        email_data.append({
            "id": e.message_id,
            "from": e.from_email,
            "from_name": e.from_name,
            "subject": e.subject,
            "snippet": e.snippet,
            "unread": e.is_unread,
            "important": e.is_important,
            "has_attachments": e.has_attachments,
            "is_reply": is_reply,
            "detected_deadline": detected_deadline,
            # Sender intelligence context
            "sender_priority_score": sender_context["priority_score"] if sender_context else 0,
            "sender_avg_rating": sender_context["avg_star_rating"] if sender_context else None,
            "sender_always_urgent": sender_context["always_urgent"] if sender_context else False,
            "sender_reply_rate": sender_context["reply_rate"] if sender_context else None,
        })

    # PRIORITY 1: Enhanced AI prompt for detailed, actionable summaries
    system_prompt = """You are an intelligent email prioritization assistant that creates SPECIFIC, ACTIONABLE summaries.

Analyze the provided emails and categorize each into:
- urgent: Needs immediate attention, reply expected today, time-sensitive
- medium: Should read when you have time, not urgent (displayed as "REVIEW LATER")
- low: FYI only, no action needed (displayed as "FYI")

CRITICAL: For each email summary, include these 5 elements:

1. WHO: Clean sender name (person/company)

2. WHAT: Specific topic/request (not vague!)
   - Bad: "regarding documents"
   - Good: "sent contract for West Village project signature"
   - Bad: "Freedom of Information Act documents"
   - Good: "sent 23-page FOIA response on police records"

3. WHY IT MATTERS: Why user should care
   - "needs your signature by Friday"
   - "answers your July 3 request"
   - "time-sensitive client deadline"
   - "just FYI, no action needed"

4. ACTION NEEDED: Be explicit about what to do
   - "Reply expected"
   - "Review and approve"
   - "Sign and return"
   - "Just read when you can"
   - "No action needed"

5. DEADLINE/URGENCY: If time-sensitive (otherwise omit)
   - "by EOD Friday"
   - "before meeting tomorrow"
   - "ASAP"

Summary format: [WHO] [WHAT] — [WHY]. **Action: [ACTION].** [DEADLINE if applicable]

Example GOOD summaries:
- "Todd Richardson sent 23-page FOIA response on West Village police records you requested July 3 — requires review and filing by Friday. **Action: Review documents and reply to confirm receipt.** Deadline: EOD Friday"
- "Liam updated you on balance review for Flats at West Village project — escalating to colleague, will follow up next week. **Action: Just FYI, no response needed.**"
- "Bank sent monthly statement for July — shows $2,450 balance, no issues detected. **Action: Review when convenient.**"

Example BAD summaries (don't do this):
- "The email contains documents" (too vague!)
- "Urgent request" (doesn't say what!)
- "Needs attention" (doesn't say why!)
- "Email from Todd" (not specific!)

PRIORITIZATION RULES - Consider ALL context signals:

Sender Intelligence:
- If sender_always_urgent=true → default to URGENT unless clearly FYI
- If sender_avg_rating ≥ 4 stars → likely important to user
- If sender_priority_score ≥ 0.4 → high priority sender
- If sender_reply_rate ≥ 80% → user usually responds (probably important)

Context Signals:
- has_attachments=true + is_reply=true → often needs action (review, sign)
- detected_deadline present → increases urgency
- is_reply=true → likely expects response
- important=true (Gmail star) → user flagged as important

Examples:
- Email from 5-star sender with always_urgent=true → URGENT
- Email from sender with 10% reply rate → likely FYI or low
- Reply with attachment + deadline → URGENT
- Not a reply + no attachment + low priority sender → FYI

Return ONLY valid JSON in this exact format:
{
  "categorized": [
    {
      "id": "email_id",
      "category": "urgent" | "medium" | "low",
      "summary": "Detailed, specific summary following format above",
      "sender_name": "Clean Name",
      "action_needed": "Brief action description (e.g., 'Reply by Friday', 'Review documents', 'No action needed')"
    }
  ]
}
"""

    user_prompt = f"Emails to categorize:\n{json.dumps(email_data, indent=2)}"

    try:
        response = chat_messages([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], max_tokens=3000)  # Increased for detailed summaries

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
            action_needed = item.get("action_needed", "")

            original_email = email_lookup.get(email_id)
            if not original_email:
                continue

            email_dict = {
                "id": email_id,
                "sender": original_email.from_email,
                "sender_name": sender_name or original_email.from_name or original_email.from_email,
                "subject": original_email.subject,
                "summary": summary,
                "action_needed": action_needed,
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
                    "action_needed": "Review email",
                    "message_link": f"https://mail.google.com/mail/u/0/#inbox/{e.message_id}",
                }
                for e in emails
            ],
            "low": [],
        }


async def generate_intelligent_recap_html(
    *,
    slot: str,
    emails: list[RecapEmail],
    account_emails: list[str],
    user_id: str = "default",
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

    # Use AI to categorize emails with all improvements
    categorized = await categorize_emails_with_ai(emails, user_id)

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
