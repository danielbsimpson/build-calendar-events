"""Durable feed revision state: stable UIDs and SEQUENCE across published runs.

This is deliberately separate from :class:`~calendar_events.store.SentStore`.
``SentStore`` is the *email delivery ledger* (what was emailed to whom). This
tracks the *published feed collection* so that an event keeps the same UID and
only bumps its iCalendar ``SEQUENCE`` when its user-visible content changes,
which is what lets a subscribed calendar update an event in place instead of
creating a duplicate.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from .models import Event

#: Bump when the on-disk schema changes in a backwards-incompatible way.
SCHEMA_VERSION = 1


class FeedState:
    """Tracks the revision of every event currently published in the feed.

    Backed by a small JSON file so it is easy to inspect and version on a
    dedicated branch. A missing file is treated as an empty first run; a file
    that exists but cannot be parsed raises, so corrupt state fails loudly
    rather than silently resetting every event's identity.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._events: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        self._events = data.get("events", {})

    def status(self, event: Event) -> Literal["new", "changed", "unchanged"]:
        """Classify an event against the previously published collection."""
        record = self._events.get(event.uid)
        if record is None:
            return "new"
        if record.get("content_hash") != event.content_hash:
            return "changed"
        return "unchanged"

    def sequence_for(self, event: Event) -> int:
        """Return the iCalendar SEQUENCE to publish for this event.

        New events start at 0. Unchanged events keep their current sequence.
        Changed events increment, so clients treat the event as an update.
        """
        record = self._events.get(event.uid)
        if record is None:
            return 0
        current = int(record.get("sequence", 0))
        return current + 1 if self.status(event) == "changed" else current

    def known_uids(self) -> set[str]:
        """UIDs of every event in the previously published collection."""
        return set(self._events)

    def removed_uids(self, events: Iterable[Event]) -> set[str]:
        """UIDs previously published that are absent from ``events``.

        Absence means the event dropped out of the current collection; it does
        not by itself prove the real-world event was cancelled.
        """
        present = {event.uid for event in events}
        return self.known_uids() - present

    def record_all(self, events: Iterable[Event]) -> None:
        """Replace the tracked collection with ``events``.

        Each event's sequence is resolved against the *prior* state before the
        collection is replaced, so sequences carry forward correctly and events
        no longer present are dropped from the state.
        """
        now = datetime.now(timezone.utc).isoformat()
        updated: dict[str, dict] = {}
        for event in events:
            prior = self._events.get(event.uid)
            updated[event.uid] = {
                "title": event.title,
                "start": event.start.isoformat(),
                "source": event.source,
                "content_hash": event.content_hash,
                "sequence": self.sequence_for(event),
                "first_seen": prior.get("first_seen", now) if prior else now,
                "last_seen": now,
            }
        self._events = updated

    def save(self) -> None:
        """Persist the state to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": SCHEMA_VERSION, "events": self._events}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
