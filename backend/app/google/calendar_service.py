"""Shared Google Calendar availability helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytz
from googleapiclient.discovery import build

DEFAULT_TIMEZONE = "America/Los_Angeles"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def has_calendar_scope(granted_scopes: list[str]) -> bool:
    if "calendar" in granted_scopes:
        return True
    return CALENDAR_SCOPE in granted_scopes


def check_slot(
    credentials,
    start_datetime: str,
    *,
    duration_minutes: int = 60,
    timezone: str = DEFAULT_TIMEZONE,
) -> str:
    """Return a one-line availability result for a proposed time slot."""
    if not start_datetime.strip():
        return ""

    try:
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        start_dt = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
        if start_dt.tzinfo is None:
            tz = pytz.timezone(timezone)
            start_dt = tz.localize(start_dt)
        end_dt = start_dt + timedelta(minutes=int(duration_minutes))

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events_list = events_result.get("items", [])
        label = start_dt.strftime("%a %b %d at %I:%M %p").lstrip("0")

        if not events_list:
            return f'- Proposed "{label}": FREE'

        conflict = events_list[0].get("summary", "Busy")
        return f'- Proposed "{label}": CONFLICT — {conflict}'
    except Exception as exc:
        return f'- Proposed slot check failed: {exc}'


def find_free_slots_text(
    credentials,
    *,
    days: int = 7,
    duration_minutes: int = 60,
    timezone: str = DEFAULT_TIMEZONE,
    working_hours_only: bool = True,
    max_slots: int = 8,
) -> str:
    """Return formatted free-slot lines for prompt injection."""
    try:
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        start_time = now
        end_time = now + timedelta(days=days)

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        busy_periods = []
        for event in events_result.get("items", []):
            event_start = event["start"].get("dateTime")
            event_end = event["end"].get("dateTime")
            if event_start and event_end:
                busy_periods.append(
                    {
                        "start": datetime.fromisoformat(event_start.replace("Z", "+00:00")),
                        "end": datetime.fromisoformat(event_end.replace("Z", "+00:00")),
                    }
                )

        free_lines: list[str] = []
        min_duration = duration_minutes

        for day in range(days + 1):
            day_start = (start_time + timedelta(days=day)).replace(
                hour=9 if working_hours_only else 0,
                minute=0,
                second=0,
                microsecond=0,
            )
            day_end = day_start.replace(
                hour=17 if working_hours_only else 23,
                minute=0 if working_hours_only else 59,
            )

            if working_hours_only and day_start.weekday() >= 5:
                continue

            slot_start = day_start
            while slot_start < day_end:
                slot_end = slot_start + timedelta(minutes=min_duration)
                if slot_end > day_end:
                    break

                is_free = True
                for busy in busy_periods:
                    if slot_start < busy["end"] and slot_end > busy["start"]:
                        is_free = False
                        slot_start = busy["end"]
                        break

                if is_free:
                    label = slot_start.strftime("%a %b %d %I:%M %p").lstrip("0")
                    end_label = slot_end.strftime("%I:%M %p").lstrip("0")
                    free_lines.append(f"- {label}–{end_label}: free")
                    slot_start = slot_end
                else:
                    continue

                if len(free_lines) >= max_slots:
                    break

            if len(free_lines) >= max_slots:
                break

        if not free_lines:
            return f"No free {duration_minutes}-minute slots found in the next {days} days."

        return "\n".join(free_lines)
    except Exception as exc:
        return f"Could not load calendar availability: {exc}"
