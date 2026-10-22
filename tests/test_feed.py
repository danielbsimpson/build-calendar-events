"""Tests for feed orchestration and publication-safety validation."""

from datetime import datetime, timedelta, timezone
from dataclasses import replace

import pytest

from calendar_events import feed
from calendar_events.config import Config
from calendar_events.feed_store import FeedState
from calendar_events.models import Event


def _config(tmp_path, sources) -> Config:
    return Config(
        look_ahead_days=120,
        sources=sources,
        data_dir=tmp_path / "data",
        feed_file=tmp_path / "public" / "sports.ics",
        feed_state_file=tmp_path / "data" / "feed_state.json",
        calendar_name="Sports",
    )


def _event(title, days_ahead, source="test", external_id=None) -> Event:
    start = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    return Event(
        source=source,
        title=title,
        start=start,
        external_id=external_id or title,
    )


class _FakeSource:
    def __init__(self, events=None, error=None):
        self._events = events or []
        self._error = error

    def fetch(self, look_ahead_days):
        if self._error is not None:
            raise self._error
        return self._events


def _patch_sources(monkeypatch, mapping):
    monkeypatch.setattr(feed, "get_source", lambda name, options: mapping[name])


def test_build_feed_fails_closed_when_a_source_errors(tmp_path, monkeypatch):
    _patch_sources(
        monkeypatch,
        {
            "f1": _FakeSource([_event("Race", 3, "f1")]),
            "ufc": _FakeSource(error=RuntimeError("scrape broke")),
        },
    )
    config = _config(tmp_path, ["f1", "ufc"])

    with pytest.raises(feed.SourceFetchError):
        feed.build_feed(config)

    # Nothing is published when a source fails.
    assert not config.feed_file.exists()
    assert not config.feed_state_file.exists()


def test_build_feed_blocks_empty_source_unless_authorized(tmp_path, monkeypatch):
    _patch_sources(
        monkeypatch,
        {
            "f1": _FakeSource([_event("Race", 3, "f1")]),
            "ufc": _FakeSource([]),
        },
    )
    config = _config(tmp_path, ["f1", "ufc"])

    with pytest.raises(feed.EmptySourceError):
        feed.build_feed(config)

    # Explicit authorization lets an empty source through.
    result = feed.build_feed(config, allow_empty=True)
    assert result.sources == {"f1": 1, "ufc": 0}
    assert result.total == 1


def test_build_feed_publishes_complete_in_window_collection(tmp_path, monkeypatch):
    _patch_sources(
        monkeypatch,
        {
            "f1": _FakeSource([_event("Race", 3, "f1"), _event("Far Race", 400, "f1")]),
            "ufc": _FakeSource([_event("Fight", 10, "ufc")]),
        },
    )
    config = _config(tmp_path, ["f1", "ufc"])

    result = feed.build_feed(config)

    # The out-of-window race is excluded; both in-window events are included.
    assert result.total == 2
    assert result.ics.count("BEGIN:VEVENT") == 2
    assert "Race" in result.ics
    assert "Fight" in result.ics
    assert "Far Race" not in result.ics


def test_build_feed_diffs_against_previously_published_state(tmp_path, monkeypatch):
    race = _event("Race", 3, "f1", external_id="r1")
    fight = _event("Fight", 10, "ufc", external_id="u1")
    _patch_sources(monkeypatch, {"f1": _FakeSource([race]), "ufc": _FakeSource([fight])})
    config = _config(tmp_path, ["f1", "ufc"])

    first = feed.build_feed(config)
    assert sorted(first.added) == sorted([race.uid, fight.uid])
    first.state.save()

    # Second run: race is rescheduled, fight is dropped, a new event appears.
    moved_race = replace(race, start=race.start + timedelta(hours=1))
    new_event = _event("Grand Prix", 20, "f1", external_id="r2")
    _patch_sources(
        monkeypatch,
        {"f1": _FakeSource([moved_race, new_event]), "ufc": _FakeSource([])},
    )

    second = feed.build_feed(config, allow_empty=True)
    assert second.changed == [moved_race.uid]
    assert second.added == [new_event.uid]
    assert second.removed == [fight.uid]
    assert second.unchanged == []


def test_build_feed_state_is_prepared_but_not_saved(tmp_path, monkeypatch):
    _patch_sources(monkeypatch, {"f1": _FakeSource([_event("Race", 3, "f1")])})
    config = _config(tmp_path, ["f1"])

    result = feed.build_feed(config)

    # build_feed must not persist; the caller decides (dry run vs publish).
    assert not config.feed_state_file.exists()
    result.state.save()
    assert FeedState(config.feed_state_file).known_uids()
