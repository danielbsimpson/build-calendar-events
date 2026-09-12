"""Tests for the UFC source parser (offline, fixture-based)."""

from datetime import timezone
from pathlib import Path

from calendar_events.sources.ufc import UFCSource

FIXTURE = Path(__file__).parent / "fixtures" / "ufc_events.html"
FAR_AHEAD = 400_000  # days; keeps far-future fixture events


def _load() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_extracts_events():
    events = UFCSource()._parse(_load(), FAR_AHEAD)
    # Two valid events; the malformed card is skipped.
    assert len(events) == 2

    ppv = next(e for e in events if "VOLKANOVSKI" in e.title)
    assert ppv.title == "🥊 UFC: VOLKANOVSKI VS EVLOEV"
    assert ppv.start.tzinfo == timezone.utc
    assert ppv.url == "https://www.ufc.com/event/ufc-333"
    assert ppv.location == "Etihad Arena, Abu Dhabi United Arab Emirates"
    assert ppv.external_id and ppv.external_id.startswith("volkanovski-vs-evloev-")


def test_ppv_only_keeps_numbered_events():
    events = UFCSource({"ppv_only": True})._parse(_load(), FAR_AHEAD)
    assert len(events) == 1
    assert events[0].url.endswith("/ufc-333")


def test_malformed_card_is_skipped_not_raised(caplog):
    events = UFCSource()._parse(_load(), FAR_AHEAD)
    assert all("BROKEN" not in e.title for e in events)


def test_window_filter_drops_far_future():
    events = UFCSource()._parse(_load(), 1)
    assert events == []
