---
goal: Implement Milestone 1 MVP — working F1 and UFC event sources with end-to-end manual run
version: 1.0
date_created: 2026-09-12
last_updated: 2026-09-12
owner: build-calendar-events maintainers
status: 'In progress'
tags: [feature, mvp, sources, f1, ufc]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan implements Milestone 1 (MVP, manual run) from [TODO.md](../TODO.md). It wires the two scaffolded event sources (`f1`, `ufc`) to real data, ensures the end-to-end pipeline produces importable `.ics` invites emailed to the user, and adds parser unit tests with fixtures plus a clear run summary. On completion, `python main.py` fetches upcoming F1 and UFC events, deduplicates them, generates `.ics` files, and emails them.

## 1. Requirements & Constraints

- **REQ-001**: `F1Source.fetch(look_ahead_days)` in [src/calendar_events/sources/f1.py](../src/calendar_events/sources/f1.py) MUST return a non-empty `list[Event]` of upcoming races within the window when the season has remaining rounds.
- **REQ-002**: `UFCSource.fetch(look_ahead_days)` in [src/calendar_events/sources/ufc.py](../src/calendar_events/sources/ufc.py) MUST return a `list[Event]` of upcoming UFC events within the window.
- **REQ-003**: Every returned `Event` MUST have a timezone-aware UTC `start` (`datetime` with `tzinfo=timezone.utc`).
- **REQ-004**: Every returned `Event` MUST set `external_id` to a source-stable identifier so `Event.uid` is deterministic across runs (F1: `f1-<season>-<round>`; UFC: slug of event name + date).
- **REQ-005**: Sources MUST honor their `config.source_options` block: F1 `include_sessions` (bool), UFC `ppv_only` (bool).
- **REQ-006**: F1 source MUST prefer the public API (`https://api.jolpi.ca/ergast/f1`); when the API request fails it MUST raise (pipeline records the error) rather than return partial data.
- **REQ-007**: Generated `.ics` files MUST import cleanly into Google Calendar, Apple Calendar, and Outlook.
- **REQ-008**: `python main.py --dry-run` MUST print a summary and MUST NOT send email or write to the dedup store.
- **SEC-001**: All outbound HTTP requests MUST set a descriptive `User-Agent` header and a request timeout of 15 seconds.
- **SEC-002**: HTML scraping MUST respect the target site `robots.txt` and MUST NOT exceed 1 request per 2 seconds per host.
- **CON-001**: No new runtime dependencies beyond those already in [requirements.txt](../requirements.txt) (`requests`, `beautifulsoup4`, `PyYAML`, `ics`, `tzdata`).
- **CON-002**: Network MUST NOT be accessed during unit tests; all parser tests MUST use local fixtures.
- **CON-003**: Python 3.10+ syntax only; use `zoneinfo` from the standard library for timezone handling.
- **GUD-001**: Timezone-naive API timestamps are UTC; parse with explicit `timezone.utc`, never local time.
- **GUD-002**: A single failing source MUST NOT abort the run (already handled by [pipeline.py](../src/calendar_events/pipeline.py)); parser errors within a source SHOULD skip the offending item and continue.
- **PAT-001**: New network + parsing logic MUST be split into a private `_fetch_raw()` (I/O) and a pure `_parse(raw)` (no I/O) so `_parse` is unit-testable with fixtures.
- **PAT-002**: Sources are discovered only via the `@register("name")` decorator and the imports in [src/calendar_events/sources/__init__.py](../src/calendar_events/sources/__init__.py).

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Implement a fully working F1 source backed by the Jolpica/Ergast API with session support and pure, testable parsing.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In [src/calendar_events/sources/f1.py](../src/calendar_events/sources/f1.py), add module constants `API_TIMEOUT = 15` and `USER_AGENT = "build-calendar-events/0.1 (+https://github.com/<you>/build-calendar-events)"`. | ✅ | 2026-09-12 |
| TASK-002 | Add private method `F1Source._fetch_raw(self) -> dict` that performs `requests.get(f"{API_BASE}/current.json", headers={"User-Agent": USER_AGENT}, timeout=API_TIMEOUT)`, calls `raise_for_status()`, and returns `response.json()`. | ✅ | 2026-09-12 |
| TASK-003 | Add pure method `F1Source._parse(self, raw: dict, look_ahead_days: int) -> list[Event]` that reads `raw["MRData"]["RaceTable"]["Races"]`, builds one race `Event` per round with `external_id=f"f1-{season}-{round}"`, `title=f"F1: {raceName}"`, `location` from `Circuit.circuitName` + `Circuit.Location.locality` + `Circuit.Location.country`, `url` from `race["url"]`, and UTC `start` parsed from `date` + `time` (default `time` to `"14:00:00Z"` when absent). | ✅ | 2026-09-12 |
| TASK-004 | In `_parse`, when `self.options.get("include_sessions")` is truthy, emit additional `Event`s for present keys `FirstPractice`, `SecondPractice`, `ThirdPractice`, `Qualifying`, `Sprint`, each with `external_id=f"f1-{season}-{round}-<session>"` and `title=f"F1 {label}: {raceName}"`. | ✅ | 2026-09-12 |
| TASK-005 | In `_parse`, filter out events whose `start` is before `datetime.now(timezone.utc)` or after `now + timedelta(days=look_ahead_days)`. | ✅ | 2026-09-12 |
| TASK-006 | Replace the stubbed `F1Source.fetch` body to `return self._parse(self._fetch_raw(), look_ahead_days)`; remove the placeholder `# TODO(Milestone 1)` comment and the empty-list return. | ✅ | 2026-09-12 |
| TASK-007 | Add a helper `F1Source._parse_utc(date_str: str, time_str: str) -> datetime` that combines an ISO date and a `HH:MM:SSZ` time into a UTC-aware `datetime`. | ✅ | 2026-09-12 |

