"""Event data model shared across sources, the store, and the .ics builder."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Event:
    """A single calendar-worthy event produced by a source.

    Times are timezone-aware. Sources should attach the correct timezone
    (ideally UTC) so the calendar client can localize correctly.
    """

    source: str
    """Name of the source that produced this event, e.g. "ufc" or "f1"."""

    title: str
    start: datetime
    end: datetime | None = None
    location: str | None = None
    description: str | None = None
    url: str | None = None

    #: Optional stable identifier from the source. If omitted, one is derived.
    external_id: str | None = None

    #: Free-form extra data a source may want to keep around.
    extra: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        """Stable unique ID used for dedup and as the .ics UID.

        Derived from the source + external id (or title+start when no external
        id is available) so the same event always maps to the same UID.
        """
        basis = self.external_id or f"{self.title}|{self.start.isoformat()}"
        digest = hashlib.sha1(f"{self.source}|{basis}".encode()).hexdigest()[:16]
        return f"{self.source}-{digest}@build-calendar-events"

    @property
    def resolved_end(self) -> datetime:
        """End time, defaulting to two hours after the start when unknown."""
        return self.end or (self.start + timedelta(hours=2))
