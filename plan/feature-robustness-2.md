---
goal: Implement Milestone 2 — robustness & polish for network calls, source isolation, rich events, and update-aware dedup
version: 1.0
date_created: 2026-09-12
last_updated: 2026-09-12
owner: build-calendar-events maintainers
status: 'Completed'
tags: [feature, robustness, networking, dedup, ics]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

This plan implements Milestone 2 (Robustness & polish) from [TODO.md](../TODO.md). It hardens all network calls with retry/backoff and timeouts, guarantees a single failing source cannot abort the run, adds polite scraping (robots.txt + rate limiting + user-agent), makes the look-ahead window configurable per invocation, enriches events (alarms/reminders, structured details), introduces content-hash based dedup so rescheduled events emit an update instead of a duplicate, and optionally emits `METHOD:REQUEST` invites. It assumes Milestone 1 (working `f1` and `ufc` sources) is complete; see [plan/feature-mvp-sources-1.md](feature-mvp-sources-1.md).

## 1. Requirements & Constraints

- **REQ-001**: A shared HTTP helper MUST wrap all outbound requests with a configurable timeout (default `15` seconds) and retry with exponential backoff (default `3` attempts, base `1.0` s, factor `2.0`) for transient failures (connection errors and HTTP `429`/`5xx`).
- **REQ-002**: The pipeline in [src/calendar_events/pipeline.py](../src/calendar_events/pipeline.py) MUST continue processing remaining sources and remaining events when any single source or event raises, recording the failure in `RunResult.errors`.
- **REQ-003**: Scraping sources MUST fetch and honor `robots.txt` for the target host and MUST NOT request a disallowed path.
- **REQ-004**: All HTTP requests MUST send a descriptive `User-Agent` header sourced from a single module constant.
- **REQ-005**: Per-host request rate MUST NOT exceed 1 request per `MIN_REQUEST_INTERVAL` seconds (default `2.0`), enforced by a shared throttle.
- **REQ-006**: The look-ahead window MUST be overridable at runtime via a new `--look-ahead-days N` CLI flag in [src/calendar_events/cli.py](../src/calendar_events/cli.py); when omitted, `config.look_ahead_days` is used.
- **REQ-007**: `Event` MUST support optional reminder/alarm offsets (minutes before start) and the `.ics` builder MUST emit a `VALARM` per configured offset.
- **REQ-008**: The `.ics` builder in [src/calendar_events/ics.py](../src/calendar_events/ics.py) MUST populate structured details (location, url, and any `Event.extra` detail lines) into the event description.
- **REQ-009**: The dedup store in [src/calendar_events/store.py](../src/calendar_events/store.py) MUST record a content hash per event UID; when a known UID's content hash changes, the event MUST be treated as an update (re-sent) rather than skipped, and the `.ics` `SEQUENCE` MUST increment.
- **REQ-010**: The `.ics` builder MUST support emitting either `METHOD:PUBLISH` (default) or `METHOD:REQUEST`, selectable via config `email.invite_method`.
- **SEC-001**: Retry/backoff MUST cap total attempts to prevent unbounded request amplification against a failing host.
- **SEC-002**: `robots.txt` fetch failures MUST fail closed for scraping sources (treat as disallowed) unless the fetch returns HTTP `404` (treat as allowed).
- **CON-001**: No new runtime dependencies beyond those already in [requirements.txt](../requirements.txt) (`requests`, `beautifulsoup4`, `PyYAML`, `ics`, `tzdata`); `urllib.robotparser` and `time` from the standard library MUST be used for robots and throttling.
- **CON-002**: Unit tests MUST NOT perform real network I/O; all HTTP behavior MUST be exercised via monkeypatched sessions or fixtures.
- **CON-003**: Python 3.10+ syntax only; use `datetime.timezone.utc` and `zoneinfo` for time handling.
- **CON-004**: Changes MUST be backward compatible with existing `config.yaml` files: all new config keys MUST have defaults.
- **GUD-001**: Network I/O and parsing MUST remain separated (`_fetch_raw` vs pure `_parse`) as established in Milestone 1.
- **GUD-002**: All new tunables (timeouts, retries, intervals, alarms, invite method) MUST be documented in [config.example.yaml](../config.example.yaml).
- **PAT-001**: Introduce a single `http` utility module reused by every source rather than duplicating request logic.
- **PAT-002**: Content hashing MUST be a pure function of user-visible event fields (title, start, end, location, description, url) so identical content yields identical hashes across runs.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Provide a reusable, resilient HTTP layer (timeouts, retry/backoff, user-agent, per-host throttling, robots.txt) and adopt it in both sources.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `src/calendar_events/http.py` defining constants `DEFAULT_TIMEOUT = 15`, `DEFAULT_RETRIES = 3`, `BACKOFF_BASE = 1.0`, `BACKOFF_FACTOR = 2.0`, `MIN_REQUEST_INTERVAL = 2.0`, and `USER_AGENT = "build-calendar-events/0.1 (+https://github.com/<you>/build-calendar-events)"`. | ✅ | 2026-09-12 |
| TASK-002 | In `src/calendar_events/http.py`, implement `get(url: str, *, timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES) -> requests.Response` that sets the `User-Agent` header, retries on `requests.ConnectionError`, `requests.Timeout`, and HTTP status `429`/`>=500` using exponential backoff `BACKOFF_BASE * BACKOFF_FACTOR ** attempt`, and calls `raise_for_status()` on the final response. | ✅ | 2026-09-12 |
| TASK-003 | In `src/calendar_events/http.py`, implement a per-host throttle `_throttle(host: str)` using a module-level `dict[str, float]` of last-request timestamps and `time.monotonic()`/`time.sleep()` to enforce `MIN_REQUEST_INTERVAL`; call it inside `get()` before each attempt. | ✅ | 2026-09-12 |
| TASK-004 | In `src/calendar_events/http.py`, implement `robots_allows(url: str) -> bool` using `urllib.robotparser.RobotFileParser`: fetch `<scheme>://<host>/robots.txt` via `get()`, return `True` on HTTP `404`, `False` on other fetch errors (SEC-002), else return `RobotFileParser.can_fetch(USER_AGENT, url)`. | ✅ | 2026-09-12 |
| TASK-005 | Refactor `F1Source._fetch_raw` in [src/calendar_events/sources/f1.py](../src/calendar_events/sources/f1.py) to call `http.get(...)` instead of `requests.get(...)`; remove the now-duplicated timeout/user-agent constants in favor of the shared module. | ✅ | 2026-09-12 |
| TASK-006 | Refactor `UFCSource._fetch_raw` in [src/calendar_events/sources/ufc.py](../src/calendar_events/sources/ufc.py) to call `http.robots_allows(EVENTS_URL)` first (raising `PermissionError` when disallowed) and then `http.get(EVENTS_URL)`; remove duplicated timeout/user-agent/interval constants. | ✅ | 2026-09-12 |

