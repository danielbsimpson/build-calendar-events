---
goal: Enrich event descriptions with detailed, source-specific context (UFC full fight card, F1 track/qualifying/weather), with an optional local-LLM polishing layer
version: 1.0
date_created: 2026-09-12
last_updated: 2026-09-12
owner: build-calendar-events maintainers
status: 'Planned'
tags: [feature, enrichment, sources, ufc, f1, llm]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan enhances the `Event.description` produced by each source so calendar invites contain meaningful detail instead of only a headline. For UFC, the description will list every bout on the card in `Fighter 1 vs Fighter 2 - Weightclass` format plus venue/broadcast context. For F1, the description will include the circuit name, locality/country, qualifying and sprint session times, and a short weather forecast for the race day. Enrichment is implemented first as deterministic regex/formatting logic (Phase 1–3). Phase 4 adds an OPTIONAL local-LLM polishing layer (Ollama or llama.cpp server) that rewrites the assembled facts into prose, controlled entirely by config and disabled by default. This plan builds on the completed Milestone 1 sources ([plan/feature-mvp-sources-1.md](feature-mvp-sources-1.md)) and is independent of Milestone 2 ([plan/feature-robustness-2.md](feature-robustness-2.md)).

## 1. Requirements & Constraints

- **REQ-001**: `UFCSource` in [src/calendar_events/sources/ufc.py](../src/calendar_events/sources/ufc.py) MUST populate `Event.description` with a bulleted list of every bout on the card, each formatted exactly as `<Red Corner> vs <Blue Corner> - <Weight Class>`.
- **REQ-002**: The UFC bout list MUST preserve card order (main event first) and MUST include the venue line and, when present, the broadcast/"how to watch" line.
- **REQ-003**: `F1Source` in [src/calendar_events/sources/f1.py](../src/calendar_events/sources/f1.py) MUST populate the race `Event.description` with: circuit name, `locality, country`, race UTC start, qualifying UTC start (when present), sprint UTC start (when present), and a weather summary line (when available).
- **REQ-004**: F1 weather MUST be fetched from the keyless Open-Meteo forecast API (`https://api.open-meteo.com/v1/forecast`) using the circuit `lat`/`long` already present in the Ergast payload and the race `date`.
- **REQ-005**: When a weather forecast is unavailable (e.g., race date beyond the forecast horizon or API failure), the description MUST omit the weather line and MUST NOT raise.
- **REQ-006**: All enrichment MUST degrade gracefully: a failure to fetch or parse detail data MUST fall back to the Milestone 1 description behavior for that event and log a warning, never aborting the run (consistent with `pipeline.run` error isolation in [src/calendar_events/pipeline.py](../src/calendar_events/pipeline.py)).
- **REQ-007**: A configuration block `enrichment` MUST be added to [config.example.yaml](../config.example.yaml) and parsed by [src/calendar_events/config.py](../src/calendar_events/config.py) with keys: `fight_card` (bool, default `true`), `weather` (bool, default `true`), `use_llm` (bool, default `false`), `llm_backend` (`"ollama"|"llamacpp"`, default `"ollama"`), `llm_model` (str, default `"llama3"`), `llm_endpoint` (str, default `"http://localhost:11434"`).
- **REQ-008**: When `enrichment.use_llm` is `true`, a new module `src/calendar_events/enrich/llm.py` MUST send the assembled deterministic facts to the configured local backend and replace `Event.description` with the model output; when `false`, the LLM module MUST NOT be imported or called.
- **REQ-009**: When `use_llm` is `true` but the backend is unreachable or returns an error, the description MUST fall back to the deterministic text and log a warning (REQ-006).
- **SEC-001**: All new outbound HTTP requests (UFC event pages, Open-Meteo, LLM endpoint) MUST set the existing `USER_AGENT` header and a 15-second timeout.
- **SEC-002**: Per-host politeness for UFC detail-page fetches MUST NOT exceed 1 request per 2 seconds; the number of detail-page fetches per run MUST be bounded by the number of in-window events.
- **SEC-003**: The LLM prompt MUST contain only already-public event facts; no secrets, credentials, or config values may be included in the prompt.
- **CON-001**: No new runtime dependencies beyond those in [requirements.txt](../requirements.txt) (`requests`, `beautifulsoup4`, `PyYAML`, `ics`, `tzdata`). Ollama and llama.cpp are accessed via their local HTTP APIs using `requests`.
- **CON-002**: Unit tests MUST NOT perform real network I/O; UFC card parsing, weather formatting, and LLM prompt construction MUST be tested against local fixtures or monkeypatched fetchers.
- **CON-003**: Python 3.10+ syntax only; all times remain timezone-aware UTC.
- **CON-004**: Changes MUST be backward compatible: existing `config.yaml` files without an `enrichment` block MUST use the documented defaults.
- **GUD-001**: Keep network I/O (`_fetch_*`) separate from pure formatting (`_parse_*`, `_build_description`) so formatting is unit-testable offline (pattern established in Milestone 1).
- **GUD-002**: The deterministic description MUST be assembled even when `use_llm` is `true`, because it is both the LLM input and the fallback.
- **PAT-001**: Description assembly MUST live in pure helper functions returning `str`, consumed by each source before constructing the `Event`.
- **PAT-002**: LLM access MUST go through a single `enrich/llm.py` interface with a `polish(facts: str, config) -> str` function so backends are swappable.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Enrich UFC event descriptions with the full fight card by scraping each event's detail page, with pure parsing/formatting and graceful fallback.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Verify live UFC event-page markup: fetch one event URL (e.g., `https://www.ufc.com/event/ufc-333`) and confirm the selectors for bout rows, red/blue corner names, and weight class (candidates: `.c-listing-fight__corner-name`, `.c-listing-fight__class-text`). Record confirmed selectors as module constants in [src/calendar_events/sources/ufc.py](../src/calendar_events/sources/ufc.py). | | |
| TASK-002 | Add `UFCSource._fetch_event_page(self, url: str) -> str` that GETs the event detail URL with `USER_AGENT` and `HTTP_TIMEOUT`, calls `raise_for_status()`, and returns `response.text`. | | |
| TASK-003 | Add pure method `UFCSource._parse_fight_card(self, html: str) -> list[str]` returning ordered bout strings `"<red> vs <blue> - <weight class>"`; skip a bout row that lacks both corner names; normalize whitespace. | | |
| TASK-004 | Add pure helper `UFCSource._build_description(self, name: str, location: str | None, bouts: list[str], watch: str | None) -> str` that composes: a header line (`name`), a blank line, one line per bout, and optional `Venue:`/`Watch:` lines. | | |
| TASK-005 | In `UFCSource._parse_card`, after building the base `Event`, when `enrichment.fight_card` is enabled call `_fetch_event_page` + `_parse_fight_card` inside a `try/except` (log warning + fall back to headline-only description on failure) and set `Event.description` via `_build_description`. | | |
| TASK-006 | Pass the `enrichment` config into `UFCSource` via `Source.options` (or a dedicated attribute) so `_parse_card` can read `fight_card`/`use_llm` without importing global config. | | |

