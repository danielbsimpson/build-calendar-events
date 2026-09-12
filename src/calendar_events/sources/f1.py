"""Formula 1 source.

Uses the public Ergast-compatible Jolpica API (https://api.jolpi.ca/ergast/),
which exposes the season calendar including per-session times. Network access is
isolated in `_fetch_raw`; `_parse` is pure so it can be unit-tested offline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .. import http
from ..models import Event
from .base import Source, register

# Ergast-compatible endpoint (the original ergast.com is being deprecated).
API_BASE = "https://api.jolpi.ca/ergast/f1"

# Session key in the API -> human label used in the event title.
_SESSIONS = [
    ("FirstPractice", "FP1"),
    ("SecondPractice", "FP2"),
    ("ThirdPractice", "FP3"),
    ("SprintQualifying", "Sprint Qualifying"),
    ("Sprint", "Sprint"),
    ("Qualifying", "Qualifying"),
]


@register("f1")
class F1Source(Source):
    def fetch(self, look_ahead_days: int) -> list[Event]:
        """Fetch upcoming F1 races (and optionally sessions) within the window."""
        return self._parse(self._fetch_raw(), look_ahead_days)

    def _fetch_raw(self) -> dict:
        response = http.get(f"{API_BASE}/current.json")
        return response.json()

    def _parse(self, raw: dict, look_ahead_days: int) -> list[Event]:
        include_sessions = bool(self.options.get("include_sessions", False))
        races = raw.get("MRData", {}).get("RaceTable", {}).get("Races", [])

        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=look_ahead_days)
        events: list[Event] = []

        for race in races:
            season = race["season"]
            rnd = race["round"]
            race_name = race["raceName"]
            circuit = race.get("Circuit", {})
            location = self._location(circuit)
            url = race.get("url")

            events.append(
                Event(
                    source="f1",
                    title=f"F1: {race_name}",
                    start=self._parse_utc(race["date"], race.get("time")),
                    location=location,
                    url=url,
                    external_id=f"f1-{season}-{rnd}",
                )
            )

            if include_sessions:
                for key, label in _SESSIONS:
                    session = race.get(key)
                    if not session:
                        continue
                    events.append(
                        Event(
                            source="f1",
                            title=f"F1 {label}: {race_name}",
                            start=self._parse_utc(session["date"], session.get("time")),
                            location=location,
                            url=url,
                            external_id=f"f1-{season}-{rnd}-{key}",
                        )
                    )

        return [e for e in events if now <= e.start <= cutoff]

    @staticmethod
    def _location(circuit: dict) -> str | None:
        loc = circuit.get("Location", {})
        parts = [circuit.get("circuitName"), loc.get("locality"), loc.get("country")]
        parts = [p for p in parts if p]
        return ", ".join(parts) or None

    @staticmethod
    def _parse_utc(date_str: str, time_str: str | None) -> datetime:
        """Combine an ISO date and a HH:MM:SSZ time into a UTC-aware datetime."""
        clean = (time_str or "14:00:00Z").rstrip("Z")
        dt = datetime.strptime(f"{date_str} {clean}", "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
