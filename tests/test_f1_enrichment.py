"""Tests for F1 weather/session enrichment (offline)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from calendar_events.sources.f1 import F1Source

FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo.json"


def _daily() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["daily"]


def test_weather_summary_formats():
    summary = F1Source({})._weather_summary(_daily())
    assert summary is not None
    assert summary.startswith("Weather: partly cloudy")
    assert "15\u201325\u00b0C" in summary  # rounded from 15.1 / 24.6
    assert "precip 30%" in summary


def test_weather_summary_none_input():
    assert F1Source({})._weather_summary(None) is None


def test_build_description_includes_sections():
    race = datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)
    quali = datetime(2026, 9, 19, 14, 0, tzinfo=timezone.utc)
    desc = F1Source({})._build_description(
        "Marina Bay Street Circuit",
        "Singapore, Singapore",
        race,
        quali,
        None,
        "Weather: clear, 20\u201330\u00b0C, precip 0%",
    )
    assert "Marina Bay Street Circuit" in desc
    assert "Singapore, Singapore" in desc
    assert "Race:" in desc
    assert "Qualifying:" in desc
    assert "Weather: clear" in desc


def test_build_description_omits_weather_when_none():
    race = datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)
    desc = F1Source({})._build_description("Circuit", "Place", race, None, None, None)
    assert "Weather" not in desc
