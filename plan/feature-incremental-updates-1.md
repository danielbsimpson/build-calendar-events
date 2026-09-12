---
goal: Incremental event updates — flag incomplete events and fill them in on re-run
version: 1.0
date_created: 2026-09-12
last_updated: 2026-09-12
owner: build-calendar-events maintainers
status: 'Planned'
tags: [feature, enrichment, dedup, sources]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan adds incremental update behavior to the pipeline. When a source exposes
an event whose headline is not yet announced (only a date) or whose fight card is
not yet listed, the event is flagged as **provisional**. On a later run, once the
source publishes the missing information, the event's meaningful content changes
and the pipeline emits an **update** invite (bumped `SEQUENCE`) instead of a
duplicate. A prerequisite fix decouples the deduplication hash from volatile
enrichment (the daily F1 weather line) so that only meaningful changes trigger an
update, and weather churn no longer produces false updates.

Concrete example: a run in September lists a December UFC card as "TBD vs TBD"
with no bouts (flagged provisional). A run in October, after the card is
announced, detects the new headline and bouts, classifies the event as
`updated`, and re-sends it as a calendar update.

## 1. Requirements & Constraints

- **REQ-001**: An event whose main-event headline is unannounced MUST be flagged as provisional. Detection signal for UFC: the parsed headline contains the token `TBD`.
- **REQ-002**: An event with no fights/bouts listed yet MUST be flagged as provisional. Detection signal for UFC: `_parse_fight_card` returns an empty list.
- **REQ-003**: On re-run, when a previously provisional event gains a headline and/or bouts, the pipeline MUST classify it as `updated` (not `unchanged`, not a new duplicate) and re-send it with an incremented `SEQUENCE`.
- **REQ-004**: The deduplication hash MUST change only for meaningful content changes (title, start, end, location, url, headline, bout list, session schedule). It MUST NOT change due to the F1 weather line or any other best-effort enrichment that varies between runs.
- **REQ-005**: The provisional state MUST be persisted in the dedup store so a run can report which upcoming events are still awaiting information.
- **REQ-006**: The run summary/logging MUST surface provisional events and MUST distinguish "updated because information filled in" from ordinary reschedules where feasible.
- **REQ-007**: F1 events MUST use the same mechanism: an F1 event is provisional when its session schedule (e.g. qualifying/race time) is not yet published by the API.
- **CON-001**: No new third-party runtime dependencies may be added; use only the current stack (`ics`, `beautifulsoup4`, `requests`, stdlib).
- **CON-002**: Unit tests MUST NOT perform network I/O; all source parsing tests use local HTML/JSON fixtures.
- **CON-003**: Changing the hash basis reclassifies every already-stored event as `updated` exactly once on the first run after deployment; this is accepted and MUST be documented.
- **CON-004**: The `Event` dataclass is `frozen=True`; new fields MUST have defaults and be set via `dataclasses.replace`.
- **GUD-001**: Keep network access isolated in `_fetch_raw`/`_fetch_event_page`; keep `_parse`/`_parse_card`/`_parse_fight_card` pure.
- **GUD-002**: Weather and other volatile text remain visible in the event description for the user; they are simply excluded from the hash basis.
- **PAT-001**: Sources declare meaningful content via a dedicated `content_signature` string; the model hashes the signature when present and falls back to `description` for backward compatibility.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Extend the `Event` model with a provisional flag and a meaningful-content signature, and make `content_hash` derive from the signature so volatile enrichment no longer affects dedup.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `src/calendar_events/models.py`, add two fields to `Event`: `provisional: bool = False` and `content_signature: str \| None = None`. Both must have defaults (dataclass is frozen). | | |
| TASK-002 | In `src/calendar_events/models.py`, redefine the `content_hash` property so its basis is `title`, `start.isoformat()`, `resolved_end.isoformat()`, `location or ""`, `url or ""`, and `content_signature if content_signature is not None else (description or "")`. This removes `description` (and thus the weather line) from the hash whenever a signature is provided. | | |
| TASK-003 | Add a `content_hash` docstring note stating the hash intentionally excludes volatile enrichment (weather) and reacts to the `content_signature`. | | |

### Implementation Phase 2

