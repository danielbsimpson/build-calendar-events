"""Tests for the JSON dedup store."""

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
