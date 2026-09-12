"""Tests for the .ics builder."""

from dataclasses import replace

from ics import Calendar

from calendar_events.ics import build_calendar, serialize_calendar, write_ics


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


def test_serialize_uses_crlf_line_endings(sample_event):
    text = serialize_calendar(build_calendar(sample_event))
    assert "\r\n" in text
    assert "\r\r\n" not in text
    # No bare LF that isn't part of a CRLF pair.
    assert "\n" not in text.replace("\r\n", "")


def test_serialize_places_method_before_vevent(sample_event):
    text = serialize_calendar(build_calendar(sample_event, method="REQUEST"))
    assert text.index("METHOD:REQUEST") < text.index("BEGIN:VEVENT")


def test_serialize_folds_long_lines(sample_event):
    long_desc = "Bulletpoint " * 40
    event = replace(
        sample_event,
        description=long_desc,
        location="A very long venue name " * 6,
    )
    text = serialize_calendar(build_calendar(event))
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75
    # Folded output must still round-trip back to the full values.
    parsed = list(Calendar(text).events)[0]
    assert "Bulletpoint" in parsed.description


def test_serialize_folds_multibyte_without_splitting(sample_event):
    event = replace(sample_event, description="🥊 " * 60)
    text = serialize_calendar(build_calendar(event))
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75
    # A clean UTF-8 decode proves no multi-byte character was split at a fold.
    parsed = list(Calendar(text).events)[0]
    assert "🥊" in parsed.description

