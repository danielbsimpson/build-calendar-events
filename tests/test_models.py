"""Tests for the Event model and UID stability."""

from datetime import datetime, timezone

from calendar_events.models import Event


def test_uid_is_stable_for_same_external_id():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = Event(source="f1", title="A", start=start, external_id="round-1")
    b = Event(source="f1", title="Different title", start=start, external_id="round-1")
    assert a.uid == b.uid


def test_uid_differs_across_sources():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = Event(source="f1", title="X", start=start, external_id="1")
    b = Event(source="ufc", title="X", start=start, external_id="1")
    assert a.uid != b.uid


def test_resolved_end_defaults_to_two_hours(sample_event):
    no_end = Event(
        source="test", title="No end", start=sample_event.start, external_id="z"
    )
    assert (no_end.resolved_end - no_end.start).total_seconds() == 2 * 3600