### Implementation Phase 2

- GOAL-002: Implement a working UFC source that scrapes the public UFC events schedule with polite rate limiting and pure, testable parsing.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | In [src/calendar_events/sources/ufc.py](../src/calendar_events/sources/ufc.py), add constants `EVENTS_URL = "https://www.ufc.com/events"`, `HTTP_TIMEOUT = 15`, `USER_AGENT` (same value as F1), and `MIN_REQUEST_INTERVAL = 2.0`. | ✅ | 2026-09-12 |
| TASK-009 | Add `UFCSource._fetch_raw(self) -> str` that GETs `EVENTS_URL` with the `User-Agent` header and timeout, calls `raise_for_status()`, and returns `response.text`. | ✅ | 2026-09-12 |
| TASK-010 | Add pure method `UFCSource._parse(self, html: str, look_ahead_days: int) -> list[Event]` using `bs4.BeautifulSoup(html, "html.parser")` to extract per-event: name, date/time, location, and a card/PPV indicator; build `Event` with `source="ufc"`, `external_id=` slug of `name`+`date`, `title=f"UFC: {name}"`, UTC `start`, `location`, and `url`. | ✅ | 2026-09-12 |
| TASK-011 | In `_parse`, when `self.options.get("ppv_only")` is truthy, keep only numbered events whose name matches regex `^UFC\s+\d+`. | ✅ | 2026-09-12 |
| TASK-012 | In `_parse`, wrap per-event parsing in try/except that logs a warning via `logging.getLogger(__name__)` and continues (satisfies GUD-002); filter by the look-ahead window as in TASK-005. | ✅ | 2026-09-12 |
| TASK-013 | Replace the stubbed `UFCSource.fetch` body to `return self._parse(self._fetch_raw(), look_ahead_days)`; remove the placeholder `# TODO(Milestone 1)` comment. | ✅ | 2026-09-12 |
| TASK-014 | Add a helper `UFCSource._slugify(text: str) -> str` producing a lowercase, hyphenated, alphanumeric identifier for `external_id`. | ✅ | 2026-09-12 |

### Implementation Phase 3

- GOAL-003: Add parser unit tests with offline fixtures, verify end-to-end run, and confirm the console summary and logging.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Create directory `tests/fixtures/` and add `f1_current.json` — a trimmed real-shape Ergast `current.json` response containing at least 2 races, one with all session keys and one without `time`. | ✅ | 2026-09-12 |
| TASK-016 | Add `tests/fixtures/ufc_events.html` — a trimmed real-shape snapshot of the UFC events page containing at least one numbered PPV and one Fight Night. | ✅ | 2026-09-12 |
| TASK-017 | Create `tests/test_f1_source.py` verifying `F1Source._parse` returns expected count/UID/`start`(UTC)/`location`; `include_sessions=True` adds session events; window filtering drops past/far-future races. Load the fixture from `tests/fixtures/f1_current.json`; perform no network I/O. | ✅ | 2026-09-12 |
| TASK-018 | Create `tests/test_ufc_source.py` verifying `UFCSource._parse` extracts events with UTC `start` and stable `external_id`; `ppv_only=True` keeps only `^UFC \d+` events. Load the fixture; perform no network I/O. | ✅ | 2026-09-12 |
| TASK-019 | Update [tests/test_sources.py](../tests/test_sources.py) `test_stub_sources_return_empty_list` — remove/replace it, since sources are no longer stubs (monkeypatch `_fetch_raw` to return a fixture and assert non-empty). | ✅ | 2026-09-12 |
| TASK-020 | Run `pytest -q` and confirm all tests pass with zero network access. | ✅ | 2026-09-12 |
| TASK-021 | Execute `python main.py --dry-run --verbose` and confirm the summary line `Fetched N event(s); M new; 0 emailed.` is printed and `.ics` files are written under `data/`. | ✅ | 2026-09-12 |
| TASK-022 | Generate one `.ics` via `python main.py --no-email` and manually import it into Google Calendar, Apple Calendar, and Outlook to confirm REQ-007; record results in this plan. | ⚠️ | Auto-validated via `ics` round-trip (valid VCALENDAR/VEVENT, UTC DTSTART/DTEND, UID, UTF-8 location); manual multi-client import pending user. |
| TASK-023 | In [TODO.md](../TODO.md), check off the completed Milestone 1 items. | ✅ | 2026-09-12 |

