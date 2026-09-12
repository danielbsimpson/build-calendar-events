# TODO

Staged roadmap for **build-calendar-events**. Checkboxes track progress; the
scaffolding for everything in Milestone 0 already exists as stubs.

---

## Milestone 0 — Scaffolding (done)

- [x] Repository layout, README, and this TODO
- [x] `requirements.txt` + virtualenv workflow
- [x] Config loading (`config.yaml` + environment variables)
- [x] `Event` data model
- [x] JSON dedup store
- [x] `.ics` builder
- [x] SMTP email sender
- [x] Source base class + registry
- [x] CLI entry point (`main.py`) with `--dry-run`, `--source`, `--no-email`, `--force`

---

## Milestone 1 — MVP (manual run)

> Implementation plan: [plan/feature-mvp-sources-1.md](plan/feature-mvp-sources-1.md)

- [x] Implement the **F1** source using a public API (Ergast / Jolpica)
  - [x] Map race + session times (practice, qualifying, sprint, race) to events
  - [x] Correct timezone handling (store UTC, let the calendar localize)
- [x] Implement the **UFC** source
  - [x] Choose data source (API if available, else HTML scrape of the schedule)
  - [x] Parse event name, date/time, location, main card start
- [x] End-to-end manual run: scrape → dedup → build `.ics` → email to self
- [ ] Verify generated `.ics` imports cleanly into Google Calendar / Apple Calendar / Outlook
  - Apple Calendar / iPhone testing (2026-09-12):
    - [x] Individual `PUBLISH` invites for this weekend's events — UFC (Silva vs Delgado) and F1 (Spanish GP) — imported correctly.
    - [ ] Batch send of all upcoming UFC + F1 events (`PUBLISH`): emails and `.ics` arrived and previewed correctly, but tapping "Done" did **not** add them (a PUBLISH preview needs "Add All to Calendar", not "Done"). **Failed test.**
    - [x] Switched to `METHOD:REQUEST` invitations (Accept/Decline): one future UFC test (Van vs Pantoja 2) accepted and added reliably — but lands in the default calendar and can't be moved to the colored "Sports" calendar (see BUG-001).
- [x] Basic unit tests for `ics`, `store`, and each source's parser (with fixtures)
- [x] Sensible logging and clear console summary of what was sent

---

## Milestone 2 — Robustness & polish

> Implementation plan: [plan/feature-robustness-2.md](plan/feature-robustness-2.md)

- [x] Retry/backoff and timeouts on all network calls
- [x] Graceful handling when a single source fails (don't abort the whole run)
- [x] Respect `robots.txt` and add polite rate limiting / user-agent
- [x] Configurable look-ahead window (e.g. only events in the next N months)
- [x] Rich event details: location, broadcaster, card/session breakdown, reminders/alarms
      — reminders/alarms, UFC fight cards, F1 track/session/weather (+ optional local LLM): [plan/feature-event-enrichment-1.md](plan/feature-event-enrichment-1.md)
- [x] De-dup by stable content hash so rescheduled events send an update, not a duplicate
- [x] Optional: emit `METHOD:REQUEST` invites vs plain `PUBLISH` events
      — REQUEST adds reliably on iOS, but introduces a calendar-color tradeoff (see BUG-001)

---

## Milestone 3 — Automation

- [ ] Publish a subscribable calendar feed (webcal / ICS URL) so events auto-update and the calendar can be colored on-device (resolves BUG-001)
- [ ] Support unattended scheduled runs (monthly)
- [ ] Runner: cron example + GitHub Actions workflow (with secrets)
- [ ] Persist dedup store between runs in CI (artifact/cache or committed data)
- [ ] Notification/summary email even when there is nothing new (optional)
- [ ] Failure alerting (email/log) when a source breaks

---

## Milestone 4 — More sports & sources

- [ ] Championship / big boxing fights
- [ ] UEFA Champions League fixtures
- [ ] NFL games (team filter)
- [ ] Per-source filters (e.g. only a favorite team/fighter)
- [ ] Source-specific config blocks in `config.yaml`

---

## Milestone 5 — Nice-to-haves

- [ ] Direct calendar integrations (Google Calendar API / CalDAV) as delivery options
- [ ] Web/HTML digest of upcoming events
- [ ] Dockerfile for reproducible runs
- [ ] Configurable event categories/colors
- [ ] Move dedup store to SQLite if the JSON file grows unwieldy

---

## Known issues

- **BUG-001 — Event color vs. reliable add on iOS (open, deferred to Milestone 3).**
  Apple Calendar colors events by their **containing calendar**, not by the `.ics`
  `COLOR` property, so per-event color does not work on iPhone.
  - `METHOD:REQUEST` invites add reliably via Accept, but iOS always files accepted
    invites in the **Default** calendar and won't let you move them afterward — so
    they can't live in the colored "Sports" calendar.
  - `METHOD:PUBLISH` events let you choose the calendar (and thus color) via
    "Add All to Calendar", but that flow proved unreliable in testing (tapping
    "Done" silently discards the event).
  - Workaround while deferred: temporarily set the iPhone **Default Calendar** to
    "Sports" before accepting REQUEST invites so they inherit its color.
  - Planned fix: deliver via a **subscribed calendar feed** (webcal / ICS URL)
    whose color is set once on the device, avoiding the per-invite limitation
    entirely (tracked in Milestone 3).

## Known decisions

- **Delivery:** generate `.ics` files and email them via SMTP.
- **Data sources:** prefer public/free APIs, fall back to HTML scraping.
- **Dedup:** simple JSON file in `data/`.
- **Tooling:** `requirements.txt` + `venv`.
- **Config:** `config.yaml` for settings, environment variables for secrets.
