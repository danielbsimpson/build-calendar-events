"""UFC source.

No stable free official API exists, so this source is expected to scrape the
public UFC events schedule (falling back between candidate data sources). The
parser should extract event name, date/time, location, and main card start.

STATUS: scaffold. `fetch()` outlines the intended flow but is not yet wired to
the network. See TODO.md, Milestone 1.
"""

from __future__ import annotations

from ..models import Event
from .base import Source, register


@register("ufc")
class UFCSource(Source):
    def fetch(self, look_ahead_days: int) -> list[Event]:
        """Fetch upcoming UFC events within the look-ahead window.

        Planned implementation:
            1. Fetch the public UFC events schedule (respecting robots.txt).
            2. Parse each event: name, date/time (with timezone), location,
               and whether it is a numbered PPV or a Fight Night.
            3. Honor the `ppv_only` option if set.
            4. Filter to events between now and now + look_ahead_days.
            5. Build Event objects with UTC start times.

        Returns an empty list until implemented.
        """
        # ppv_only = bool(self.options.get("ppv_only", False))
        events: list[Event] = []
        # TODO(Milestone 1): scrape the schedule and populate `events`.
        return events
