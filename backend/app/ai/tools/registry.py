"""
Tool registry initialization.

This module sets up the global tool registry with all available tools.
Import get_tool_registry() to access the configured registry.
"""

from app.ai.tools.base import ToolRegistry
from app.ai.tools.tavily import WebSearchTool
from app.ai.tools.tavily_extract import ExtractUrlTool
from app.ai.tools.answer import AnswerTool
from app.ai.tools.calendar_tool import (
    AddCalendarEventTool,
    ListCalendarEventsTool,
    DeleteCalendarEventTool,
    UpdateCalendarEventTool,
    CheckAvailabilityTool,
    GetTodayScheduleTool,
    FindFreeSlotsTool,
)
from app.ai.tools.gmail_tool import (
    ListEmailsTool,
    ReadEmailTool,
    ReadEmailThreadTool,
    GetEmailConversationTool,
    SendEmailTool,
    MarkEmailAsReadTool,
)
from app.ai.tools.drive_tool import (
    ListDriveFilesTool,
    ReadDriveFileTool,
    SearchDriveFilesTool,
    CreateGoogleDocTool,
    UpdateGoogleDocTool,
)
from app.ai.tools.sheets_tool import (
    ReadGoogleSheetTool,
    CreateGoogleSheetTool,
    UpdateGoogleSheetTool,
    AppendGoogleSheetTool,
)
from app.ai.tools.maps_tool import (
    GetDistanceTimeTool,
    SearchPlacesTool,
    GeocodeTool,
)
from app.ai.tools.robinhood_tool import get_robinhood_tools
from app.ai.tools.youtube_tool import (
    SearchYouTubeTool,
    GetVideoDetailsTool,
    GetTrendingVideosTool,
    GetMyWatchHistoryTool,
    GetMySubscriptionsTool,
    GetMyPlaylistsTool,
)


_initialized_registry: ToolRegistry | None = None


def get_tool_registry(context_query: str | None = None) -> ToolRegistry:
    """
    Get the configured tool registry with all tools registered.

    Args:
        context_query: Optional query context for tools that need it (like ExtractUrlTool)

    Returns:
        ToolRegistry instance with all tools registered
    """
    # Always create a fresh registry to support context_query
    registry = ToolRegistry()

    # Register all available tools
    registry.register(WebSearchTool())
    registry.register(ExtractUrlTool(context_query=context_query))
    registry.register(AnswerTool())

    # Calendar tools
    registry.register(AddCalendarEventTool())
    registry.register(ListCalendarEventsTool())
    registry.register(DeleteCalendarEventTool())
    registry.register(UpdateCalendarEventTool())
    registry.register(CheckAvailabilityTool())
    registry.register(GetTodayScheduleTool())
    registry.register(FindFreeSlotsTool())

    # Gmail tools
    registry.register(ListEmailsTool())
    registry.register(ReadEmailTool())
    registry.register(ReadEmailThreadTool())
    registry.register(GetEmailConversationTool())
    registry.register(SendEmailTool())
    registry.register(MarkEmailAsReadTool())

    # Google Drive & Docs tools
    registry.register(ListDriveFilesTool())
    registry.register(ReadDriveFileTool())
    registry.register(SearchDriveFilesTool())
    registry.register(CreateGoogleDocTool())
    registry.register(UpdateGoogleDocTool())

    # Google Sheets tools
    registry.register(ReadGoogleSheetTool())
    registry.register(CreateGoogleSheetTool())
    registry.register(UpdateGoogleSheetTool())
    registry.register(AppendGoogleSheetTool())

    # Google Maps tools
    registry.register(GetDistanceTimeTool())
    registry.register(SearchPlacesTool())
    registry.register(GeocodeTool())

    # Robinhood MCP tools (when connected)
    for robinhood_tool in get_robinhood_tools():
        registry.register(robinhood_tool)

    # YouTube tools (public)
    registry.register(SearchYouTubeTool())
    registry.register(GetVideoDetailsTool())
    registry.register(GetTrendingVideosTool())

    # YouTube tools (personal - requires OAuth)
    registry.register(GetMyWatchHistoryTool())
    registry.register(GetMySubscriptionsTool())
    registry.register(GetMyPlaylistsTool())

    return registry


