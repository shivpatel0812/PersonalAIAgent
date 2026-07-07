"""Calendar tool - allows the agent to add events to Google Calendar."""

from datetime import datetime, timedelta
from typing import Any
from pydantic import BaseModel
import pytz

from app.ai.tools.base import Tool, ToolParameter
from app.google.oauth import load_credentials
from googleapiclient.discovery import build

# Default timezone - can be made configurable per user in the future
DEFAULT_TIMEZONE = "America/Los_Angeles"


class CalendarEventResult(BaseModel):
    """Result of adding a calendar event."""
    success: bool
    event_id: str | None = None
    event_link: str | None = None
    summary: str
    start_time: str
    message: str


class AddCalendarEventTool(Tool):
    """Tool for adding events to Google Calendar."""

    @property
    def name(self) -> str:
        return "add_calendar_event"

    @property
    def description(self) -> str:
        return "add an event to the user's Google Calendar with a title, date, time, and optional duration"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "summary",
                "type": "string",
                "description": "event title/summary (e.g., 'Meeting with Sarah', 'Dentist appointment')",
                "required": True,
            },
            {
                "name": "start_datetime",
                "type": "string",
                "description": "start date and time in ISO format (e.g., '2026-07-10T14:00:00')",
                "required": True,
            },
            {
                "name": "duration_minutes",
                "type": "integer",
                "description": "event duration in minutes (default: 60)",
                "required": False,
            },
            {
                "name": "description",
                "type": "string",
                "description": "optional event description or notes",
                "required": False,
            },
            {
                "name": "location",
                "type": "string",
                "description": "event location (e.g., 'Conference Room A', '123 Main St', 'Zoom')",
                "required": False,
            },
            {
                "name": "attendees",
                "type": "string",
                "description": "comma-separated list of attendee email addresses (e.g., 'john@example.com,sarah@example.com')",
                "required": False,
            },
            {
                "name": "timezone",
                "type": "string",
                "description": "timezone for the event (e.g., 'America/Los_Angeles', 'America/New_York'). Default: America/Los_Angeles",
                "required": False,
            },
            {
                "name": "recurrence",
                "type": "string",
                "description": "recurrence pattern: 'daily', 'weekly', 'weekdays' (Mon-Fri), 'monthly', or custom RRULE (optional)",
                "required": False,
            },
            {
                "name": "recurrence_count",
                "type": "integer",
                "description": "number of times to repeat (optional, default: 10 for recurring events)",
                "required": False,
            },
            {
                "name": "reminder_minutes",
                "type": "integer",
                "description": "reminder before event in minutes (e.g., 15 for 15 min reminder, optional)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> CalendarEventResult:
        """
        Add an event to Google Calendar.

        Args:
            summary: Event title
            start_datetime: Start time in ISO format
            duration_minutes: Event duration (default 60 minutes)
            description: Optional event description
            location: Optional event location
            attendees: Optional comma-separated list of attendee emails
            timezone: Optional timezone (default: America/Los_Angeles)

        Returns:
            CalendarEventResult with event details
        """
        summary = kwargs.get("summary", "").strip()
        start_datetime_str = kwargs.get("start_datetime", "").strip()
        duration_minutes = kwargs.get("duration_minutes", 60)
        description = kwargs.get("description", "")
        location = kwargs.get("location", "").strip()
        attendees_str = kwargs.get("attendees", "").strip()
        timezone = kwargs.get("timezone", DEFAULT_TIMEZONE).strip()
        recurrence_pattern = kwargs.get("recurrence", "").strip().lower()
        recurrence_count = kwargs.get("recurrence_count", 10)
        reminder_minutes = kwargs.get("reminder_minutes")

        if not summary:
            raise ValueError("Event summary is required")

        if not start_datetime_str:
            raise ValueError("Start datetime is required")

        # Load Google Calendar credentials
        credentials = load_credentials()
        if not credentials:
            return CalendarEventResult(
                success=False,
                summary=summary,
                start_time=start_datetime_str,
                message="Google Calendar is not connected. Please connect your calendar first."
            )

        try:
            # Parse start datetime
            start_dt = datetime.fromisoformat(start_datetime_str.replace('Z', '+00:00'))
            end_dt = start_dt + timedelta(minutes=int(duration_minutes))

            # Build Calendar API service
            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

            # Create event
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': timezone,
                },
            }

            # Add location if provided
            if location:
                event['location'] = location

            # Add attendees if provided
            if attendees_str:
                attendee_emails = [email.strip() for email in attendees_str.split(',') if email.strip()]
                event['attendees'] = [{'email': email} for email in attendee_emails]
                # Send notifications to attendees
                event['sendNotifications'] = True

            # Add recurrence if provided
            if recurrence_pattern:
                rrule = None
                if recurrence_pattern == "daily":
                    rrule = f"RRULE:FREQ=DAILY;COUNT={recurrence_count}"
                elif recurrence_pattern == "weekly":
                    rrule = f"RRULE:FREQ=WEEKLY;COUNT={recurrence_count}"
                elif recurrence_pattern == "weekdays":
                    rrule = f"RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;COUNT={recurrence_count}"
                elif recurrence_pattern == "monthly":
                    rrule = f"RRULE:FREQ=MONTHLY;COUNT={recurrence_count}"
                elif recurrence_pattern.startswith("RRULE:"):
                    rrule = recurrence_pattern
                else:
                    # Try to parse as custom pattern
                    rrule = recurrence_pattern

                if rrule:
                    event['recurrence'] = [rrule]

            # Add reminders if provided
            if reminder_minutes is not None:
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': int(reminder_minutes)},
                    ],
                }

            # Insert event
            created_event = service.events().insert(
                calendarId='primary',
                body=event,
                sendNotifications=bool(attendees_str)
            ).execute()

            # Build success message
            msg_parts = [f"✅ Added '{summary}' to your calendar for {start_dt.strftime('%A, %B %d at %I:%M %p')}"]
            if recurrence_pattern:
                msg_parts.append(f"Recurrence: {recurrence_pattern} ({recurrence_count} occurrences)")
            if location:
                msg_parts.append(f"Location: {location}")
            if attendees_str:
                msg_parts.append(f"Invites sent to: {attendees_str}")
            if reminder_minutes is not None:
                msg_parts.append(f"Reminder: {reminder_minutes} minutes before")

            return CalendarEventResult(
                success=True,
                event_id=created_event.get('id'),
                event_link=created_event.get('htmlLink'),
                summary=summary,
                start_time=start_dt.strftime('%Y-%m-%d %I:%M %p'),
                message="\n".join(msg_parts)
            )

        except ValueError as e:
            return CalendarEventResult(
                success=False,
                summary=summary,
                start_time=start_datetime_str,
                message=f"Error parsing datetime: {str(e)}. Please use ISO format like '2026-07-10T14:00:00'"
            )
        except Exception as e:
            return CalendarEventResult(
                success=False,
                summary=summary,
                start_time=start_datetime_str,
                message=f"Failed to add event: {str(e)}"
            )


