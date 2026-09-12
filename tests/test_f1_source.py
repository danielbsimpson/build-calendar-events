"""Tests for the F1 source parser (offline, fixture-based)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from calendar_events.sources.f1 import F1Source

FIXTURE = Path(__file__).parent / "fixtures" / "f1_current.json"
FAR_AHEAD = 400_000  # days; keeps far-future fixture races


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_returns_future_races_only():
    events = F1Source()._parse(_load(), FAR_AHEAD)
    # Two future races kept; the year-2000 race is dropped as past.
    assert len(events) == 2
    titles = {e.title for e in events}
    assert titles == {"F1: Future Grand Prix A", "F1: Future Grand Prix B"}

    race_a = next(e for e in events if e.title == "F1: Future Grand Prix A")
    assert race_a.start == datetime(2099, 6, 1, 13, 0, tzinfo=timezone.utc)
    assert race_a.start.tzinfo == timezone.utc
    assert race_a.location == "Future Circuit A, Testville, Testland"
    assert race_a.external_id == "f1-2099-1"
    assert race_a.uid.startswith("f1-")


def test_missing_time_defaults_to_1400z():
    events = F1Source()._parse(_load(), FAR_AHEAD)
    race_b = next(e for e in events if e.title == "F1: Future Grand Prix B")
    assert race_b.start == datetime(2099, 6, 15, 14, 0, tzinfo=timezone.utc)


def test_include_sessions_adds_session_events():
    events = F1Source({"include_sessions": True})._parse(_load(), FAR_AHEAD)
    sessions = [e for e in events if e.external_id and e.external_id.count("-") > 2]
    # Race A defines FP1, FP2, FP3, Qualifying (4); Race B defines none.
    assert len(sessions) == 4
    labels = {e.title.split(":")[0] for e in sessions}
    assert labels == {"F1 FP1", "F1 FP2", "F1 FP3", "F1 Qualifying"}


def test_window_filter_drops_far_future():
    events = F1Source()._parse(_load(), 1)
    assert events == []


def test_parse_utc_defaults_and_timezone():
    dt = F1Source._parse_utc("2099-06-01", None)
    assert dt == datetime(2099, 6, 1, 14, 0, tzinfo=timezone.utc)
    dt2 = F1Source._parse_utc("2099-06-01", "09:30:00Z")
    assert dt2 == datetime(2099, 6, 1, 9, 30, tzinfo=timezone.utc)
