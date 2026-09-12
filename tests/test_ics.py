"""Tests for the .ics builder."""

from calendar_events.ics import build_calendar, write_ics


def test_build_calendar_contains_event(sample_event):
    text = build_calendar(sample_event).serialize()
    assert "BEGIN:VCALENDAR" in text
    assert "BEGIN:VEVENT" in text
    assert sample_event.title in text
    assert sample_event.uid in text


def test_write_ics_creates_file(tmp_path, sample_event):
    path = write_ics(sample_event, tmp_path)
    assert path.exists()
    assert path.suffix == ".ics"
    assert sample_event.title in path.read_text(encoding="utf-8")
