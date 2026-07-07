"""
Email Intelligence API endpoints.
Handles ratings, tracking, and learning from user email behavior.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.supabase_client import get_supabase_client

router = APIRouter(prefix="/email-intelligence", tags=["email-intelligence"])


class EmailRatingRequest(BaseModel):
    email_id: str
    gmail_message_id: str | None = None
    sender: str
    subject: str | None = None
    stars: int
    user_id: str = "default"
    category: str | None = None


class EmailEventRequest(BaseModel):
    email_id: str
    gmail_message_id: str | None = None
    sender: str
    subject: str | None = None
    event_type: str
    user_id: str = "default"
    response_time_minutes: int | None = None
    in_digest: bool = False


@router.get("/rate")
async def rate_email(
    id: str = Query(..., description="Email identifier"),
    stars: int = Query(..., ge=1, le=5, description="Star rating 1-5"),
    sender: str = Query(..., description="Email sender"),
    subject: str = Query(default="", description="Email subject"),
    user: str = Query(default="default", description="User ID"),
):
    """
    Rate an email from the digest.
    Called when user clicks a star rating link.
    """
    try:
        supabase = get_supabase_client()

        # Store the rating
        supabase.table("email_ratings").insert({
            "user_id": user,
            "email_id": id,
            "sender": sender,
            "subject": subject,
            "stars": stars,
        }).execute()

        # Return a nice confirmation page
        feedback_messages = {
            1: "Got it! I'll deprioritize emails like this.",
            2: "Noted. I'll show these less prominently.",
            3: "Thanks! I'll keep showing these as normal.",
            4: "Got it! I'll prioritize emails like this.",
            5: "Noted! I'll always highlight emails like this.",
        }

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Rating Saved</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 3rem;
                    border-radius: 1rem;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                    max-width: 500px;
                }}
                h1 {{
                    color: #2d3748;
                    margin-bottom: 1rem;
                    font-size: 2rem;
                }}
                .stars {{
                    font-size: 3rem;
                    margin: 1rem 0;
                    color: #f59e0b;
                }}
                .message {{
                    color: #4a5568;
                    font-size: 1.1rem;
                    line-height: 1.6;
                    margin: 1.5rem 0;
                }}
                .sender {{
                    background: #edf2f7;
                    padding: 0.5rem 1rem;
                    border-radius: 0.5rem;
                    color: #2d3748;
                    font-weight: 500;
                    margin: 1rem 0;
                }}
                .info {{
                    color: #718096;
                    font-size: 0.9rem;
                    margin-top: 2rem;
                    padding-top: 2rem;
                    border-top: 1px solid #e2e8f0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✓ Rating Saved!</h1>
                <div class="stars">{"⭐" * stars}</div>
                <div class="message">{feedback_messages[stars]}</div>
                <div class="sender">From: {sender}</div>
                <div class="info">
                    Your feedback helps me learn what's important to you.
                    <br><br>
                    Changes will appear in tomorrow's digest.
                </div>
            </div>
        </body>
        </html>
        """

        return HTMLResponse(content=html_content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rating: {str(e)}")


@router.post("/event")
async def log_email_event(request: EmailEventRequest):
    """
    Log an email interaction event (opened, replied, archived, etc.)
    """
    try:
        supabase = get_supabase_client()

        supabase.table("email_events").insert({
            "user_id": request.user_id,
            "email_id": request.email_id,
            "gmail_message_id": request.gmail_message_id,
            "sender": request.sender,
            "subject": request.subject,
            "event_type": request.event_type,
            "response_time_minutes": request.response_time_minutes,
            "in_digest": request.in_digest,
        }).execute()

        return {"status": "success", "event": request.event_type}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log event: {str(e)}")


@router.get("/priorities")
async def get_sender_priorities(user_id: str = "default"):
    """
    Get learned sender priorities for a user.
    """
    try:
        supabase = get_supabase_client()

        result = supabase.table("sender_priorities")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("priority_score", desc=True)\
            .execute()

        return {"priorities": result.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get priorities: {str(e)}")


@router.post("/update-priorities")
async def trigger_priority_update():
    """
    Manually trigger sender priority recalculation.
    Normally runs weekly via cron.
    """
    try:
        supabase = get_supabase_client()

        # Call the stored procedure
        supabase.rpc("update_sender_priorities").execute()

        return {"status": "success", "message": "Sender priorities updated"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update priorities: {str(e)}")


@router.get("/stats")
async def get_learning_stats(user_id: str = "default"):
    """
    Get statistics about what the system has learned.
    """
    try:
        supabase = get_supabase_client()

        # Get rating stats
        ratings = supabase.table("email_ratings")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()

        # Get event stats
        events = supabase.table("email_events")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()

        # Get priorities
        priorities = supabase.table("sender_priorities")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("priority_score", desc=True)\
            .limit(10)\
            .execute()

        # Calculate stats
        total_ratings = len(ratings.data)
        avg_stars = sum(r["stars"] for r in ratings.data) / total_ratings if total_ratings > 0 else 0

        event_counts = {}
        for event in events.data:
            event_type = event["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            "total_ratings": total_ratings,
            "average_rating": round(avg_stars, 2),
            "event_counts": event_counts,
            "top_senders": priorities.data[:5],
            "learning_active": total_ratings > 0,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