class CalendarEvent(BaseModel):
    """Represents a calendar event."""
    id: str
    summary: str
    start_time: str
    end_time: str
    description: str | None = None
    location: str | None = None
    html_link: str | None = None


class ListEventsResult(BaseModel):
    """Result of listing calendar events."""
    success: bool
    events: list[CalendarEvent] = []
    count: int
    message: str


class ListCalendarEventsTool(Tool):
    """Tool for listing upcoming calendar events."""

    @property
    def name(self) -> str:
        return "list_calendar_events"

    @property
    def description(self) -> str:
        return "list upcoming events from the user's Google Calendar with optional time range and max results"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of events to return (default: 10)",
                "required": False,
            },
            {
                "name": "days_ahead",
                "type": "integer",
                "description": "number of days ahead to look (default: 7)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ListEventsResult:
        """
        List upcoming calendar events.

        Args:
            max_results: Maximum number of events to return (default 10)
            days_ahead: Number of days ahead to look (default 7)

        Returns:
            ListEventsResult with list of events
        """
        max_results = kwargs.get("max_results", 10)
        days_ahead = kwargs.get("days_ahead", 7)

        credentials = load_credentials()
        if not credentials:
            return ListEventsResult(
                success=False,
                count=0,
                message="Google Calendar is not connected. Please connect your calendar first."
            )

        try:
            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

            # Get events from now to days_ahead in the future
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'

            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events_list = events_result.get('items', [])

            calendar_events = []
            for event in events_list:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                calendar_events.append(CalendarEvent(
                    id=event['id'],
                    summary=event.get('summary', 'No title'),
                    start_time=start,
                    end_time=end,
                    description=event.get('description'),
                    location=event.get('location'),
                    html_link=event.get('htmlLink')
                ))

            return ListEventsResult(
                success=True,
                events=calendar_events,
                count=len(calendar_events),
                message=f"Found {len(calendar_events)} upcoming event(s) in the next {days_ahead} days"
            )

        except Exception as e:
            return ListEventsResult(
                success=False,
                count=0,
                message=f"Failed to list events: {str(e)}"
            )


class DeleteEventResult(BaseModel):
    """Result of deleting a calendar event."""
    success: bool
    event_id: str | None = None
    message: str


class DeleteCalendarEventTool(Tool):
    """Tool for deleting/canceling calendar events."""

    @property
    def name(self) -> str:
        return "delete_calendar_event"

    @property
    def description(self) -> str:
        return "delete or cancel an event from the user's Google Calendar by event ID"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "event_id",
                "type": "string",
                "description": "the ID of the event to delete (get this from list_calendar_events)",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> DeleteEventResult:
        """
        Delete a calendar event.

        Args:
            event_id: The ID of the event to delete

        Returns:
            DeleteEventResult with success status
        """
        event_id = kwargs.get("event_id", "").strip()

        if not event_id:
            raise ValueError("Event ID is required")

        credentials = load_credentials()
        if not credentials:
            return DeleteEventResult(
                success=False,
                message="Google Calendar is not connected. Please connect your calendar first."
            )

        try:
            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

            # Delete the event
            service.events().delete(calendarId='primary', eventId=event_id).execute()

            return DeleteEventResult(
                success=True,
                event_id=event_id,
                message=f"✅ Event deleted successfully"
            )

        except Exception as e:
            return DeleteEventResult(
                success=False,
                event_id=event_id,
                message=f"Failed to delete event: {str(e)}"
            )


class UpdateEventResult(BaseModel):
    """Result of updating a calendar event."""
    success: bool
    event_id: str | None = None
    event_link: str | None = None
    message: str


class UpdateCalendarEventTool(Tool):
    """Tool for updating/editing calendar events."""

    @property
    def name(self) -> str:
        return "update_calendar_event"

    @property
    def description(self) -> str:
        return "update or modify an existing event in the user's Google Calendar (change time, title, description, etc.)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "event_id",
                "type": "string",
                "description": "the ID of the event to update (get this from list_calendar_events)",
                "required": True,
            },
            {
                "name": "summary",
                "type": "string",
                "description": "new event title/summary (optional - only if changing title)",
                "required": False,
            },
            {
                "name": "start_datetime",
                "type": "string",
                "description": "new start date and time in ISO format (optional - only if changing time)",
                "required": False,
            },
            {
                "name": "duration_minutes",
                "type": "integer",
                "description": "new event duration in minutes (optional - only if changing duration)",
                "required": False,
            },
            {
                "name": "description",
                "type": "string",
                "description": "new event description (optional - only if changing description)",
                "required": False,
            },
            {
                "name": "location",
                "type": "string",
                "description": "new event location (optional - only if changing location)",
                "required": False,
            },
            {
                "name": "attendees",
                "type": "string",
                "description": "comma-separated list of attendee emails (optional - only if changing attendees)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> UpdateEventResult:
        """
        Update a calendar event.

        Args:
            event_id: The ID of the event to update
            summary: New event title (optional)
            start_datetime: New start time in ISO format (optional)
            duration_minutes: New duration in minutes (optional)
            description: New description (optional)

        Returns:
            UpdateEventResult with success status
        """
        event_id = kwargs.get("event_id", "").strip()

        if not event_id:
            raise ValueError("Event ID is required")

        credentials = load_credentials()
        if not credentials:
            return UpdateEventResult(
                success=False,
                message="Google Calendar is not connected. Please connect your calendar first."
            )

        try:
            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

            # First, get the existing event
            event = service.events().get(calendarId='primary', eventId=event_id).execute()

            # Update only the fields that were provided
            if "summary" in kwargs and kwargs["summary"]:
                event['summary'] = kwargs["summary"].strip()

            if "description" in kwargs and kwargs["description"] is not None:
                event['description'] = kwargs["description"]

            if "location" in kwargs and kwargs["location"] is not None:
                event['location'] = kwargs["location"].strip()

            if "attendees" in kwargs and kwargs["attendees"]:
                attendees_str = kwargs["attendees"].strip()
                attendee_emails = [email.strip() for email in attendees_str.split(',') if email.strip()]
                event['attendees'] = [{'email': email} for email in attendee_emails]

            if "start_datetime" in kwargs and kwargs["start_datetime"]:
                start_dt = datetime.fromisoformat(kwargs["start_datetime"].replace('Z', '+00:00'))

                # Calculate end time
                if "duration_minutes" in kwargs and kwargs["duration_minutes"]:
                    end_dt = start_dt + timedelta(minutes=int(kwargs["duration_minutes"]))
                else:
                    # Keep the same duration as before
                    old_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    old_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    duration = old_end - old_start
                    end_dt = start_dt + duration

                # Use existing timezone or default
                existing_tz = event['start'].get('timeZone', DEFAULT_TIMEZONE)
                event['start'] = {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': existing_tz,
                }
                event['end'] = {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': existing_tz,
                }

            # Update the event
            send_updates = bool(kwargs.get("attendees"))
            updated_event = service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event,
                sendNotifications=send_updates
            ).execute()

            return UpdateEventResult(
                success=True,
                event_id=updated_event.get('id'),
                event_link=updated_event.get('htmlLink'),
                message=f"✅ Event updated successfully"
            )

        except ValueError as e:
            return UpdateEventResult(
                success=False,
                event_id=event_id,
                message=f"Error parsing datetime: {str(e)}. Please use ISO format like '2026-07-10T14:00:00'"
            )
        except Exception as e:
            return UpdateEventResult(
                success=False,
                event_id=event_id,
                message=f"Failed to update event: {str(e)}"
            )