### Implementation Phase 2

- GOAL-002: Make the pipeline resilient per-event, add a configurable runtime look-ahead window, and improve run reporting.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | In [src/calendar_events/pipeline.py](../src/calendar_events/pipeline.py), wrap the per-event body (build `.ics`, send, record) in a `try/except Exception` that appends `f"failed to process '{event.title}': {exc}"` to `result.errors` and `continue`s, so one bad event cannot abort the loop (REQ-002). | ✅ | 2026-09-12 |
| TASK-008 | Add `run(..., look_ahead_days: int | None = None)` parameter to `run()` in [src/calendar_events/pipeline.py](../src/calendar_events/pipeline.py); use `look_ahead_days if look_ahead_days is not None else config.look_ahead_days` for both `source.fetch(...)` and the `cutoff` computation. | ✅ | 2026-09-12 |
| TASK-009 | Add `--look-ahead-days` (type `int`, default `None`) to the parser in [src/calendar_events/cli.py](../src/calendar_events/cli.py) and pass it through to `run(...)` (REQ-006). | ✅ | 2026-09-12 |
| TASK-010 | Extend `RunResult` in [src/calendar_events/pipeline.py](../src/calendar_events/pipeline.py) with `updated: int = 0`; increment it when an event is re-sent due to a content-hash change (see Phase 4) and include it in the CLI summary line in [src/calendar_events/cli.py](../src/calendar_events/cli.py). | ✅ | 2026-09-12 |

