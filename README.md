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

Today it runs **manually** as a single command. It is structured so it can later
be run on a schedule (e.g. monthly via cron / GitHub Actions) to automatically
pick up only newly announced events.

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

## Project structure

```
build-calendar-events/
├── main.py                     # entry point (thin wrapper around the CLI)
├── config.example.yaml         # documented config template
├── .env.example                # secret env-var template
├── requirements.txt
├── data/                       # dedup store + generated .ics files (gitignored)
├── src/
│   └── calendar_events/
│       ├── cli.py              # argument parsing & orchestration
│       ├── config.py           # load/merge config.yaml + env vars
│       ├── models.py           # Event data model
│       ├── ics.py              # build .ics calendar files
│       ├── email_sender.py     # SMTP delivery
│       ├── store.py            # JSON dedup store
│       ├── pipeline.py         # ties the whole flow together
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