### Implementation Phase 2

- GOAL-002: Enrich F1 race descriptions with track, session, and weather details, using the Open-Meteo keyless API and pure formatting.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | In [src/calendar_events/sources/f1.py](../src/calendar_events/sources/f1.py), capture `Circuit.Location.lat` and `Circuit.Location.long` during `_parse` and retain the `Qualifying`/`Sprint` session datetimes for the race event even when `include_sessions` is `false`. | | |
| TASK-008 | Add `WEATHER_API = "https://api.open-meteo.com/v1/forecast"` and `F1Source._fetch_weather(self, lat: float, lon: float, date: str) -> dict | None` that requests `daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code`, `start_date=date`, `end_date=date`, `timezone=UTC`; return `None` on any error or empty result. | | |
| TASK-009 | Add pure helper `F1Source._weather_summary(self, daily: dict | None) -> str | None` mapping WMO `weather_code` to a short label and formatting `"Weather: <label>, <min>–<max>°C, precip <p>%"`; return `None` when input is `None`. | | |
| TASK-010 | Add pure helper `F1Source._build_description(self, circuit: str, location: str, race_dt, qualifying_dt, sprint_dt, weather_line: str | None, url: str) -> str` composing circuit/location, race/qualifying/sprint UTC times, optional weather line, and the Wikipedia URL. | | |
| TASK-011 | In `F1Source._parse`, when `enrichment.weather` is enabled fetch weather (inside `try/except`, warn + `None` on failure) and set the race `Event.description` via `_build_description`; session events keep a minimal description. | | |
| TASK-012 | Guard weather fetches to races within the Open-Meteo horizon (≈16 days): if `race_date - now > 16 days`, skip the fetch and omit the weather line (REQ-005) to avoid pointless requests. | | |

### Implementation Phase 3

- GOAL-003: Add configuration plumbing and wire enrichment settings through the pipeline to the sources.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Add an `EnrichmentConfig` dataclass to [src/calendar_events/config.py](../src/calendar_events/config.py) with fields per REQ-007 and parse the `enrichment:` block in `load_config` with the specified defaults. | | |
| TASK-014 | Add `enrichment: EnrichmentConfig` to the `Config` dataclass and expose it to sources: extend `pipeline.run` / `get_source` wiring so each source receives the enrichment settings (e.g., merged into `options` under key `enrichment`). | | |
| TASK-015 | Document the full `enrichment` block with inline comments and defaults in [config.example.yaml](../config.example.yaml). | | |

### Implementation Phase 4

