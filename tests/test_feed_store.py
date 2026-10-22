"""Tests for the durable feed revision state."""

from dataclasses import replace

from calendar_events.feed_store import FeedState


def test_new_event_starts_at_sequence_zero(tmp_path, sample_event):
    state = FeedState(tmp_path / "feed_state.json")
    assert state.status(sample_event) == "new"
    assert state.sequence_for(sample_event) == 0


def test_unchanged_event_keeps_sequence_across_runs(tmp_path, sample_event):
    path = tmp_path / "feed_state.json"
    first = FeedState(path)
    first.record_all([sample_event])
    first.save()

    second = FeedState(path)
    assert second.status(sample_event) == "unchanged"
    assert second.sequence_for(sample_event) == 0


def test_changed_event_bumps_sequence_and_persists(tmp_path, sample_event):
    path = tmp_path / "feed_state.json"
    first = FeedState(path)
    first.record_all([sample_event])
    first.save()

    changed = replace(sample_event, location="A different venue")
    assert changed.uid == sample_event.uid

    second = FeedState(path)
    assert second.status(changed) == "changed"
    assert second.sequence_for(changed) == 1
    second.record_all([changed])
    second.save()

    # The bumped sequence must stick: a later unchanged run keeps it at 1.
    third = FeedState(path)
    assert third.status(changed) == "unchanged"
    assert third.sequence_for(changed) == 1


def test_removed_uids_reports_events_absent_from_new_collection(tmp_path, sample_event):
    other = replace(sample_event, external_id="evt-456", title="Second Event")
    path = tmp_path / "feed_state.json"
    first = FeedState(path)
    first.record_all([sample_event, other])
    first.save()

    second = FeedState(path)
    removed = second.removed_uids([sample_event])
    assert removed == {other.uid}

    # Recording the smaller collection drops the removed event from state.
    second.record_all([sample_event])
    second.save()
    assert FeedState(path).known_uids() == {sample_event.uid}
