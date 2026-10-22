# build-calendar-events

A one-shot Python program that scrapes the web for specific sporting events and
sends you calendar invites (`.ics`) by email so you can drop them straight into
your personal calendar.

It ships with support for **UFC events** and **Formula 1 races**, and is designed
so that new event sources (boxing, Champions League, NFL, etc.) can be added with
minimal effort.

---

## How it works

```
sources (scrape/API)  ──►  dedup store  ──►  .ics builder  ──►  SMTP email
   UFC, F1, ...            (JSON file)        (per event)       (to yourself)
```

1. **Scrape** — Each source fetches upcoming events. Where a public/free API is
   available (e.g. the Ergast/Jolpica API for F1) it is used; otherwise the
   source falls back to HTML scraping.
2. **Dedup** — Every event has a stable ID. Already-sent events are recorded in a
   local JSON store so they are never sent twice.
3. **Build invites** — New events are turned into standards-compliant `.ics`
   calendar files.
4. **Deliver** — The `.ics` files are emailed to you via SMTP as calendar
   attachments.

Today it runs **manually** as a single command. It can also publish a combined,
subscribable calendar **feed** (see [Subscription feed](#subscription-feed)) that
you subscribe to once on your devices and colour on-device.

---

## Requirements

- Python 3.10+
- An SMTP account you can send mail from (e.g. Gmail app password, Fastmail, etc.)

---

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/<you>/build-calendar-events.git
cd build-calendar-events

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your config
cp config.example.yaml config.yaml
cp .env.example .env
# then edit config.yaml and .env with your details
```

---

## Configuration

Configuration is split into two places:

- **`config.yaml`** — non-secret settings: which sources to enable, how far ahead
  to look, output folder, recipient email, SMTP host/port, etc.
- **`.env` / environment variables** — secrets such as your SMTP username and
  password. Environment variables override values in `config.yaml`.

See [config.example.yaml](config.example.yaml) and [.env.example](.env.example)
for the full list of options and documentation.

---

## Usage

Run the full pipeline (scrape → dedup → build → email):

```bash
python main.py
```

Useful flags:

```bash
# See what would be sent without emailing or updating the dedup store
python main.py --dry-run

# Only run specific sources
python main.py --source ufc --source f1

# Write .ics files to disk but do not send email
python main.py --no-email

# Ignore the dedup store and reprocess everything
python main.py --force
```

Run `python main.py --help` for the complete list.

---

## Subscription feed

Instead of emailing one `.ics` per event, you can publish a single **combined
calendar feed** containing the complete set of upcoming F1 + UFC events and
subscribe to it once per device. Apple Calendar colours events by their
**containing calendar**, so a subscribed feed is the reliable way to get a
coloured "Sports" calendar on iPhone (this is the intended fix for BUG-001 —
see [TODO.md](TODO.md)).

Build the feed locally:

```bash
# Write the full upcoming collection to public/sports.ics (see config.yaml)
python main.py feed

# Validate without writing the feed or state
python main.py feed --dry-run

# Authorize publishing even if a source returns no in-window events
python main.py feed --allow-empty
```

The feed **fails closed**: if any enabled source errors, or returns no in-window
events without `--allow-empty`, nothing is written and the command exits
non-zero — so a broken scraper can never silently replace your calendar with a
partial one. Event UIDs and `SEQUENCE` are tracked in `feed_state_file` so a
rescheduled event **updates in place** for subscribers instead of duplicating.

### Hosting the feed (GitHub Pages)

[`.github/workflows/publish-feed.yml`](.github/workflows/publish-feed.yml)
rebuilds and publishes the feed to GitHub Pages monthly (and on demand via
**Run workflow**). One-time setup:

1. Push to a **public** repository (free GitHub Pages requires public repos).
2. **Settings → Pages → Build and deployment → Source: "GitHub Actions"**.
3. Trigger the workflow once (**Actions → Publish sports feed → Run workflow**).

The feed is then served at a stable HTTPS URL:

```
https://<your-user>.github.io/<repo>/sports.ics
```

Durable state (UIDs/`SEQUENCE`) and the published `.ics` are committed to a
dedicated **`feed-state`** branch so updates stay stable across runs; the
workflow serializes runs and never touches the hosted feed when a build fails.

> **Heads up:** scheduled GitHub Actions are auto-disabled after 60 days of
> repository inactivity and can be delayed under load — re-enable them from the
> Actions tab if a monthly run is skipped.

### Subscribing on iPhone

On iOS, **Calendar → Calendars → Add Calendar → Add Subscription Calendar**,
paste the HTTPS `sports.ics` URL, then pick a colour. The calendar is read-only;
corrections flow from the feed rather than from editing events on the device.
(A `webcal://` link can open the subscription sheet directly, but the canonical
address is the HTTPS URL.) After verifying the subscription, remove or hide any
old sports events you previously imported — the feed cannot delete copies that
already live in your other calendars.

Google Calendar and Outlook can also subscribe by URL (not one-time *import*),
but refresh timing is controlled by each client and is not certified here.

### Running elsewhere (cron)

[`docs/cron-example.sh`](docs/cron-example.sh) shows how to regenerate the feed
on another always-on machine on a schedule. Note it only *generates* the file;
hosting it over HTTPS is left to you (GitHub Actions → Pages is the supported
end-to-end path).

---

## Project structure

```
build-calendar-events/
├── main.py                     # entry point (thin wrapper around the CLI)
├── config.example.yaml         # documented config template
├── .env.example                # secret env-var template
├── requirements.txt
├── .github/workflows/          # publish-feed.yml (monthly Pages publish)
├── docs/                       # cron-example.sh, agent/domain docs
├── data/                       # dedup store + feed state + .ics output (gitignored)
├── public/                     # generated feed (public/sports.ics)
├── src/
│   └── calendar_events/
│       ├── cli.py              # argument parsing & orchestration (email + feed)
│       ├── config.py           # load/merge config.yaml + env vars
│       ├── models.py           # Event data model
│       ├── ics.py              # build .ics calendar files (single + feed)
│       ├── email_sender.py     # SMTP delivery
│       ├── store.py            # JSON dedup store (email ledger)
│       ├── feed_store.py       # durable feed revision state (UIDs/SEQUENCE)
│       ├── feed.py             # build + validate the subscription feed
│       ├── pipeline.py         # ties the email flow together
│       └── sources/
│           ├── base.py         # Source base class + registry
│           ├── ufc.py          # UFC events source
│           └── f1.py           # Formula 1 source
└── tests/                      # unit tests
```

---

## Adding a new event source

1. Create a new file in `src/calendar_events/sources/`, e.g. `boxing.py`.
2. Subclass `Source` from `sources/base.py` and implement `fetch()` returning a
   list of `Event` objects.
3. Register it so the CLI can discover it (see the registry in
   [src/calendar_events/sources/base.py](src/calendar_events/sources/base.py)).
4. Enable it in `config.yaml`.

That's it — dedup, `.ics` generation, and emailing are handled for you.

---

## Roadmap

See [TODO.md](TODO.md) for the detailed, staged plan (MVP → automation →
additional sports).

---

## Disclaimer

This project scrapes publicly available information. Respect each site's
`robots.txt` and terms of service, use reasonable request rates, and prefer
official APIs where they exist.