- GOAL-004: Add an OPTIONAL local-LLM polishing layer (Ollama / llama.cpp) that rewrites deterministic facts into prose, disabled by default, with deterministic fallback.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016 | Create package `src/calendar_events/enrich/__init__.py` and module `src/calendar_events/enrich/llm.py` exposing `polish(facts: str, config: EnrichmentConfig) -> str`. | | |
| TASK-017 | In `llm.py`, implement `_ollama(facts, config)` POSTing to `f"{llm_endpoint}/api/generate"` with JSON `{"model": llm_model, "prompt": <template+facts>, "stream": false}`, 15s timeout, returning `response.json()["response"].strip()`. | | |
| TASK-018 | In `llm.py`, implement `_llamacpp(facts, config)` POSTing to `f"{llm_endpoint}/completion"` with JSON `{"prompt": <template+facts>, "n_predict": 200}`, returning the completion text. | | |
| TASK-019 | In `llm.py`, `polish()` MUST select the backend by `config.llm_backend`, wrap the call in `try/except`, and return the ORIGINAL `facts` unchanged on any error (REQ-009); define a constant `PROMPT_TEMPLATE` instructing the model to write a concise calendar description from the provided facts without inventing information. | | |
| TASK-020 | In both sources, after assembling the deterministic description, when `enrichment.use_llm` is `true` call `enrich.llm.polish(description, enrichment)` and use its return value as `Event.description`. Import `enrich.llm` lazily so it is not loaded when `use_llm` is `false` (REQ-008). | | |

### Implementation Phase 5

- GOAL-005: Add offline tests and verify end-to-end enrichment against live sources.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | Add fixture `tests/fixtures/ufc_event_page.html` (trimmed real event page with ≥3 bouts incl. main event) and `tests/test_ufc_enrichment.py` asserting `_parse_fight_card` returns ordered `"A vs B - Weight"` strings and `_build_description` includes them; no network I/O. | | |
| TASK-022 | Add fixture `tests/fixtures/open_meteo.json` and `tests/test_f1_enrichment.py` asserting `_weather_summary` formats correctly, returns `None` for `None` input, and `_build_description` includes circuit/qualifying/weather lines; no network I/O. | | |
| TASK-023 | Add `tests/test_llm.py` asserting `polish()` returns the original facts unchanged when the backend call is monkeypatched to raise, and that `_ollama`/`_llamacpp` build the correct request payloads (monkeypatched `requests.post`); no network I/O. | | |
| TASK-024 | Run `pytest -q` and confirm all tests pass with zero network access (CON-002). | | |
| TASK-025 | Execute `python main.py --dry-run --no-email --source ufc --source f1`, open one generated `.ics` per source, and confirm the `DESCRIPTION` contains the fight card (UFC) and track/qualifying/weather (F1). Record results here. | | |
| TASK-026 | Update [TODO.md](../TODO.md) Milestone 2 "Rich event details" item to reference this plan and check it off when complete. | | |

## 3. Alternatives

- **ALT-001**: Parse the UFC fight card from the events listing page instead of each event detail page — rejected because the listing page shows only the headliners, not the full card.
- **ALT-002**: Use a paid sports-data API (e.g., a UFC/F1 stats provider) for structured cards and weather — rejected to honor CON-001 (no new/paid dependencies) and keep the tool free.
- **ALT-003**: Use a weather provider requiring an API key (OpenWeatherMap) — rejected in favor of keyless Open-Meteo to avoid secret management for a non-critical field.
- **ALT-004**: Always run the LLM to generate descriptions — rejected; deterministic formatting is reliable, testable, offline, and free, so the LLM is opt-in polish only.
- **ALT-005**: Call the LLM once per run over all events in a batch prompt — deferred; per-event polishing is simpler and keeps failures isolated. Batch mode can be a later optimization.

## 4. Dependencies

- **DEP-001**: `requests` (already in [requirements.txt](../requirements.txt)) — UFC detail pages, Open-Meteo, and local LLM HTTP calls.
- **DEP-002**: `beautifulsoup4` (already present) — parsing UFC event detail pages.
- **DEP-003**: Open-Meteo forecast API availability (`https://api.open-meteo.com/v1/forecast`), keyless (external service).
- **DEP-004**: Ergast/Jolpica payload continuing to include `Circuit.Location.lat`/`long` (verified present in Milestone 1 data).
- **DEP-005**: OPTIONAL — a local Ollama server (`http://localhost:11434`) or llama.cpp server, only when `enrichment.use_llm` is `true`.
- **DEP-006**: Milestone 1 completion — working `f1` and `ufc` sources ([plan/feature-mvp-sources-1.md](feature-mvp-sources-1.md)).

## 5. Files

