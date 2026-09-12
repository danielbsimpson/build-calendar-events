"""Tests for pipeline resilience and the look-ahead override."""

from datetime import datetime, timedelta, timezone

from calendar_events import pipeline
from calendar_events.config import Config, EmailConfig
from calendar_events.models import Event


def _config(tmp_path) -> Config:
    return Config(
        look_ahead_days=120,
        sources=[],
        data_dir=tmp_path / "data",
        store_file=tmp_path / "data" / "sent.json",
        email=EmailConfig(),
    )


def _event(title: str, days_ahead: int, source: str = "test") -> Event:
    start = datetime.now(timezone.utc) + timedelta(days=days_ahead)
    return Event(source=source, title=title, start=start, external_id=title)


class _FakeSource:
    def __init__(self, events=None, error=None):
        self._events = events or []
        self._error = error

    def fetch(self, look_ahead_days):
        if self._error is not None:
            raise self._error
        return self._events


def test_pipeline_isolates_failing_source(tmp_path, monkeypatch):
    sources = {
        "good": _FakeSource([_event("Good", 3)]),
        "bad": _FakeSource(error=RuntimeError("boom")),
    }
    monkeypatch.setattr(pipeline, "get_source", lambda name, options: sources[name])

    result = pipeline.run(_config(tmp_path), ["bad", "good"], dry_run=True)

    assert result.fetched == 1
    assert result.new == 1
    assert any("bad" in err for err in result.errors)


def test_pipeline_isolates_failing_event(tmp_path, monkeypatch):
    events = [_event("Ok", 3), _event("Broken", 4)]
    monkeypatch.setattr(
        pipeline, "get_source", lambda name, options: _FakeSource(events)
    )

    def fake_write(event, out_dir, **_kw):
        if event.title == "Broken":
            raise RuntimeError("disk full")
        return tmp_path / f"{event.uid}.ics"

    monkeypatch.setattr(pipeline, "write_ics", fake_write)

    result = pipeline.run(_config(tmp_path), ["s"], dry_run=True)

    assert result.new == 2  # both counted before the build step
    assert any("Broken" in err for err in result.errors)


def test_look_ahead_override_excludes_far_events(tmp_path, monkeypatch):
    events = [_event("Near", 3), _event("Far", 30)]
    monkeypatch.setattr(
        pipeline, "get_source", lambda name, options: _FakeSource(events)
    )

    result = pipeline.run(_config(tmp_path), ["s"], dry_run=True, look_ahead_days=7)

    assert result.new == 1
