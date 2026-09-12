"""Tests for the source registry and stub sources."""

from calendar_events.sources import available_sources, get_source


def test_builtin_sources_registered():
    names = available_sources()
    assert "ufc" in names
    assert "f1" in names


def test_get_source_returns_instance():
    source = get_source("f1", {"include_sessions": True})
    assert source.name == "f1"
    assert source.options == {"include_sessions": True}


def test_stub_sources_return_empty_list():
    # Scaffold sources return [] until implemented (Milestone 1).
    assert get_source("ufc").fetch(120) == []
    assert get_source("f1").fetch(120) == []