- GOAL-002: Populate provisional detection and `content_signature` in the UFC and F1 sources.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | In `src/calendar_events/sources/ufc.py` `_parse_card`, set `provisional=True` on the returned `Event` when the headline `name` contains the case-insensitive token `TBD`. Pass it via the `Event(...)` constructor. | | |
| TASK-005 | In `src/calendar_events/sources/ufc.py` `_enrich`, compute `bouts` first; when `bouts` is empty, mark the event `provisional=True` via `replace`. When `bouts` is non-empty and the headline is not `TBD`, keep `provisional=False`. | | |
| TASK-006 | In `src/calendar_events/sources/ufc.py` `_enrich`, set `content_signature` to a stable string built from the headline and bout list only, e.g. `"headline=" + name + "|bouts=" + "\n".join(bouts)`. Do not include venue-only or weather text. Apply via the same `replace` call that sets the description. | | |
| TASK-007 | In `src/calendar_events/sources/f1.py` `_enrich_race`, set `content_signature` from stable schedule fields only — circuit name plus `race_dt`, `qualifying_dt`, `sprint_dt` ISO strings — explicitly excluding `weather_line`. Apply via the existing `replace` call. | | |
| TASK-008 | In `src/calendar_events/sources/f1.py` `_parse`/`_enrich_race`, set `provisional=True` when the race time (`race.get("time")`) or qualifying session is absent (schedule not yet published). Default `provisional=False` when the schedule is complete. | | |

### Implementation Phase 3

- GOAL-003: Persist provisional state, ensure update-on-fill-in works end to end, and surface provisional/updated events in output.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | In `src/calendar_events/store.py` `add`, persist `"provisional": event.provisional` in each record and bump the payload `version` to `3` in `save`. Update `_load` to tolerate records with or without `provisional` (default `False`). | | |
| TASK-010 | In `src/calendar_events/store.py`, add a method `provisional_uids() -> set[str]` returning UIDs whose stored record has `provisional == True`, for reporting. | | |
| TASK-011 | Confirm `status` and `sequence_for` require no change (they already compare `content_hash`); add a regression test rather than code. When a provisional event fills in, `content_hash` changes → `status == "updated"` → `sequence_for` increments. | | |
| TASK-012 | In `src/calendar_events/pipeline.py` `RunResult`, add `provisional: int = 0`; in `run`, increment it for each fetched event with `event.provisional`, and log a summary line listing provisional event titles (e.g. `logger.info("Provisional (awaiting details): %s", title)`). | | |
| TASK-013 | In `src/calendar_events/pipeline.py` `run`, when `status == "updated"` and the stored record was `provisional` while the current event is not, log `Prepared UPDATE (details announced): <title>` to distinguish meaningful fill-ins from reschedules. | | |
| TASK-014 | Update the console summary emitted by `main.py`/pipeline to include the provisional count (e.g. `"; N provisional"`). | | |

### Implementation Phase 4

- GOAL-004: Test coverage and documentation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Add tests in `tests/test_ufc_enrichment.py` (or a new `tests/test_ufc_provisional.py`) using a fixture with a `TBD` headline and a fixture with an empty fight card, asserting `event.provisional is True`. Add a fixture with a full card asserting `event.provisional is False` and a populated `content_signature`. | | |
| TASK-016 | Add a test in `tests/test_models.py` asserting `content_hash` is identical for two events that differ only in `description` (simulating changed weather) when both share the same `content_signature`, and differs when `content_signature` differs. | | |
| TASK-017 | Add a test in `tests/test_store.py` asserting the fill-in flow: record a provisional event, then re-classify an event with the same UID but a changed `content_signature` as `"updated"` with `sequence_for` incremented; assert `provisional_uids()` round-trips through save/load. | | |
| TASK-018 | Add a test in `tests/test_f1_enrichment.py` asserting the F1 `content_hash` is stable across two different `weather_line` values (same schedule) and that a provisional F1 event (missing session time) is flagged. | | |
| TASK-019 | Update `TODO.md`: check the relevant Milestone 2 item, and reference this plan; note the one-time reclassification (CON-003). Update `config.example.yaml`/README only if a new user-facing option is introduced (none is expected). | | |
| TASK-020 | Run `pytest -q` and confirm all tests pass; run one live `python main.py --source ufc --dry-run` to confirm provisional logging appears without sending email. | | |

## 3. Alternatives

- **ALT-001**: Exclude the entire `description` from `content_hash` instead of introducing `content_signature`. Rejected: it would also suppress meaningful UFC fight-card changes (which live in the description), defeating the update-on-fill-in requirement.
- **ALT-002**: Stabilize the weather line (e.g. round or cache it) so the description hash stops changing. Rejected: weather legitimately changes as the race approaches; suppressing it is fragile and still couples dedup to enrichment.
- **ALT-003**: Track provisional state and diffs in a separate sidecar file. Rejected: the existing JSON store already keys by UID and is the natural home; a second store adds sync burden.
- **ALT-004**: Always re-send every event on every run (rely on `SEQUENCE` + client dedup). Rejected: produces update-email spam and defeats the purpose of the dedup store.

