---
goal: Historical-average weather fallback for events beyond the forecast horizon
version: 1.0
date_created: 2026-09-12
last_updated: 2026-09-12
owner: build-calendar-events maintainers
status: 'Planned'
tags: [feature, enrichment, f1, weather]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

The F1 source enriches each race with a weather line, but Open-Meteo only
forecasts roughly 16 days ahead (`WEATHER_HORIZON`), so races further out have no
weather at all. This plan adds a **historical-average fallback**: when a live
forecast is unavailable, the event is enriched with climatology for that
calendar date computed from the **last 5 years** of Open-Meteo archive data —
average / high / low temperature and average / high / low rainfall — clearly
labeled as a historical average rather than a forecast. When the race later moves
inside the forecast horizon, the live forecast replaces the historical line on
the next run.

## 1. Requirements & Constraints

- **REQ-001**: When a race start is beyond `WEATHER_HORIZON` (16 days) but within the look-ahead window, and no live forecast is available, the F1 source MUST attach a historical-average weather line.
- **REQ-002**: The historical line MUST include temperature as average, high, and low, and rainfall as average, high, and low, derived from daily archive data.
- **REQ-003**: Historical data MUST be restricted to the most recent N complete years, default `N = 5`, configurable via `enrichment.historical_years`.
- **REQ-004**: The historical line MUST be visually distinguishable from a forecast (e.g. prefixed `Weather (5-yr avg):`) so the user knows it is not a prediction.
- **REQ-005**: When a live forecast IS available (race within `WEATHER_HORIZON`), the existing forecast behavior MUST be used unchanged and historical data MUST NOT be fetched.
- **REQ-006**: Historical enrichment MUST be best-effort: any fetch/parse failure or insufficient data MUST result in no weather line (return `None`), never an exception that aborts the run.
- **REQ-007**: A feature toggle `enrichment.historical_weather` (default `true`) MUST enable/disable this behavior independently of the `enrichment.weather` forecast toggle.
- **REQ-008**: The historical weather line, like the forecast line, MUST be treated as volatile enrichment and MUST NOT participate in the deduplication hash (consistent with `content_signature` in the incremental-updates plan).
- **CON-001**: No new runtime dependencies; use the shared `http` module (`http.get`) with its existing throttling, retries, and user-agent.
- **CON-002**: Unit tests MUST NOT perform network I/O; use a local Open-Meteo archive JSON fixture.
- **CON-003**: Per-race historical enrichment issues at most `historical_years` archive requests; the `http` module enforces `MIN_REQUEST_INTERVAL = 2.0s`, so far-out races add latency. This is acceptable for the intended monthly run cadence.
- **CON-004**: The Open-Meteo archive endpoint is `https://archive-api.open-meteo.com/v1/archive` and exposes `temperature_2m_max`, `temperature_2m_min`, and `precipitation_sum` as daily variables (no precipitation probability); rainfall is expressed in millimetres via `precipitation_sum`.
- **GUD-001**: Keep network access in a dedicated `_fetch_*` method and keep aggregation/formatting pure and unit-testable.
- **GUD-002**: Reuse the existing `_build_description` weather slot; the historical line occupies the same position as the forecast line.
- **PAT-001**: Mirror the existing forecast pattern in `src/calendar_events/sources/f1.py` (`_fetch_weather` + `_weather_summary`) with parallel `_fetch_climatology` + `_climatology_summary` helpers.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Add configuration for the historical fallback.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `src/calendar_events/config.py` `EnrichmentConfig`, add fields `historical_weather: bool = True` and `historical_years: int = 5`. | | |
| TASK-002 | In `src/calendar_events/config.py` `load_config`, parse `historical_weather` via `_as_bool(enrich_raw.get("historical_weather", True))` and `historical_years=int(enrich_raw.get("historical_years", 5))`. | | |
| TASK-003 | In `config.example.yaml`, document the new `enrichment.historical_weather` and `enrichment.historical_years` options with defaults and a one-line explanation. | | |

### Implementation Phase 2