### Implementation Phase 3

- GOAL-003: Enrich events with reminders and structured details, and add configurable invite method to the `.ics` output.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | In [src/calendar_events/models.py](../src/calendar_events/models.py), add field `alarms: tuple[int, ...] = ()` to `Event` (minutes-before-start reminder offsets) and a `details: tuple[str, ...] = ()` field for structured description lines. | ✅ | 2026-09-12 |
| TASK-012 | In [src/calendar_events/ics.py](../src/calendar_events/ics.py) `build_calendar`, append one `ics.alarm.DisplayAlarm(trigger=timedelta(minutes=-m))` per value in `event.alarms` to `ics_event.alarms`. | ✅ | 2026-09-12 |
| TASK-013 | In [src/calendar_events/ics.py](../src/calendar_events/ics.py) `build_calendar`, compose the description from `event.description`, each line in `event.details`, and `event.url`, joined by newlines (REQ-008). | ✅ | 2026-09-12 |
| TASK-014 | Add `invite_method` (default `"PUBLISH"`) to `EmailConfig` in [src/calendar_events/config.py](../src/calendar_events/config.py) (read from `email.invite_method`), pass it into `build_calendar`/`write_ics`, and set `Calendar.method` accordingly (REQ-010). | ✅ | 2026-09-12 |
| TASK-015 | Add default alarm offsets via config: new `Config` field `default_alarms: tuple[int, ...]` (read from `default_alarms:` list, default `(60,)`), applied by the pipeline to events that define none. | ✅ | 2026-09-12 |
| TASK-016 | Document `default_alarms`, `email.invite_method`, `http` timeouts/retries, and `look_ahead_days` runtime override in [config.example.yaml](../config.example.yaml) (GUD-002). | ✅ | 2026-09-12 |

### Implementation Phase 4

- GOAL-004: Implement content-hash dedup so rescheduled events emit an update (incremented SEQUENCE) instead of being skipped or duplicated.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | In [src/calendar_events/models.py](../src/calendar_events/models.py), add property `content_hash` returning a `sha1` hex digest over `title`, `start.isoformat()`, `resolved_end.isoformat()`, `location or ""`, `description or ""`, and `url or ""` (PAT-002). | ✅ | 2026-09-12 |
| TASK-018 | In [src/calendar_events/store.py](../src/calendar_events/store.py), store `content_hash` and a monotonically increasing `sequence` per UID; add methods `status(event) -> Literal["new","updated","unchanged"]` (compares stored vs current hash) and `sequence_for(event) -> int` (returns next sequence for new/updated, current for unchanged). | ✅ | 2026-09-12 |
| TASK-019 | Update `SentStore.add` in [src/calendar_events/store.py](../src/calendar_events/store.py) to persist `content_hash`, `sequence`, and `recorded_at`; bump `sequence` on update. Bump the store schema `version` to `2` and read `version 1` files without a hash as `status == "new"`. | ✅ | 2026-09-12 |
| TASK-020 | In [src/calendar_events/pipeline.py](../src/calendar_events/pipeline.py), replace `store.has(event)` skip logic with `status = store.status(event)`: skip when `unchanged` and not `force`; count `new`/`updated` accordingly; pass the sequence to the `.ics` builder. | ✅ | 2026-09-12 |
| TASK-021 | In [src/calendar_events/ics.py](../src/calendar_events/ics.py), accept a `sequence: int = 0` argument in `build_calendar`/`write_ics` and set `ics_event.sequence = sequence` (REQ-009). | ✅ | 2026-09-12 |