class AvailabilityResult(BaseModel):
    """Result of checking calendar availability."""
    success: bool
    is_available: bool
    time_slot: str
    conflicting_events: list[CalendarEvent] = []
    message: str


class CheckAvailabilityTool(Tool):
    """Tool for checking if a time slot is available (free/busy check)."""

    @property
    def name(self) -> str:
        return "check_availability"

    @property
    def description(self) -> str:
        return "check if the user is available (free) at a specific date and time, or if there are conflicting events"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "start_datetime",
                "type": "string",
                "description": "start date and time to check in ISO format (e.g., '2026-07-10T14:00:00')",
                "required": True,
            },
            {
                "name": "duration_minutes",
                "type": "integer",
                "description": "duration to check in minutes (default: 60)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> AvailabilityResult:
        """
        Check if a time slot is available.

        Args:
            start_datetime: Start time to check in ISO format
            duration_minutes: Duration to check (default 60 minutes)

        Returns:
            AvailabilityResult indicating if time is free and any conflicts
        """
        start_datetime_str = kwargs.get("start_datetime", "").strip()
        duration_minutes = kwargs.get("duration_minutes", 60)

        if not start_datetime_str:
            raise ValueError("Start datetime is required")

        credentials = load_credentials()
        if not credentials:
            return AvailabilityResult(
                success=False,
                is_available=False,
                time_slot=start_datetime_str,
                message="Google Calendar is not connected. Please connect your calendar first."
            )

        try:
            from app.google.calendar_service import check_slot as calendar_check_slot

            line = calendar_check_slot(
                credentials,
                start_datetime_str,
                duration_minutes=int(duration_minutes),
                timezone=DEFAULT_TIMEZONE,
            )
            start_dt = datetime.fromisoformat(start_datetime_str.replace("Z", "+00:00"))
            time_slot_str = f"{start_dt.strftime('%A, %B %d at %I:%M %p')} ({duration_minutes} min)"
            is_available = "FREE" in line

            if is_available:
                message = f"✅ You are free at {time_slot_str}"
            else:
                conflict = line.split("CONFLICT —", 1)[-1].strip() if "CONFLICT" in line else "busy"
                message = f"❌ You have a conflict at {time_slot_str}: {conflict}"

            return AvailabilityResult(
                success=True,
                is_available=is_available,
                time_slot=time_slot_str,
                conflicting_events=[],
                message=message,
            )

        except ValueError as e:
            return AvailabilityResult(
                success=False,
                is_available=False,
                time_slot=start_datetime_str,
                message=f"Error parsing datetime: {str(e)}. Please use ISO format like '2026-07-10T14:00:00'"
            )
        except Exception as e:
            return AvailabilityResult(
                success=False,
                is_available=False,
                time_slot=start_datetime_str,
                message=f"Failed to check availability: {str(e)}"
            )


class TodayScheduleResult(BaseModel):
    """Result of getting today's schedule."""
    success: bool
    date: str
    events: list[CalendarEvent] = []
    count: int
    message: str


class GetTodayScheduleTool(Tool):
    """Tool for getting today's calendar schedule (proactive assistant feature)."""

    @property
    def name(self) -> str:
        return "get_today_schedule"

    @property
    def description(self) -> str:
        return "get a summary of all events scheduled for today (morning briefing, daily overview)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    def execute(self, **kwargs) -> TodayScheduleResult:
        """
        Get today's calendar schedule.

        Returns:
            TodayScheduleResult with list of today's events
        """
        credentials = load_credentials()
        if not credentials:
            return TodayScheduleResult(
                success=False,
                date="",
                count=0,
                message="Google Calendar is not connected. Please connect your calendar first."
            )

        try:
            service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

            # Get today's date range
            tz = pytz.timezone(DEFAULT_TIMEZONE)
            now = datetime.now(tz)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events_list = events_result.get('items', [])

            calendar_events = []
            for event in events_list:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                calendar_events.append(CalendarEvent(
                    id=event['id'],
                    summary=event.get('summary', 'No title'),
                    start_time=start,
                    end_time=end,
                    description=event.get('description'),
                    location=event.get('location'),
                    html_link=event.get('htmlLink')
                ))

            date_str = now.strftime('%A, %B %d, %Y')

            if len(calendar_events) == 0:
                message = f"📅 You have no events scheduled for today ({date_str}). Your day is free!"
            else:
                message = f"📅 Today's schedule for {date_str}:\n"
                for idx, evt in enumerate(calendar_events, 1):
                    start_dt = datetime.fromisoformat(evt.start_time.replace('Z', '+00:00'))
                    time_str = start_dt.strftime('%I:%M %p')
                    location_str = f" at {evt.location}" if evt.location else ""
                    message += f"\n{idx}. {time_str} - {evt.summary}{location_str}"

            return TodayScheduleResult(
                success=True,
                date=date_str,
                events=calendar_events,
                count=len(calendar_events),
                message=message
            )

        except Exception as e:
            return TodayScheduleResult(
                success=False,
                date="",
                count=0,
                message=f"Failed to get today's schedule: {str(e)}"
            )


class FreeSlot(BaseModel):
    """Represents a free time slot."""
    start_time: str
    end_time: str
    duration_minutes: int


class FindFreeSlotsResult(BaseModel):
    """Result of finding free time slots."""
    success: bool
    date_range: str
    free_slots: list[FreeSlot] = []
    message: str


class FindFreeSlotsTool(Tool):
    """Tool for finding free time slots (smart scheduling feature)."""

    @property
    def name(self) -> str:
        return "find_free_slots"

    @property
    def description(self) -> str:
        return "find available free time slots in the user's calendar for scheduling meetings"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "days_ahead",
                "type": "integer",
                "description": "number of days ahead to search (default: 7)",
                "required": False,
            },
            {
                "name": "min_duration_minutes",
                "type": "integer",
                "description": "minimum duration of free slots to find in minutes (default: 60)",
                "required": False,
            },
            {
                "name": "working_hours_only",
                "type": "boolean",
                "description": "only show slots during working hours 9am-5pm (default: true)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> FindFreeSlotsResult:
        """
        Find free time slots in the calendar.

        Args:
            days_ahead: Days to search ahead (default 7)
            min_duration_minutes: Minimum slot duration (default 60)
            working_hours_only: Only show 9am-5pm slots (default true)

        Returns:
            FindFreeSlotsResult with available time slots
        """
        days_ahead = kwargs.get("days_ahead", 7)
        min_duration = kwargs.get("min_duration_minutes", 60)
        working_hours_only = kwargs.get("working_hours_only", True)

        credentials = load_credentials()
        if not credentials:
            return FindFreeSlotsResult(
                success=False,
                date_range="",
                message="Google Calendar is not connected. Please connect your calendar first."
            )

        try:
            from app.google.calendar_service import find_free_slots_text

            free_text = find_free_slots_text(
                credentials,
                days=int(days_ahead),
                duration_minutes=int(min_duration),
                timezone=DEFAULT_TIMEZONE,
                working_hours_only=working_hours_only,
            )

            tz = pytz.timezone(DEFAULT_TIMEZONE)
            now = datetime.now(tz)
            end_time = now + timedelta(days=days_ahead)
            date_range_str = f"{now.strftime('%B %d')} - {end_time.strftime('%B %d, %Y')}"

            if free_text.startswith("No free"):
                return FindFreeSlotsResult(
                    success=True,
                    date_range=date_range_str,
                    free_slots=[],
                    message=free_text,
                )

            return FindFreeSlotsResult(
                success=True,
                date_range=date_range_str,
                free_slots=[],
                message=f"Found free time slots:\n{free_text}",
            )

        except Exception as e:
            return FindFreeSlotsResult(
                success=False,
                date_range="",
                message=f"Failed to find free slots: {str(e)}"
            )
