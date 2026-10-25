"""Tests for the UFC source parser (offline, fixture-based)."""

from datetime import timezone
from pathlib import Path

from calendar_events.sources.ufc import UFCSource

FIXTURE = Path(__file__).parent / "fixtures" / "ufc_events.html"
FAR_AHEAD = 400_000  # days; keeps far-future fixture events


def _load() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def _card(name: str, slug: str, timestamp: int = 4081312800) -> str:
    """A minimal UFC event card with a given headline name and URL slug."""
    return (
        '<div class="c-card-event--result">'
        '<h3 class="c-card-event--result__headline">'
        f'<a href="/event/{slug}">{name}</a></h3>'
        '<div class="c-card-event--result__date tz-change-data" '
        f'data-main-card-timestamp="{timestamp}"></div>'
        "</div>"
    )


def test_parse_extracts_events():
    events = UFCSource()._parse(_load(), FAR_AHEAD)
    # Two valid events; the malformed card is skipped.
    assert len(events) == 2

    ppv = next(e for e in events if "VOLKANOVSKI" in e.title)
    assert ppv.title == "🥊 UFC: VOLKANOVSKI VS EVLOEV"
    assert ppv.start.tzinfo == timezone.utc
    assert ppv.url == "https://www.ufc.com/event/ufc-333"
    assert ppv.location == "Etihad Arena, Abu Dhabi United Arab Emirates"
    assert ppv.external_id == "ufc-333"


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


def test_external_id_uses_url_slug():
    events = UFCSource()._parse(_card("Van vs Kape", "ufc-336"), FAR_AHEAD)
    assert len(events) == 1
    assert events[0].external_id == "ufc-336"


def test_uid_stable_when_headliner_announced():
    # Same event page (slug), headliner goes from TBD to an announced matchup.
    tbd = UFCSource()._parse(_card("TBD vs TBD", "ufc-336"), FAR_AHEAD)[0]
    announced = UFCSource()._parse(_card("Van vs Kape", "ufc-336"), FAR_AHEAD)[0]

    # Identity is stable, so a subscriber's event updates in place...
    assert announced.uid == tbd.uid
    # ...and the content hash changes, so SEQUENCE bumps (a real update).
    assert announced.content_hash != tbd.content_hash


def test_external_id_falls_back_to_name_and_date_without_slug():
    # A card whose link has no event slug falls back to the old scheme.
    card = _card("Some Fight", "").replace('href="/event/"', 'href="/events"')
    event = UFCSource()._parse(card, FAR_AHEAD)[0]
    assert event.external_id.startswith("some-fight-")