## 4. Dependencies

- **DEP-001**: Existing `SentStore` JSON dedup store (`src/calendar_events/store.py`), schema versioned (currently `2`, moving to `3`).
- **DEP-002**: Existing UFC scrape selectors (`FIGHT_SELECTOR`, `CORNER_NAME_SELECTOR`, `WEIGHT_CLASS_SELECTOR`) in `src/calendar_events/sources/ufc.py`.
- **DEP-003**: Jolpica/Ergast F1 API schedule fields (`Qualifying`, `Sprint`, race `time`) in `src/calendar_events/sources/f1.py`.
- **DEP-004**: `dataclasses.replace` for updating the frozen `Event`.

## 5. Files

- **FILE-001**: `src/calendar_events/models.py` — add `provisional` and `content_signature` fields; redefine `content_hash`.
- **FILE-002**: `src/calendar_events/sources/ufc.py` — provisional detection (TBD headline, empty card) and `content_signature` from headline + bouts.
- **FILE-003**: `src/calendar_events/sources/f1.py` — provisional detection (missing schedule) and `content_signature` from circuit + session times, excluding weather.
- **FILE-004**: `src/calendar_events/store.py` — persist `provisional`, bump schema to `3`, add `provisional_uids()`.
- **FILE-005**: `src/calendar_events/pipeline.py` — `RunResult.provisional`, provisional/updated logging, summary count.
- **FILE-006**: `tests/test_ufc_provisional.py` (new) and/or `tests/test_ufc_enrichment.py` — provisional detection tests + fixtures.
- **FILE-007**: `tests/test_models.py` — hash stability vs weather; hash sensitivity vs signature.
- **FILE-008**: `tests/test_store.py` — fill-in/update flow and provisional round-trip.
- **FILE-009**: `tests/test_f1_enrichment.py` — F1 weather-stable hash and provisional flag.
- **FILE-010**: `TODO.md` — mark item done, link plan, note one-time reclassification.

## 6. Testing

- **TEST-001**: UFC event with a `TBD` headline is flagged `provisional=True`.
- **TEST-002**: UFC event with an empty fight card is flagged `provisional=True`; with a full card it is `provisional=False` and `content_signature` is populated.
- **TEST-003**: `content_hash` is identical for two events differing only in `description` when `content_signature` is equal (weather-change no-op).
- **TEST-004**: `content_hash` differs when `content_signature` differs (headline/bouts announced).
- **TEST-005**: Store fill-in flow — provisional record then same-UID event with changed signature classifies as `"updated"` and increments `sequence_for`.
- **TEST-006**: `provisional_uids()` survives `save()`/`_load()` round-trip across schema `3`.
- **TEST-007**: F1 `content_hash` is stable across two different `weather_line` values with the same schedule; F1 event missing a session time is flagged provisional.
- **TEST-008**: `pytest -q` passes with no network access; `main.py --source ufc --dry-run` logs provisional events and sends nothing.

## 7. Risks & Assumptions

- **RISK-001**: One-time mass reclassification — the first run after the hash change marks all stored events as `updated`, sending an update for each. Mitigation: document (CON-003); optionally run once with `--no-email` to backfill hashes silently.
- **RISK-002**: UFC markup changes could break `TBD`/empty-card detection. Mitigation: detection is defensive (empty list ⇒ provisional) and covered by fixture tests.
- **RISK-003**: A source that briefly returns a partial/empty card due to a transient fetch error could momentarily flag a complete event as provisional and later "update" it. Mitigation: `_enrich` already falls back to the prior event on fetch failure; only a successful parse yielding zero bouts flags provisional.
- **RISK-004**: F1 `TBD` schedules are rare (Ergast usually has times), so F1 provisional flagging is low-value but harmless.
- **ASSUMPTION-001**: The dedup store remains the single source of truth for prior state and is persisted between runs (see Milestone 3 for CI persistence).
- **ASSUMPTION-002**: `content_signature` is deterministic for identical source data across runs (stable ordering of bouts and sessions).

## 8. Related Specifications / Further Reading

- [plan/feature-event-enrichment-1.md](feature-event-enrichment-1.md) — fight-card, weather, and LLM enrichment this plan builds on.
- [plan/feature-robustness-2.md](feature-robustness-2.md) — dedup-by-content-hash and per-source failure isolation.
- [plan/feature-mvp-sources-1.md](feature-mvp-sources-1.md) — F1/UFC source and end-to-end flow.
- [TODO.md](../TODO.md) — roadmap and known issues (BUG-001, BUG-002).
- RFC 5545 §3.8.7.4 (SEQUENCE) — update semantics for iCalendar entities.
