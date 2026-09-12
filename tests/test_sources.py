"""Tests for the source registry and stub sources."""

import json
from pathlib import Path

from calendar_events.sources import available_sources, get_source

FIXTURES = Path(__file__).parent / "fixtures"


def test_builtin_sources_registered():
    names = available_sources()
    assert "ufc" in names
    assert "f1" in names


def test_get_source_returns_instance():
    source = get_source("f1", {"include_sessions": True})
    assert source.name == "f1"
    assert source.options == {"include_sessions": True}


def test_sources_return_events_from_fixture(monkeypatch):
    # Sources are wired to real data; monkeypatch the I/O layer with fixtures.
    f1_raw = json.loads(
        (FIXTURES / "f1_current.json").read_text(encoding="utf-8")
    )
    ufc_html = (FIXTURES / "ufc_events.html").read_text(encoding="utf-8")

    f1 = get_source("f1")
    monkeypatch.setattr(f1, "_fetch_raw", lambda: f1_raw)
    assert f1.fetch(400_000)

    ufc = get_source("ufc")
    monkeypatch.setattr(ufc, "_fetch_raw", lambda: ufc_html)
    assert ufc.fetch(400_000)
