"""UFC source.

No stable free official API exists, so this source scrapes the public UFC events
schedule at https://www.ufc.com/events. Each event card exposes a
`data-main-card-timestamp` (UTC epoch seconds) attribute, which gives an exact,
timezone-safe start time. Network access is isolated in `_fetch_raw`; `_parse`
is pure so it can be unit-tested offline.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import http
from ..models import Event
from .base import Source, register

BASE_URL = "https://www.ufc.com"
EVENTS_URL = "https://www.ufc.com/events"

logger = logging.getLogger(__name__)

# Numbered PPV events have URL slugs like ufc-332 / cryptocom-ufc-331.
_PPV_SLUG = re.compile(r"ufc-\d+")


@register("ufc")
class UFCSource(Source):
    def fetch(self, look_ahead_days: int) -> list[Event]:
        """Fetch upcoming UFC events within the look-ahead window."""
        return self._parse(self._fetch_raw(), look_ahead_days)

    def _fetch_raw(self) -> str:
        if not http.robots_allows(EVENTS_URL):
            raise PermissionError(f"robots.txt disallows fetching {EVENTS_URL}")
        return http.get(EVENTS_URL).text

    def _parse(self, html: str, look_ahead_days: int) -> list[Event]:
        ppv_only = bool(self.options.get("ppv_only", False))
        soup = BeautifulSoup(html, "html.parser")

        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=look_ahead_days)
        events: list[Event] = []

        for card in soup.select(".c-card-event--result"):
            try:
                event = self._parse_card(card)
            except Exception as exc:  # skip a malformed card, keep going
                logger.warning("Skipping unparseable UFC card: %s", exc)
                continue
            if event is None:
                continue
            if ppv_only and not _PPV_SLUG.search(event.url or ""):
                continue
            events.append(event)

        return [e for e in events if now <= e.start <= cutoff]

    def _parse_card(self, card) -> Event | None:
        headline = card.select_one("h3.c-card-event--result__headline a")
        date_el = card.select_one(".c-card-event--result__date")
        if headline is None or date_el is None:
            return None

        name = headline.get_text(strip=True)
        url = urljoin(BASE_URL, headline.get("href", ""))
        timestamp = date_el.get("data-main-card-timestamp")
        if not timestamp:
            return None
        start = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)

        location = self._location(card)
        return Event(
            source="ufc",
            title=f"UFC: {name}",
            start=start,
            location=location,
            url=url,
            external_id=self._slugify(f"{name}-{start.date().isoformat()}"),
        )

    @staticmethod
    def _location(card) -> str | None:
        loc_el = card.select_one(".c-card-event--result__location")
        if loc_el is None:
            return None
        venue_el = loc_el.select_one("h5")
        venue = venue_el.get_text(strip=True) if venue_el else None
        locality = loc_el.get_text(" ", strip=True)
        if venue:
            locality = locality.replace(venue, "", 1)
        locality = re.sub(r"\s+,", ",", re.sub(r"\s{2,}", " ", locality)).strip(" ,")
        parts = [p for p in (venue, locality) if p]
        return ", ".join(parts) or None

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug or "ufc-event"

