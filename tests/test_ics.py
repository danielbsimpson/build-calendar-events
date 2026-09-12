"""Tests for the .ics builder."""

from dataclasses import replace

from ics import Calendar

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


def test_build_calendar_includes_alarms(sample_event):
    event = replace(sample_event, alarms=(60, 15))
    text = build_calendar(event).serialize()
    assert text.count("BEGIN:VALARM") == 2
    assert "TRIGGER" in text


def test_build_calendar_sequence_and_method(sample_event):
    text = build_calendar(sample_event, sequence=3, method="REQUEST").serialize()
    assert "SEQUENCE:3" in text
    assert "METHOD:REQUEST" in text


def test_build_calendar_includes_details_in_description(sample_event):
    event = replace(
        sample_event,
        details=("Fighter A vs Fighter B", "Fighter C vs Fighter D"),
    )
    cal = Calendar(build_calendar(event).serialize())
    description = list(cal.events)[0].description
    assert "Fighter A vs Fighter B" in description
    assert "Fighter C vs Fighter D" in description
