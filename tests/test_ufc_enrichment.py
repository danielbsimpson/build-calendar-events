"""Tests for UFC fight-card enrichment (offline)."""

from pathlib import Path

from calendar_events.sources.ufc import UFCSource

FIXTURE = Path(__file__).parent / "fixtures" / "ufc_event_page.html"


def _html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_fight_card_orders_and_formats():
    bouts = UFCSource({})._parse_fight_card(_html())
    assert len(bouts) == 3
    assert bouts[0] == "Jean Silva vs Jose Miguel Delgado - Featherweight"
    assert bouts[1] == "Brandon Moreno vs Joseph Morales - Flyweight"
    for bout in bouts:
        assert " vs " in bout and " - " in bout


def test_parse_fight_card_skips_rows_missing_names():
    bouts = UFCSource({})._parse_fight_card(_html())
    assert all("TBD" not in bout for bout in bouts)


def test_build_description_includes_bouts_and_venue():
    bouts = ["A vs B - Lightweight", "C vs D - Welterweight"]
    desc = UFCSource({})._build_description(
        "UFC Fight Night", "T-Mobile Arena, Las Vegas", bouts, None
    )
    assert desc.startswith("UFC Fight Night")
    assert "\u2022 A vs B - Lightweight" in desc
    assert "Venue: T-Mobile Arena, Las Vegas" in desc
