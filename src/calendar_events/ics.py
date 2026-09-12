"""Turn Event objects into .ics calendar files."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from ics import Calendar
from ics import Event as IcsEvent
from ics.alarm import DisplayAlarm
from ics.grammar.parse import ContentLine

from .models import Event


def _build_description(event: Event) -> str:
    """Compose the invite description from the main text, details, and URL."""
    parts: list[str] = []
    if event.description:
        parts.append(event.description)
    if event.details:
        parts.append("\n".join(event.details))
    if event.url:
        parts.append(event.url)
    return "\n\n".join(parts)


def build_calendar(
    event: Event,
    *,
    sequence: int = 0,
    method: str = "PUBLISH",
    color: str | None = None,
) -> Calendar:
    """Build a single-event iCalendar object from an Event."""
    cal = Calendar()
    cal.method = method
    ics_event = IcsEvent()
    ics_event.uid = event.uid
    ics_event.name = event.title
    ics_event.begin = event.start
    ics_event.end = event.resolved_end
    if event.location:
        ics_event.location = event.location
    description = _build_description(event)
    if description:
        ics_event.description = description
    for minutes in event.alarms:
        ics_event.alarms.append(DisplayAlarm(trigger=timedelta(minutes=-minutes)))
    # ics 0.7.x has no native SEQUENCE support; inject it as a raw content line.
    ics_event.extra.append(ContentLine(name="SEQUENCE", value=str(sequence)))
    if color:
        # RFC 7986 COLOR (event + calendar) so supporting clients can tint it.
        cal.extra.append(ContentLine(name="COLOR", value=color))
        ics_event.extra.append(ContentLine(name="COLOR", value=color))
    ics_event.extra.append(ContentLine(name="CATEGORIES", value="Sports"))
    cal.events.add(ics_event)
    return cal


def write_ics(
    event: Event,
    out_dir: str | Path,
    *,
    sequence: int = 0,
    method: str = "PUBLISH",
    color: str | None = None,
) -> Path:
    """Serialize an event to a .ics file and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{event.uid}.ics"
    calendar = build_calendar(event, sequence=sequence, method=method, color=color)
    path.write_text(calendar.serialize(), encoding="utf-8")
    return path
