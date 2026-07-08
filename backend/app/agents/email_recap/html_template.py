"""HTML email templates for digest recaps."""

from urllib.parse import quote


def generate_star_rating_links(
    *,
    email_id: str,
    sender: str,
    subject: str,
    base_url: str = "https://personalaiagent-production.up.railway.app",
) -> str:
    """Generate clickable star rating links for an email."""
    stars_html = []

    for rating in range(1, 6):
        # URL encode parameters
        url = (
            f"{base_url}/email-intelligence/rate?"
            f"id={quote(email_id)}&"
            f"stars={rating}&"
            f"sender={quote(sender)}&"
            f"subject={quote(subject or '')}"
        )

        # Show filled stars up to rating, then empty stars
        star_display = "⭐" * rating + "☆" * (5 - rating)

        stars_html.append(
            f'<a href="{url}" style="text-decoration: none; color: #f59e0b; font-size: 18px; margin: 0 2px;">{star_display}</a>'
        )

    return " ".join(stars_html)


def generate_email_digest_html(
    *,
    greeting: str,
    urgent_emails: list[dict],
    medium_emails: list[dict],
    low_emails: list[dict],
    stats: dict,
    base_url: str = "https://personalaiagent-production.up.railway.app",
) -> str:
    """
    Generate beautiful HTML digest email.

    Each email dict should contain:
    - id: unique identifier
    - sender: sender email
    - sender_name: display name
    - subject: email subject
    - summary: 1-2 sentence summary
    - message_link: link to Gmail message
    """

    def render_email_section(title: str, emails: list[dict], color: str, emoji: str) -> str:
        if not emails:
            return ""

        items = []
        for email in emails:
            stars = generate_star_rating_links(
                email_id=email["id"],
                sender=email["sender"],
                subject=email.get("subject", ""),
                base_url=base_url,
            )

            # Build action needed section if available
            action_html = ""
            if email.get("action_needed"):
                action_html = f"""
                    <div style="background: rgba(251, 191, 36, 0.1); border-left: 3px solid #fbbf24; padding: 10px 12px; margin: 12px 0; border-radius: 6px;">
                        <div style="color: #fbbf24; font-weight: 600; font-size: 13px;">
                            📋 {email.get("action_needed")}
                        </div>
                    </div>
                """

            items.append(f"""
                <div style="background: #1e293b; border-left: 4px solid {color}; padding: 20px; margin: 15px 0; border-radius: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: #f1f5f9; font-size: 16px; margin-bottom: 5px;">
                                {email.get("sender_name", email["sender"])}
                            </div>
                            <div style="color: #94a3b8; font-size: 14px;">
                                {email.get("subject", "No subject")}
                            </div>
                        </div>
                    </div>

                    {action_html}

                    <div style="color: #cbd5e1; font-size: 14px; line-height: 1.6; margin: 12px 0;">
                        {email.get("summary", "No summary available")}
                    </div>

                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #334155;">
                        <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">
                            Rate this email's importance:
                        </div>
                        <div style="margin-bottom: 10px;">
                            {stars}
                        </div>
                        <div style="margin-top: 10px;">
                            <a href="{email.get('message_link', '#')}"
                               style="display: inline-block; background: #3b82f6; color: white; padding: 8px 16px; text-decoration: none; border-radius: 6px; font-size: 13px; margin-right: 8px;">
                                View Email
                            </a>
                        </div>
                    </div>
                </div>
            """)

        section_html = f"""
            <div style="margin: 30px 0;">
                <div style="display: flex; align-items: center; margin-bottom: 15px;">
                    <span style="font-size: 24px; margin-right: 8px;">{emoji}</span>
                    <h2 style="color: #f1f5f9; font-size: 20px; margin: 0; font-weight: 600;">
                        {title}
                    </h2>
                </div>
                {"".join(items)}
            </div>
        """

        return section_html

    # Render sections
    urgent_section = render_email_section(
        "URGENT",
        urgent_emails,
        "#ef4444",
        "🔴"
    )

    medium_section = render_email_section(
        "REVIEW LATER",
        medium_emails,
        "#f59e0b",
        "🟡"
    )

    low_section = render_email_section(
        "FYI",
        low_emails,
        "#10b981",
        "🟢"
    )

    # Stats section
    stats_html = f"""
        <div style="background: #1e293b; padding: 20px; border-radius: 8px; margin-top: 30px;">
            <h3 style="color: #f1f5f9; font-size: 16px; margin: 0 0 15px 0;">
                📊 Inbox Stats
            </h3>
            <div style="color: #cbd5e1; font-size: 14px; line-height: 1.8;">
                <div>✉️  Total processed: <strong>{stats.get('total', 0)} emails</strong></div>
                <div>✅ Important: <strong>{stats.get('important', 0)}</strong></div>
                <div>🗑️  Auto-archived: <strong>{stats.get('archived', 0)}</strong></div>
            </div>
        </div>
    """

    # Learning tip (if available)
    learning_tip = ""
    if stats.get("tip"):
        learning_tip = f"""
            <div style="background: #312e81; border-left: 4px solid #6366f1; padding: 15px; margin-top: 20px; border-radius: 8px;">
                <div style="color: #a5b4fc; font-size: 14px;">
                    💡 <strong>Learning:</strong> {stats["tip"]}
                </div>
            </div>
        """

    # Full HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Email Digest</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; background: #0f172a;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <!-- Header -->
            <div style="text-align: center; padding: 30px 0;">
                <h1 style="color: #f1f5f9; font-size: 28px; margin: 0 0 10px 0;">
                    🌅 {greeting}!
                </h1>
                <p style="color: #94a3b8; font-size: 16px; margin: 0;">
                    Here's what needs your attention
                </p>
            </div>

            <!-- Email Sections -->
            {urgent_section}
            {medium_section}
            {low_section}

            <!-- Stats -->
            {stats_html}

            <!-- Learning Tip -->
            {learning_tip}

            <!-- Footer -->
            <div style="text-align: center; padding: 30px 0; color: #64748b; font-size: 13px;">
                <p style="margin: 5px 0;">
                    Your feedback helps me learn what's important to you
                </p>
                <p style="margin: 5px 0;">
                    Changes will appear in tomorrow's digest
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return html