> Implementation note (TASK-014/021): `ics` 0.7.3 exposes `Calendar.method` (used for `METHOD`) but has no native `Event.sequence`. `SEQUENCE` is therefore emitted by appending a raw `ContentLine(name="SEQUENCE", value=...)` to `ics_event.extra`, which serializes to the same `SEQUENCE:` property.

## 3. Alternatives

- **ALT-001**: Adopt `urllib3.util.retry.Retry` with a `requests` `HTTPAdapter` for retries — viable, but a small explicit backoff loop keeps behavior transparent and avoids coupling to `urllib3` internals while honoring CON-001.
- **ALT-002**: Use `tenacity` for retry/backoff — rejected to avoid a new dependency (CON-001).
- **ALT-002b**: Skip robots.txt and rely solely on rate limiting — rejected; honoring robots.txt is a stated Milestone 2 requirement and reduces legal/ToS risk.
- **ALT-003**: Store dedup state in SQLite to support update tracking — deferred to Milestone 5; the JSON store extended with a hash/sequence is sufficient now (CON-004).
- **ALT-004**: Always emit `METHOD:REQUEST` invites — rejected as default because `PUBLISH` imports more predictably across calendar clients; `REQUEST` is offered as opt-in.

## 4. Dependencies

- **DEP-001**: `requests` (already in [requirements.txt](../requirements.txt)) — HTTP transport for the shared `http` module.
- **DEP-002**: `beautifulsoup4` (already present) — used by the UFC scraper.
- **DEP-003**: `ics` (already present) — alarms (`VALARM`), `SEQUENCE`, and `METHOD` support in generated calendars.
- **DEP-004**: Standard library `urllib.robotparser` — robots.txt evaluation (no new dependency).
- **DEP-005**: Standard library `time` — monotonic clock and sleep for throttling/backoff.
- **DEP-006**: Milestone 1 completion — working `f1` and `ufc` sources ([plan/feature-mvp-sources-1.md](feature-mvp-sources-1.md)).

## 5. Files

- **FILE-001**: `src/calendar_events/http.py` — new shared HTTP module (timeouts, retry/backoff, user-agent, throttle, robots).
- **FILE-002**: [src/calendar_events/sources/f1.py](../src/calendar_events/sources/f1.py) — use shared `http.get`.
- **FILE-003**: [src/calendar_events/sources/ufc.py](../src/calendar_events/sources/ufc.py) — use shared `http` with robots check and throttling.
- **FILE-004**: [src/calendar_events/pipeline.py](../src/calendar_events/pipeline.py) — per-event resilience, runtime look-ahead, `updated` counter, content-hash dedup wiring, default alarms.
- **FILE-005**: [src/calendar_events/cli.py](../src/calendar_events/cli.py) — `--look-ahead-days` flag and summary line including `updated`.
- **FILE-006**: [src/calendar_events/models.py](../src/calendar_events/models.py) — `alarms`, `details`, and `content_hash`.
- **FILE-007**: [src/calendar_events/ics.py](../src/calendar_events/ics.py) — `VALARM`, structured description, `SEQUENCE`, `METHOD`.
- **FILE-008**: [src/calendar_events/store.py](../src/calendar_events/store.py) — content hash + sequence, `status()`/`sequence_for()`, schema v2.
- **FILE-009**: [src/calendar_events/config.py](../src/calendar_events/config.py) — `invite_method`, `default_alarms`, and HTTP tunables.
- **FILE-010**: [config.example.yaml](../config.example.yaml) — document all new config keys.
- **FILE-011**: `tests/test_http.py` — new tests for retry/backoff, throttle, and robots handling.
- **FILE-012**: `tests/test_store.py` — extend for update/unchanged status and sequence bumping.
- **FILE-013**: `tests/test_ics.py` — extend for alarms, sequence, and method.
- **FILE-014**: [TODO.md](../TODO.md) — reference this plan and check off completed items.

