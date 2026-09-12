"""Formula 1 source.

Uses the public Ergast-compatible Jolpica API (https://api.jolpi.ca/ergast/),
which exposes the season calendar including per-session times. Network access is
isolated in `_fetch_raw`; `_parse` is pure so it can be unit-tested offline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from .. import http
from ..models import Event
from .base import Source, register

logger = logging.getLogger(__name__)

# Ergast-compatible endpoint (the original ergast.com is being deprecated).
API_BASE = "https://api.jolpi.ca/ergast/f1"

# Keyless forecast API for race-day weather.
WEATHER_API = "https://api.open-meteo.com/v1/forecast"
# Open-Meteo only forecasts ~16 days out; skip weather beyond this horizon.
WEATHER_HORIZON = timedelta(days=16)

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

            race_dt = self._parse_utc(race["date"], race.get("time"))
            qualifying_dt = self._session_dt(race.get("Qualifying"))
            sprint_dt = self._session_dt(race.get("Sprint"))
            race_event = Event(
                source="f1",
                title=f"🏎️ F1: {race_name}",
                start=race_dt,
                location=location,
                url=url,
                external_id=f"f1-{season}-{rnd}",
            )
            events.append(
                self._enrich_race(
                    race_event, circuit, race_dt, qualifying_dt, sprint_dt, now, cutoff
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
                            title=f"🏎️ F1 {label}: {race_name}",
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
    def _session_dt(session: dict | None) -> datetime | None:
        if not session:
            return None
        return F1Source._parse_utc(session["date"], session.get("time"))

    def _enrich_race(
        self,
        event: Event,
        circuit: dict,
        race_dt: datetime,
        qualifying_dt: datetime | None,
        sprint_dt: datetime | None,
        now: datetime,
        cutoff: datetime,
    ) -> Event:
        """Attach a track/session/weather description; fall back on failure."""
        from dataclasses import replace

        enrichment = self.options.get("enrichment")
        if enrichment is None:
            return event  # base behavior for direct/unit-test use

        weather_line = None
        if getattr(enrichment, "weather", False) and now <= race_dt <= cutoff:
            loc = circuit.get("Location", {})
            if race_dt - now <= WEATHER_HORIZON:
                weather_line = self._weather_summary(
                    self._fetch_weather(
                        loc.get("lat"), loc.get("long"), race_dt.date().isoformat()
                    )
                )

        place = ", ".join(
            p
            for p in (
                circuit.get("Location", {}).get("locality"),
                circuit.get("Location", {}).get("country"),
            )
            if p
        )
        description = self._build_description(
            circuit.get("circuitName", ""),
            place,
            race_dt,
            qualifying_dt,
            sprint_dt,
            weather_line,
        )
        if getattr(enrichment, "use_llm", False):
            from ..enrich import llm  # lazy import: only when enabled

            description = llm.polish(description, enrichment)
        return replace(event, description=description)

    def _fetch_weather(self, lat, lon, date: str) -> dict | None:
        """Return the Open-Meteo daily block for a date, or None on any failure."""
        if lat is None or lon is None:
            return None
        query = urlencode(
            {
                "latitude": lat,
                "longitude": lon,
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,weather_code"
                ),
                "start_date": date,
                "end_date": date,
                "timezone": "UTC",
            }
        )
        try:
            data = http.get(f"{WEATHER_API}?{query}").json()
        except Exception as exc:  # weather is best-effort
            logger.warning("F1 weather fetch failed: %s", exc)
            return None
        daily = data.get("daily")
        if not daily or not daily.get("time"):
            return None
        return daily

    def _weather_summary(self, daily: dict | None) -> str | None:
        """Format an Open-Meteo daily block into a one-line summary."""
        if not daily:
            return None
        try:
            tmax = daily["temperature_2m_max"][0]
            tmin = daily["temperature_2m_min"][0]
            precip = daily["precipitation_probability_max"][0]
            code = int(daily["weather_code"][0])
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        label = _WMO_LABELS.get(code, "mixed conditions")
        return (
            f"Weather: {label}, {round(tmin)}\u2013{round(tmax)}\u00b0C, "
            f"precip {round(precip)}%"
        )

    def _build_description(
        self,
        circuit: str,
        location: str,
        race_dt: datetime,
        qualifying_dt: datetime | None,
        sprint_dt: datetime | None,
        weather_line: str | None,
    ) -> str:
        """Compose circuit/location, session times, and optional weather."""
        lines: list[str] = []
        if circuit:
            lines.append(circuit)
        if location:
            lines.append(location)
        lines.append("")
        lines.append(f"Race: {_fmt_dt(race_dt)}")
        if qualifying_dt:
            lines.append(f"Qualifying: {_fmt_dt(qualifying_dt)}")
        if sprint_dt:
            lines.append(f"Sprint: {_fmt_dt(sprint_dt)}")
        if weather_line:
            lines.append("")
            lines.append(weather_line)
        return "\n".join(lines)

    @staticmethod
    def _parse_utc(date_str: str, time_str: str | None) -> datetime:
        """Combine an ISO date and a HH:MM:SSZ time into a UTC-aware datetime."""
        clean = (time_str or "14:00:00Z").rstrip("Z")
        dt = datetime.strptime(f"{date_str} {clean}", "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)


# Subset of WMO weather-interpretation codes to short labels.
_WMO_LABELS = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "thunderstorm with hail",
}


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%a %d %b %Y %H:%M UTC")