- **FILE-001**: [src/calendar_events/sources/ufc.py](../src/calendar_events/sources/ufc.py) — event-page fetch, fight-card parse, and UFC description builder.
- **FILE-002**: [src/calendar_events/sources/f1.py](../src/calendar_events/sources/f1.py) — lat/long capture, weather fetch/summary, and F1 description builder.
- **FILE-003**: [src/calendar_events/config.py](../src/calendar_events/config.py) — `EnrichmentConfig` and `Config.enrichment` parsing.
- **FILE-004**: [src/calendar_events/pipeline.py](../src/calendar_events/pipeline.py) — pass enrichment settings to sources.
- **FILE-005**: `src/calendar_events/enrich/__init__.py` — new subpackage init.
- **FILE-006**: `src/calendar_events/enrich/llm.py` — optional local-LLM polishing interface (`polish`, `_ollama`, `_llamacpp`).
- **FILE-007**: [config.example.yaml](../config.example.yaml) — documented `enrichment` block.
- **FILE-008**: `tests/fixtures/ufc_event_page.html` — UFC detail-page fixture.
- **FILE-009**: `tests/fixtures/open_meteo.json` — weather API fixture.
- **FILE-010**: `tests/test_ufc_enrichment.py` — UFC card parsing/description tests.
- **FILE-011**: `tests/test_f1_enrichment.py` — F1 weather/description tests.
- **FILE-012**: `tests/test_llm.py` — LLM interface and fallback tests.
- **FILE-013**: [TODO.md](../TODO.md) — reference this plan and check off the rich-details item.

## 6. Testing

- **TEST-001**: `UFCSource._parse_fight_card` on `ufc_event_page.html` returns bout strings in card order, each matching `^.+ vs .+ - .+$`, with the main event first.
- **TEST-002**: `UFCSource._parse_fight_card` skips a bout row missing both corner names without raising.
- **TEST-003**: `UFCSource._build_description` includes every bout line plus the venue line.
- **TEST-004**: `F1Source._weather_summary` formats a known `open_meteo.json` daily block into `"Weather: <label>, <min>–<max>°C, precip <p>%"` and returns `None` for `None`.
- **TEST-005**: `F1Source._build_description` includes circuit, `locality, country`, race time, qualifying time, and (when provided) the weather line.
- **TEST-006**: F1 enrichment omits the weather line and does not raise when `_fetch_weather` returns `None` (beyond-horizon or error).
- **TEST-007**: `enrich.llm.polish` returns the input facts unchanged when the monkeypatched backend raises (fallback path).
- **TEST-008**: `enrich.llm._ollama` and `_llamacpp` construct the documented request payloads (monkeypatched `requests.post`, asserting URL and JSON body).
- **TEST-009**: `load_config` applies `enrichment` defaults when the block is absent and overrides them when present (CON-004).
- **TEST-010**: Full `pytest -q` passes with no network access (CON-002).

## 7. Risks & Assumptions

- **RISK-001**: UFC event-page markup changes and breaks fight-card parsing — mitigated by isolating parsing in `_parse_fight_card`, per-row skipping, fixture tests, and graceful fallback (REQ-006).
- **RISK-002**: Fetching a detail page per event increases run time and request volume — mitigated by rate limiting (SEC-002), bounding fetches to in-window events, and making `fight_card` toggleable.
- **RISK-003**: Open-Meteo only forecasts ≈16 days ahead, so most future races lack weather — accepted; weather is best-effort and omitted otherwise (REQ-005, TASK-012).
- **RISK-004**: Local LLM output may hallucinate or reformat facts incorrectly — mitigated by a constrained prompt (TASK-019), opt-in default-off, and deterministic fallback that is always computed (GUD-002).
- **RISK-005**: WMO weather-code-to-label mapping may be incomplete — mitigated by a default "mixed conditions" label for unknown codes.
- **ASSUMPTION-001**: UFC event detail pages list all announced bouts with corner names and weight class in a parseable structure.
- **ASSUMPTION-002**: The local LLM backend, when enabled, follows the documented Ollama (`/api/generate`) or llama.cpp (`/completion`) HTTP contract.
- **ASSUMPTION-003**: A ~2-hour default event duration and UTC session times from Milestone 1 remain acceptable; this plan changes only descriptions, not timing.

## 8. Related Specifications / Further Reading

- [plan/feature-mvp-sources-1.md](feature-mvp-sources-1.md) — Milestone 1 sources (prerequisite)
- [plan/feature-robustness-2.md](feature-robustness-2.md) — Milestone 2 (shared HTTP layer this plan can later adopt)
- [README.md](../README.md) — architecture and configuration
- Open-Meteo forecast API: https://open-meteo.com/en/docs
- WMO weather interpretation codes: https://open-meteo.com/en/docs#weathervariables
- Ollama REST API (`/api/generate`): https://github.com/ollama/ollama/blob/main/docs/api.md
- llama.cpp server API (`/completion`): https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