def create_dynamic_system_prompt(context_query: str | None = None) -> str:
    """
    Create a system prompt dynamically from registered tools.

    Args:
        context_query: Optional query context for tools that need it

    Returns:
        Complete system prompt string
    """
    from datetime import datetime

    current_date = datetime.now().strftime("%Y-%m-%d")
    current_day = datetime.now().strftime("%A")

    base_instructions = f"""You are a helpful AI assistant with access to various tools.

Current date and time: {current_date} ({current_day})

Rules:
- Use the appropriate tool based on what the user needs
- For research questions: use search to discover URLs, then scrape them for detailed content

- For Gmail, you have full access to read and send emails:
  - list_emails: List recent emails with filters (unread, search query, max results)
  - read_email: Read full email content by ID
  - read_email_thread: Read an entire thread in order (all messages start to finish)
  - get_email_conversation: Find recent threads with a person and load each full thread — USE THIS before replying
  - send_email: Send emails; for replies pass thread_id + reply_to_email_id from the conversation tools
  - mark_email_read: Mark emails as read or unread
  - When the user asks to reply/respond to someone: first call get_email_conversation(person=...), read the full thread context, draft the reply, then send_email with thread_id and reply_to_email_id from the latest message
  - When searching emails, use Gmail query syntax: "from:user@example.com", "subject:meeting", "is:unread"

- For Google Drive & Docs, you can access and manage files:
  - list_drive_files: List files and folders in Drive
  - search_drive_files: Search for files by name or content
  - read_drive_file: Read content from text files and Google Docs
  - create_google_doc: Create new Google Docs with content
  - update_google_doc: Edit existing Docs (append, prepend, or replace content)
  - Use search_drive_files to find files, then read_drive_file to get content
  - To edit a doc: search/list to get doc_id, then update_google_doc with action (append/prepend/replace_all)

- For Google Sheets, you can read and write spreadsheet data:
  - read_google_sheet: Read data from a sheet (specify spreadsheet_id and range like 'Sheet1!A1:D10')
  - create_google_sheet: Create new spreadsheets
  - update_google_sheet: Update/write data to specific cells (provide values as JSON array)
  - append_google_sheet: Add new rows to the end of a sheet
  - Values format: Use JSON arrays like [["Name", "Age"], ["John", 30]] for multi-row data

- For Google Maps, you can get location and navigation info:
  - get_distance_time: Calculate distance and travel time between two locations (supports driving, walking, bicycling, transit)
  - search_places: Find places, businesses, or points of interest (e.g., "coffee shops near me")
  - geocode_address: Convert addresses to coordinates (latitude/longitude)
  - Perfect for: "How long to get from X to Y?", "Find restaurants nearby", "What are the coordinates of X?"

- For Robinhood Agentic Trading (Stock Research page), connect Robinhood MCP first:
  - Tools are prefixed with robinhood_ (e.g. robinhood_get_portfolio, robinhood_get_equity_quotes)
  - Read tools can access portfolio, positions, balances, and quotes across accounts
  - Trade tools only execute in the dedicated Robinhood Agentic account
  - Use review tools before placing orders when available

- For YouTube, you can search videos AND access personal data:
  Public data:
  - search_youtube: Search for videos by keyword or topic
  - get_youtube_video_details: Get detailed info about a video (views, likes, description) by URL or ID
  - get_trending_youtube_videos: See what's trending on YouTube

  Personal data (requires OAuth):
  - get_my_youtube_history: Get user's recently watched/liked videos
  - get_my_youtube_subscriptions: List channels the user is subscribed to
  - get_my_youtube_playlists: Get user's playlists (Watch Later, etc.)
  - Perfect for: "Show my YouTube subscriptions", "What's in my Watch Later playlist?", "What videos did I like?"

- For calendar management, you have full access to the user's Google Calendar:

  Basic CRUD:
  - add_calendar_event: Create new events with location, attendees, timezone, reminders
  - list_calendar_events: View upcoming events (default 7 days ahead)
  - update_calendar_event: Modify existing events (time, title, description, location, attendees)
  - delete_calendar_event: Cancel/remove events

  Smart Features:
  - check_availability: Check if user is free at a specific time (prevents double-booking)
  - get_today_schedule: Get today's calendar overview (morning briefing)
  - find_free_slots: Find available time slots for scheduling (smart scheduling)

  Recurring Events (add_calendar_event):
  - Use recurrence parameter: "daily", "weekly", "weekdays" (Mon-Fri), "monthly"
  - Set recurrence_count for number of occurrences (default: 10)
  - Example: "Daily standup at 9am Monday-Friday" → recurrence: "weekdays"

  Reminders (add_calendar_event):
  - Use reminder_minutes parameter (e.g., 15 for 15-minute reminder)

  Date/Time Rules:
  - IMPORTANT: When calculating dates, use the current date above. "Tomorrow" means {current_date} + 1 day
  - Use ISO format: YYYY-MM-DDTHH:MM:SS (e.g., "2026-07-06T15:00:00" for July 6th at 3pm)
  - To modify/delete events, first use list_calendar_events to get the event_id
  - When adding attendees, use comma-separated emails: "john@example.com,sarah@example.com"
  - Before scheduling, you can use check_availability to prevent conflicts

- Think step by step and use multiple tools if needed
- Only answer when you have enough information or have completed the requested action
- Base your answers on search results and tool outputs — do not invent facts
- If past research memory is provided, use it as context but search for current information when needed
- Return only the JSON object, no markdown fences or extra commentary"""

    registry = get_tool_registry(context_query=context_query)
    return registry.generate_system_prompt(base_instructions)
