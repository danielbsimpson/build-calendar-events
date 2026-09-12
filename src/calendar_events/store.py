"""JSON-backed dedup store: remembers which events have already been sent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .models import Event


class SentStore:
    """Tracks event UIDs that have already been turned into invites.

    Backed by a simple JSON file so it is easy to inspect and version if needed.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._sent: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            self._sent = data.get("sent", {})

    def has(self, event: Event) -> bool:
        """Return True if this event was already recorded as sent."""
        return event.uid in self._sent

    def status(self, event: Event) -> Literal["new", "updated", "unchanged"]:
        """Classify an event against what was previously recorded.

        Records written by the version 1 schema have no content hash and are
        treated as ``"new"`` so they get re-sent once to backfill the hash.
        """
        record = self._sent.get(event.uid)
        if record is None or "content_hash" not in record:
            return "new"
        if record["content_hash"] != event.content_hash:
            return "updated"
        return "unchanged"

    def sequence_for(self, event: Event) -> int:
        """Return the iCalendar SEQUENCE to use for this event.

        Incremented only when a previously sent event has changed, so calendar
        clients treat the new invite as an update rather than a duplicate.
        """
        record = self._sent.get(event.uid)
        if record is None:
            return 0
        current = int(record.get("sequence", 0))
        return current + 1 if self.status(event) == "updated" else current

    def add(self, event: Event) -> None:
        """Record an event as sent (call after successful delivery)."""
        self._sent[event.uid] = {
            "title": event.title,
            "start": event.start.isoformat(),
            "source": event.source,
            "content_hash": event.content_hash,
            "sequence": self.sequence_for(event),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        """Persist the store to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 2, "sent": self._sent}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