- GOAL-002: Fetch and aggregate 5-year climatology in the F1 source.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | In `src/calendar_events/sources/f1.py`, add module constants `ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"` and `HISTORICAL_YEARS_DEFAULT = 5`. | | |
| TASK-005 | Add method `_fetch_climatology(self, lat, lon, month: int, day: int, years: int) -> list[dict] \| None`. For each of the last `years` complete calendar years, request the archive API for a ±3-day window around `month/day` with `daily=temperature_2m_max,temperature_2m_min,precipitation_sum` and `timezone=UTC`, using `http.get`. Return a combined list of per-day dicts, or `None` if `lat`/`lon` is missing or all requests fail. Wrap network calls in try/except and `logger.warning` on failure (best-effort). | | |
| TASK-006 | Add pure method `_climatology_summary(self, samples: list[dict] \| None, years: int) -> str \| None`. Aggregate across all sampled days: temperature avg = mean of `temperature_2m_max`/`temperature_2m_min` midpoints (or report high=mean(max), low=mean(min), avg=mean of all); high = max of daily max; low = min of daily min. Rainfall avg = mean of `precipitation_sum`; high = max; low = min. Return `None` when `samples` is empty. | | |
| TASK-007 | Format the historical line as: `Weather ({years}-yr avg): {avg}°C avg ({low}–{high}°C), rain {ravg}mm avg ({rlow}–{rhigh}mm)` using en-dash `\u2013` and degree `\u00b0`, rounding all numbers to whole units. | | |

### Implementation Phase 3