## 3. Alternatives

- **ALT-001**: Use the original `ergast.com` API directly for F1 — rejected because it is being deprecated; the Jolpica mirror (`api.jolpi.ca`) is the maintained, drop-in replacement.
- **ALT-002**: Add a heavyweight F1/sports data library or paid API — rejected to honor CON-001 (no new dependencies) and keep the project free to run.
- **ALT-003**: Scrape F1 HTML instead of using an API — rejected because the API provides structured, reliable session times; HTML scraping is reserved as a future fallback.
- **ALT-004**: Consume a UFC JSON/mobile API — rejected because no stable, documented free endpoint exists; HTML scraping of the public schedule is the pragmatic MVP path.

## 4. Dependencies

- **DEP-001**: `requests` (already in [requirements.txt](../requirements.txt)) — HTTP client for both sources.
- **DEP-002**: `beautifulsoup4` (already present) — HTML parsing for the UFC source.
- **DEP-003**: `ics` (already present) — `.ics` generation via [src/calendar_events/ics.py](../src/calendar_events/ics.py).
- **DEP-004**: `tzdata` + stdlib `zoneinfo`/`datetime.timezone` — UTC-correct timestamps on Windows.
- **DEP-005**: Jolpica/Ergast API availability at `https://api.jolpi.ca/ergast/f1` (external service).
- **DEP-006**: Reachability and stable markup of `https://www.ufc.com/events` (external service).

## 5. Files

- **FILE-001**: [src/calendar_events/sources/f1.py](../src/calendar_events/sources/f1.py) — implement `_fetch_raw`, `_parse`, `_parse_utc`, and `fetch`.
- **FILE-002**: [src/calendar_events/sources/ufc.py](../src/calendar_events/sources/ufc.py) — implement `_fetch_raw`, `_parse`, `_slugify`, and `fetch`.
- **FILE-003**: `tests/fixtures/f1_current.json` — new offline fixture for F1 parser tests.
- **FILE-004**: `tests/fixtures/ufc_events.html` — new offline fixture for UFC parser tests.
- **FILE-005**: `tests/test_f1_source.py` — new F1 parser unit tests.
- **FILE-006**: `tests/test_ufc_source.py` — new UFC parser unit tests.
- **FILE-007**: [tests/test_sources.py](../tests/test_sources.py) — update the stub-behavior test.
- **FILE-008**: [TODO.md](../TODO.md) — check off completed Milestone 1 items.

## 6. Testing

- **TEST-001**: `F1Source._parse` on `f1_current.json` returns the expected number of race events with UTC `start`, correct `location`, and deterministic `external_id`/`uid`.
- **TEST-002**: `F1Source._parse` with `include_sessions=True` adds one event per present session key and none for absent keys.
- **TEST-003**: `F1Source._parse` applies the look-ahead window, dropping past and beyond-window races.
- **TEST-004**: `F1Source._parse_utc` defaults a missing `time` to `14:00:00Z` and yields a `timezone.utc` `datetime`.
- **TEST-005**: `UFCSource._parse` on `ufc_events.html` extracts events with UTC `start`, `location`, `url`, and stable `external_id`.
- **TEST-006**: `UFCSource._parse` with `ppv_only=True` keeps only names matching `^UFC \d+`.
- **TEST-007**: `UFCSource._parse` skips a malformed event block without raising and logs a warning.
- **TEST-008**: Updated [tests/test_sources.py](../tests/test_sources.py) confirms both sources return non-empty lists when `_fetch_raw` is monkeypatched to fixture data.
- **TEST-009**: Full `pytest -q` run passes with no network access (CON-002).

## 7. Risks & Assumptions

- **RISK-001**: The UFC page markup changes and breaks the scraper — mitigated by isolating parsing in `_parse`, per-item try/except (GUD-002), and fixture-based tests that flag drift.
- **RISK-002**: The Jolpica API applies rate limits or has downtime — mitigated by timeouts, a descriptive `User-Agent`, and pipeline-level error isolation.
- **RISK-003**: Session time keys vary across the season (e.g., sprint weekends) — mitigated by emitting session events only for keys present in the payload.
- **RISK-004**: Timezone mishandling shifts event times — mitigated by parsing all times as explicit UTC and TEST-001/TEST-004.
- **ASSUMPTION-001**: The Jolpica `current.json` schema matches the classic Ergast schema (`MRData.RaceTable.Races[]`).
- **ASSUMPTION-002**: UFC publishes upcoming events with parseable date, time, and location on `https://www.ufc.com/events`.
- **ASSUMPTION-003**: A default 2-hour event duration (from `Event.resolved_end`) is acceptable for the MVP.

## 8. Related Specifications / Further Reading

- [TODO.md](../TODO.md) — project roadmap and milestone definitions
- [README.md](../README.md) — architecture, configuration, and "adding a new source"
- Jolpica-F1 (Ergast successor) API docs: https://github.com/jolpica/jolpica-f1
- Ergast Developer API reference: https://ergast.com/mrd/
- iCalendar specification (RFC 5545): https://datatracker.ietf.org/doc/html/rfc5545
