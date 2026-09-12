"""JSON-backed dedup store: remembers which events have already been sent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

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

    def add(self, event: Event) -> None:
        """Record an event as sent (call after successful delivery)."""
        self._sent[event.uid] = {
            "title": event.title,
            "start": event.start.isoformat(),
            "source": event.source,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        """Persist the store to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "sent": self._sent}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
