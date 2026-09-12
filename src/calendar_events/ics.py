"""Turn Event objects into .ics calendar files."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    organizer: str | None = None,
    attendee: str | None = None,
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
    # DTSTAMP is REQUIRED by RFC 5545 for every VEVENT; ics 0.7.x omits it.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ics_event.extra.append(ContentLine(name="DTSTAMP", value=stamp))
    if method == "REQUEST":
        # A REQUEST is a real invitation: iOS shows Accept/Decline and adds it
        # to the default calendar. Needs ORGANIZER + ATTENDEE.
        ics_event.extra.append(ContentLine(name="STATUS", value="CONFIRMED"))
        if organizer:
            ics_event.extra.append(
                ContentLine(
                    name="ORGANIZER",
                    params={"CN": ["Sports Calendar"]},
                    value=f"mailto:{organizer}",
                )
            )
        if attendee:
            ics_event.extra.append(
                ContentLine(
                    name="ATTENDEE",
                    params={
                        "CN": [attendee],
                        "ROLE": ["REQ-PARTICIPANT"],
                        "PARTSTAT": ["NEEDS-ACTION"],
                        "RSVP": ["TRUE"],
                    },
                    value=f"mailto:{attendee}",
                )
            )
    cal.events.add(ics_event)
    return cal


# Calendar-level property order (RFC 5545 §3.6); METHOD must precede VEVENT.
_CAL_PROP_ORDER = {"VERSION": 0, "PRODID": 1, "CALSCALE": 2, "METHOD": 3}


def _fold_line(line: str) -> list[str]:
    """Fold a content line to <=75 octets per RFC 5545 §3.1, UTF-8 aware."""
    if len(line.encode("utf-8")) <= 75:
        return [line]
    segments: list[bytes] = []
    current = b""
    first = True
    for char in line:
        encoded = char.encode("utf-8")
        # Continuation lines carry a leading space, so cap them one octet lower.
        cap = 75 if first else 74
        if len(current) + len(encoded) > cap:
            segments.append(current)
            current = encoded
            first = False
        else:
            current += encoded
    segments.append(current)
    return [
        seg.decode("utf-8") if i == 0 else " " + seg.decode("utf-8")
        for i, seg in enumerate(segments)
    ]


def _reorder_calendar_lines(lines: list[str]) -> list[str]:
    """Hoist calendar-level properties (esp. METHOD) ahead of the VEVENT block."""
    cal_props: list[str] = []
    event_block: list[str] = []
    in_event = False
    for line in lines:
        if line in ("BEGIN:VCALENDAR", "END:VCALENDAR"):
            continue
        if line == "BEGIN:VEVENT":
            in_event = True
        if in_event:
            event_block.append(line)
        else:
            cal_props.append(line)
        if line == "END:VEVENT":
            in_event = False
    cal_props.sort(key=lambda p: _CAL_PROP_ORDER.get(p.split(":", 1)[0].split(";", 1)[0], 9))
    return ["BEGIN:VCALENDAR", *cal_props, *event_block, "END:VCALENDAR"]


def serialize_calendar(calendar: Calendar) -> str:
    """Serialize with METHOD hoisted, long lines folded, and CRLF endings.

    ics 0.7.x emits METHOD after the event and never folds lines, both of which
    trip up strict parsers such as Apple Calendar.
    """
    raw = calendar.serialize().replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln for ln in raw.split("\n") if ln != ""]
    ordered = _reorder_calendar_lines(lines)
    folded: list[str] = []
    for line in ordered:
        folded.extend(_fold_line(line))
    return "\r\n".join(folded) + "\r\n"


def write_ics(
    event: Event,
    out_dir: str | Path,
    *,
    sequence: int = 0,
    method: str = "PUBLISH",
    color: str | None = None,
    organizer: str | None = None,
    attendee: str | None = None,
) -> Path:
    """Serialize an event to a .ics file and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{event.uid}.ics"
    calendar = build_calendar(
        event,
        sequence=sequence,
        method=method,
        color=color,
        organizer=organizer,
        attendee=attendee,
    )
    # newline="" keeps our serializer's CRLF intact (Windows would add \r\r\n).
    path.write_text(serialize_calendar(calendar), encoding="utf-8", newline="")
    return path