- GOAL-003: Wire the fallback into race enrichment.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | In `src/calendar_events/sources/f1.py` `_enrich_race`, keep the existing forecast branch when `race_dt - now <= WEATHER_HORIZON`. Add an `elif` branch: when `getattr(enrichment, "historical_weather", False)` is true and `now <= race_dt <= cutoff`, compute `weather_line = self._climatology_summary(self._fetch_climatology(loc.get("lat"), loc.get("long"), race_dt.month, race_dt.day, getattr(enrichment, "historical_years", 5)), years)`. | | |
| TASK-009 | Ensure the historical `weather_line` flows through the existing `_build_description(...)` weather slot unchanged (no new description field). | | |
| TASK-010 | Confirm (via the incremental-updates plan's `content_signature`) that neither the forecast nor historical weather line is part of the dedup hash; if that plan is not yet implemented, add an inline comment marking the historical line as excluded-from-hash volatile enrichment. | | |

### Implementation Phase 4

- GOAL-004: Tests and documentation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Add fixture `tests/fixtures/open_meteo_archive.json` containing a representative archive daily block (multiple days of `temperature_2m_max`, `temperature_2m_min`, `precipitation_sum`). | | |
| TASK-012 | In `tests/test_f1_enrichment.py`, add a test that `_climatology_summary` computes correct avg/high/low temperature and avg/high/low rainfall from the fixture, and returns `None` for empty input. | | |
| TASK-013 | Add a test that a race beyond `WEATHER_HORIZON` (patch `_fetch_climatology` to return the fixture samples) produces a description containing `Weather (5-yr avg):`, and that a race within `WEATHER_HORIZON` uses the forecast path and does NOT call climatology. | | |
| TASK-014 | Add a test that historical enrichment is skipped when `enrichment.historical_weather` is `False`, and that a fetch failure (patched to raise) yields no weather line without raising. | | |
| TASK-015 | Update `TODO.md` Milestone 2 enrichment notes to mention the historical-average fallback and link this plan. | | |
| TASK-016 | Run `pytest -q` (all pass, no network) and one live `python main.py --source f1 --dry-run` to confirm far-out races show the historical line and near races show the forecast. | | |

## 3. Alternatives

- **ALT-001**: Use the Open-Meteo Climate API (downscaled model projections) instead of the historical archive. Rejected: projections are model scenarios, not observed history; the user explicitly requested historical averages over the last 5 years.
- **ALT-002**: One archive request spanning the full 5-year range and filter the target date client-side. Rejected: returns ~1825 contiguous daily records per race (large payload) versus small windowed per-year requests.
- **ALT-002b**: Exactly the target day per year with no ±window. Rejected in favor of a ±3-day window to smooth single-day anomalies; window size is a small constant, not user-facing.
- **ALT-003**: Precompute and cache climatology per circuit on disk. Deferred: useful for the automated/monthly runner (Milestone 3) but out of scope here; can be layered on later without changing the summary format.
- **ALT-004**: Express rainfall as a probability like the forecast line. Rejected: the archive exposes `precipitation_sum` (mm), not probability; millimetres is the faithful historical measure and matches the requested avg/high/low rainfall.

## 4. Dependencies

- **DEP-001**: Open-Meteo archive API `https://archive-api.open-meteo.com/v1/archive` (keyless) with `temperature_2m_max`, `temperature_2m_min`, `precipitation_sum` daily variables.
- **DEP-002**: Shared HTTP client `src/calendar_events/http.py` (`http.get`) for throttling, retries, and user-agent.
- **DEP-003**: Existing F1 enrichment scaffolding in `src/calendar_events/sources/f1.py` (`_enrich_race`, `_build_description`, `WEATHER_HORIZON`).
- **DEP-004**: `EnrichmentConfig` in `src/calendar_events/config.py`.
- **DEP-005 (soft)**: `plan/feature-incremental-updates-1.md` `content_signature` to keep weather out of the dedup hash.

## 5. Files

- **FILE-001**: `src/calendar_events/config.py` — add `historical_weather` and `historical_years` to `EnrichmentConfig` and `load_config`.
- **FILE-002**: `src/calendar_events/sources/f1.py` — add `ARCHIVE_API`, `_fetch_climatology`, `_climatology_summary`, and the `_enrich_race` fallback branch.
- **FILE-003**: `config.example.yaml` — document the two new options.
- **FILE-004**: `tests/fixtures/open_meteo_archive.json` — new archive fixture.
- **FILE-005**: `tests/test_f1_enrichment.py` — aggregation, fallback selection, toggle-off, and failure-fallback tests.
- **FILE-006**: `TODO.md` — reference the historical-average fallback and link this plan.

## 6. Testing

- **TEST-001**: `_climatology_summary` returns correct rounded avg/high/low temperature and avg/high/low rainfall for the fixture, and `None` for empty samples.
- **TEST-002**: A race beyond `WEATHER_HORIZON` yields a description containing `Weather (5-yr avg):` when `_fetch_climatology` is patched to return fixture samples.
- **TEST-003**: A race within `WEATHER_HORIZON` uses the forecast path and does not invoke climatology.
- **TEST-004**: Historical enrichment is skipped when `enrichment.historical_weather` is `False`.
- **TEST-005**: A raised exception inside `_fetch_climatology` results in no weather line and no run failure.
- **TEST-006**: `enrichment.historical_years` controls the request count and the `{years}-yr avg` label.
- **TEST-007**: `pytest -q` passes with zero network access.

## 7. Risks & Assumptions

- **RISK-001**: Archive latency — up to `historical_years` requests per far-out race at ≥2s throttle each adds runtime. Mitigation: only fetched for races beyond the forecast horizon and within the look-ahead window; caching deferred to Milestone 3 (ALT-003).
- **RISK-002**: Sparse or missing archive data for a location/date yields too few samples. Mitigation: `_climatology_summary` returns `None` on empty input, degrading gracefully to no weather line.
- **RISK-003**: Circuit coordinates (`lat`/`long`) may be missing from the API for some rounds. Mitigation: `_fetch_climatology` returns `None` when coordinates are absent.
- **RISK-004**: Rainfall in millimetres vs the forecast's precipitation-probability percentage may confuse users. Mitigation: distinct label `Weather (5-yr avg):` and explicit `mm` units.
- **ASSUMPTION-001**: The last 5 complete years are representative enough for a useful average at a fixed circuit/date.
- **ASSUMPTION-002**: Open-Meteo archive coverage extends to all current F1 circuit coordinates for the last 5 years.

## 8. Related Specifications / Further Reading

- [plan/feature-event-enrichment-1.md](feature-event-enrichment-1.md) — original weather/fight-card/LLM enrichment.
- [plan/feature-incremental-updates-1.md](feature-incremental-updates-1.md) — `content_signature` keeping weather out of the dedup hash.
- [plan/feature-robustness-2.md](feature-robustness-2.md) — shared HTTP client, throttling, and per-source failure isolation.
- Open-Meteo Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api
- [TODO.md](../TODO.md) — roadmap and enrichment status.