## 6. Testing

- **TEST-001**: `http.get` retries the configured number of times on `requests.ConnectionError` then raises, with backoff sleeps monkeypatched (no real delay).
- **TEST-002**: `http.get` retries on HTTP `503` then succeeds on a subsequent `200`, returning the successful response.
- **TEST-003**: `http.get` does NOT retry on HTTP `404` and raises via `raise_for_status()`.
- **TEST-004**: `_throttle` enforces `MIN_REQUEST_INTERVAL` between two calls for the same host (monkeypatch `time.monotonic`/`time.sleep` and assert sleep duration).
- **TEST-005**: `robots_allows` returns `True` on `404`, `False` on fetch error (SEC-002), and respects a `Disallow` rule for `USER_AGENT`.
- **TEST-006**: Pipeline continues and records an error when one source raises, still processing the other source's events (REQ-002).
- **TEST-007**: Pipeline continues to the next event when `write_ics`/`send` raises for one event, recording the error.
- **TEST-008**: `--look-ahead-days 7` overrides config; events beyond 7 days are excluded from processing.
- **TEST-009**: `build_calendar` emits one `VALARM`/`BEGIN:VALARM` per alarm offset with a negative trigger.
- **TEST-010**: `build_calendar` sets `SEQUENCE` to the provided sequence and `METHOD` to the configured `invite_method`.
- **TEST-011**: `Event.content_hash` is stable for identical content and differs when `start` changes.
- **TEST-012**: `SentStore.status` returns `new` for unseen UID, `unchanged` for identical content, and `updated` when the content hash changes; `sequence_for` increments only on `updated`.
- **TEST-013**: A `version 1` store file (no hash) is read as `status == "new"` without error (CON-004).
- **TEST-014**: Full `pytest -q` run passes with zero network access (CON-002).

## 7. Risks & Assumptions

- **RISK-001**: Aggressive ret/backoff could amplify load against a struggling host — mitigated by capped attempts (SEC-001) and per-host throttling.
- **RISK-002**: Some calendar clients ignore `VALARM` or handle `SEQUENCE`/`METHOD:REQUEST` inconsistently — mitigated by keeping `PUBLISH` + reminders as defaults and making `REQUEST` opt-in.
- **RISK-003**: Content-hash churn (e.g., description whitespace) could trigger spurious updates — mitigated by hashing a fixed set of normalized fields (PAT-002).
- **RISK-004**: A site's `robots.txt` may disallow the events path, blocking the UFC scraper — mitigated by clear error reporting; a future API/fallback is tracked in later milestones.
- **RISK-005**: Store schema migration (v1 → v2) could mis-read legacy files — mitigated by explicit version handling and TEST-013.
- **ASSUMPTION-001**: `requests.Response.status_code` and exception types are sufficient to classify transient vs permanent failures.
- **ASSUMPTION-002**: The `ics` library version pinned in [requirements.txt](../requirements.txt) supports `DisplayAlarm`, `Event.sequence`, and `Calendar.method`.
- **ASSUMPTION-003**: Per-host in-process throttling is adequate for a single manual run (distributed throttling is out of scope until automation, Milestone 3).

## 8. Related Specifications / Further Reading

- [TODO.md](../TODO.md) — project roadmap and milestone definitions
- [plan/feature-mvp-sources-1.md](feature-mvp-sources-1.md) — Milestone 1 (prerequisite)
- [README.md](../README.md) — architecture and configuration
- iCalendar specification (RFC 5545), `VALARM`/`SEQUENCE`/`METHOD`: https://datatracker.ietf.org/doc/html/rfc5545
- Robots Exclusion Protocol (RFC 9309): https://datatracker.ietf.org/doc/html/rfc9309
- `ics.py` documentation: https://icspy.readthedocs.io/
