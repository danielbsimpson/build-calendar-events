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
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import http
from ..models import Event
from .base import Source, register

BASE_URL = "https://www.ufc.com"
EVENTS_URL = "https://www.ufc.com/events"

# Detail-page fight-card selectors (confirmed against live markup 2026-09).
FIGHT_SELECTOR = ".c-listing-fight"
CORNER_NAME_SELECTOR = ".c-listing-fight__corner-name"
WEIGHT_CLASS_SELECTOR = ".c-listing-fight__class-text"

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

    def _fetch_event_page(self, url: str) -> str:
        return http.get(url).text

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

        in_window = [e for e in events if now <= e.start <= cutoff]
        # Enrich only in-window events so detail-page fetches stay bounded.
        return [self._enrich(e) for e in in_window]

    def _enrich(self, event: Event) -> Event:
        """Add the full fight card to the description, falling back on failure."""
        enrichment = self.options.get("enrichment")
        if not getattr(enrichment, "fight_card", False) or not event.url:
            return event
        try:
            bouts = self._parse_fight_card(self._fetch_event_page(event.url))
        except Exception as exc:  # never abort the run over enrichment
            logger.warning("UFC fight-card enrichment failed for %s: %s", event.title, exc)
            return event
        if not bouts:
            return event
        name = event.title.removeprefix("🥊 UFC: ")
        description = self._build_description(name, event.location, bouts, None)
        if getattr(enrichment, "use_llm", False):
            from ..enrich import llm  # lazy import: only when enabled

            description = llm.polish(description, enrichment)
        return replace(event, description=description)

    def _parse_fight_card(self, html: str) -> list[str]:
        """Return ordered bout strings '<red> vs <blue> - <weight class>'."""
        soup = BeautifulSoup(html, "html.parser")
        bouts: list[str] = []
        for fight in soup.select(FIGHT_SELECTOR):
            names = [
                _normalize_ws(n.get_text(" ", strip=True))
                for n in fight.select(CORNER_NAME_SELECTOR)
            ]
            names = [n for n in names if n]
            if len(names) < 2:  # need both corners to form a matchup
                continue
            weight_el = fight.select_one(WEIGHT_CLASS_SELECTOR)
            weight = _clean_weight(weight_el.get_text(strip=True)) if weight_el else ""
            bout = f"{names[0]} vs {names[1]}"
            if weight:
                bout += f" - {weight}"
            bouts.append(bout)
        return bouts

    def _build_description(
        self,
        name: str,
        location: str | None,
        bouts: list[str],
        watch: str | None,
    ) -> str:
        """Compose a description: headline, bout list, and optional venue/watch."""
        lines = [name, ""]
        lines.extend(f"\u2022 {bout}" for bout in bouts)
        if location:
            lines.append("")
            lines.append(f"Venue: {location}")
        if watch:
            lines.append(f"Watch: {watch}")
        return "\n".join(lines)

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
            title=f"🥊 UFC: {name}",
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


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text).strip()


def _clean_weight(text: str) -> str:
    """Turn 'Featherweight Bout' into 'Featherweight'."""
    return _normalize_ws(re.sub(r"\bbout\b\s*$", "", text, flags=re.I))

