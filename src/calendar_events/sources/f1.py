"""Formula 1 source.

Prefers the public Ergast-compatible API (https://api.jolpi.ca/ergast/), which
exposes the season calendar including per-session times. HTML scraping can be
added later as a fallback if the API is unavailable.

STATUS: scaffold. `fetch()` outlines the intended flow but is not yet wired to
the network. See TODO.md, Milestone 1.
"""

from __future__ import annotations

from ..models import Event
from .base import Source, register

# Ergast-compatible endpoint (the original ergast.com is being deprecated).
API_BASE = "https://api.jolpi.ca/ergast/f1"


@register("f1")
class F1Source(Source):
    def fetch(self, look_ahead_days: int) -> list[Event]:
        """Fetch upcoming F1 races within the look-ahead window.

        Planned implementation:
            1. GET {API_BASE}/current.json to list the season's rounds.
            2. For each round, read `date`/`time` (race) and, when
               `include_sessions` is set, the FirstPractice/Qualifying/Sprint
               session times.
            3. Filter to events between now and now + look_ahead_days.
            4. Build Event objects (UTC start times, location from Circuit).

        Returns an empty list until implemented.
        """
        # include_sessions = bool(self.options.get("include_sessions", False))
        events: list[Event] = []
        # TODO(Milestone 1): call the API and populate `events`.
        return events
