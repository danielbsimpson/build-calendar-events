"""Tests for the JSON dedup store."""

import json
from dataclasses import replace

from calendar_events.store import SentStore


def test_store_roundtrip(tmp_path, sample_event):
    store_path = tmp_path / "sent.json"
    store = SentStore(store_path)

    assert not store.has(sample_event)
    store.add(sample_event)
    store.save()

    reloaded = SentStore(store_path)
    assert reloaded.has(sample_event)


def test_missing_store_file_is_empty(tmp_path, sample_event):
    store = SentStore(tmp_path / "does_not_exist.json")
    assert not store.has(sample_event)


def test_status_new_then_unchanged(tmp_path, sample_event):
    store = SentStore(tmp_path / "sent.json")
    assert store.status(sample_event) == "new"
    store.add(sample_event)
    assert store.status(sample_event) == "unchanged"


def test_status_updated_when_content_changes(tmp_path, sample_event):
    store = SentStore(tmp_path / "sent.json")
    store.add(sample_event)
    changed = replace(sample_event, description="Rescheduled to a new time.")
    assert changed.uid == sample_event.uid
    assert store.status(changed) == "updated"


def test_sequence_bumps_only_on_update(tmp_path, sample_event):
    store = SentStore(tmp_path / "sent.json")
    assert store.sequence_for(sample_event) == 0
    store.add(sample_event)
    assert store.sequence_for(sample_event) == 0

    changed = replace(sample_event, location="Elsewhere")
    assert store.sequence_for(changed) == 1
    store.add(changed)
    assert store.sequence_for(changed) == 1


def test_version1_record_is_treated_as_new(tmp_path, sample_event):
    path = tmp_path / "sent.json"
    legacy = {
        "version": 1,
        "sent": {
            sample_event.uid: {
                "title": sample_event.title,
                "start": sample_event.start.isoformat(),
                "source": sample_event.source,
                "recorded_at": "2020-01-01T00:00:00+00:00",
            }
        },
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")
    store = SentStore(path)
    assert store.status(sample_event) == "new"
