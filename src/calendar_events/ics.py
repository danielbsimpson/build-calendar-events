"""Turn Event objects into .ics calendar files."""

from __future__ import annotations

from pathlib import Path

from ics import Calendar
from ics import Event as IcsEvent

from .models import Event


def build_calendar(event: Event) -> Calendar:
    """Build a single-event iCalendar object from an Event."""
    cal = Calendar()
    ics_event = IcsEvent()
    ics_event.uid = event.uid
    ics_event.name = event.title
    ics_event.begin = event.start
    ics_event.end = event.resolved_end
    if event.location:
        ics_event.location = event.location
    description_parts = [p for p in (event.description, event.url) if p]
    if description_parts:
        ics_event.description = "\n\n".join(description_parts)
    cal.events.add(ics_event)
    return cal


def write_ics(event: Event, out_dir: str | Path) -> Path:
    """Serialize an event to a .ics file and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{event.uid}.ics"
    path.write_text(build_calendar(event).serialize(), encoding="utf-8")
    return path
