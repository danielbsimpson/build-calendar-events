"""Tests for the combined subscription-feed .ics builder."""

from datetime import datetime, timedelta, timezone

from ics import Calendar

from calendar_events.ics import build_feed_calendar, serialize_calendar
from calendar_events.models import Event


def _event(title: str, external_id: str, days_ahead: int = 7) -> Event:
    start = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    return Event(
        source="test",
        title=title,
        start=start,
        end=start + timedelta(hours=2),
        location="Somewhere",
        external_id=external_id,
    )


def test_feed_contains_every_event_once():
    events = [_event("Race One", "e1"), _event("Fight Two", "e2")]
    text = serialize_calendar(build_feed_calendar(events))

    assert text.count("BEGIN:VEVENT") == 2
    for event in events:
        assert event.uid in text
        assert event.title in text

    parsed = Calendar(text)
    assert len(parsed.events) == 2


def test_feed_has_calendar_name_and_no_method():
    text = serialize_calendar(
        build_feed_calendar([_event("Race One", "e1")], calendar_name="Sports")
    )
    assert "X-WR-CALNAME:Sports" in text
    # A subscribed feed is a published collection, not an iTIP message.
    assert "METHOD:" not in text


def test_feed_applies_per_event_sequence():
    e1 = _event("Race One", "e1")
    e2 = _event("Fight Two", "e2")
    text = serialize_calendar(
        build_feed_calendar([e1, e2], sequences={e1.uid: 0, e2.uid: 4})
    )
    assert "SEQUENCE:0" in text
    assert "SEQUENCE:4" in text


def test_feed_serialization_is_crlf_and_folded():
    long_name = "A very long event headline that should exceed limits " * 3
    events = [_event(long_name, "e1"), _event("Short", "e2", days_ahead=10)]
    text = serialize_calendar(build_feed_calendar(events))

    assert "\r\n" in text
    assert "\r\r\n" not in text
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75
    assert "\n" not in text.replace("\r\n", "")
