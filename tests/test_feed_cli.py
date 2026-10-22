"""Smoke tests for the `feed` CLI subcommand wiring."""

from datetime import datetime, timedelta, timezone

import yaml

from calendar_events import cli, feed
from calendar_events.feed_store import FeedState
from calendar_events.models import Event


def _write_config(tmp_path):
    config = {
        "look_ahead_days": 120,
        "sources": ["f1"],
        "data_dir": str(tmp_path / "data"),
        "feed_file": str(tmp_path / "public" / "sports.ics"),
        "feed_state_file": str(tmp_path / "data" / "feed_state.json"),
        "calendar_name": "Sports",
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


class _FakeSource:
    def fetch(self, look_ahead_days):
        start = datetime.now(timezone.utc) + timedelta(days=5)
        return [Event(source="f1", title="Race", start=start, external_id="r1")]


def test_feed_command_writes_feed_and_state(tmp_path, monkeypatch):
    monkeypatch.setattr(feed, "get_source", lambda name, options: _FakeSource())
    config_path = _write_config(tmp_path)

    code = cli.main(["feed", "--config", str(config_path)])

    assert code == 0
    feed_file = tmp_path / "public" / "sports.ics"
    assert feed_file.exists()
    assert "BEGIN:VEVENT" in feed_file.read_text(encoding="utf-8")
    assert FeedState(tmp_path / "data" / "feed_state.json").known_uids()


def test_feed_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(feed, "get_source", lambda name, options: _FakeSource())
    config_path = _write_config(tmp_path)

    code = cli.main(["feed", "--config", str(config_path), "--dry-run"])

    assert code == 0
    assert not (tmp_path / "public" / "sports.ics").exists()
    assert not (tmp_path / "data" / "feed_state.json").exists()


def test_feed_command_fails_closed_on_empty_source(tmp_path, monkeypatch):
    class _Empty:
        def fetch(self, look_ahead_days):
            return []

    monkeypatch.setattr(feed, "get_source", lambda name, options: _Empty())
    config_path = _write_config(tmp_path)

    code = cli.main(["feed", "--config", str(config_path)])

    assert code == 1
    assert not (tmp_path / "public" / "sports.ics").exists()


def test_step_summary_outcome_matches_result(tmp_path, monkeypatch):
    summary = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    config_path = _write_config(tmp_path)

    # A rejected build must not report itself as published.
    class _Empty:
        def fetch(self, look_ahead_days):
            return []

    monkeypatch.setattr(feed, "get_source", lambda name, options: _Empty())
    assert cli.main(["feed", "--config", str(config_path)]) == 1
    failed = summary.read_text(encoding="utf-8")
    assert "not published" in failed
    assert "Outcome: published" not in failed

    # A successful build reports "published".
    summary.write_text("", encoding="utf-8")
    monkeypatch.setattr(feed, "get_source", lambda name, options: _FakeSource())
    assert cli.main(["feed", "--config", str(config_path)]) == 0
    assert "Outcome: published" in summary.read_text(encoding="utf-8")
