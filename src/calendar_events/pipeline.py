"""Ties the flow together: scrape sources, dedup, build .ics, email, record."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from .config import Config
from .email_sender import EmailSender
from .ics import write_ics
from .models import Event
from .sources import get_source
from .store import SentStore

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    fetched: int = 0
    new: int = 0
    updated: int = 0
    sent: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def run(
    config: Config,
    source_names: list[str] | None = None,
    *,
    dry_run: bool = False,
    no_email: bool = False,
    force: bool = False,
    look_ahead_days: int | None = None,
    limit: int | None = None,
) -> RunResult:
    """Execute the pipeline once.

    Args:
        config: Loaded configuration.
        source_names: Subset of sources to run; defaults to config.sources.
        dry_run: Do not send email or update the store; just report.
        no_email: Build .ics files but do not send email.
        force: Ignore the dedup store and process all fetched events.
        look_ahead_days: Override config.look_ahead_days for this run.
        limit: Process at most this many events (None means no cap).
    """
    result = RunResult()
    names = source_names or config.sources
    days = look_ahead_days if look_ahead_days is not None else config.look_ahead_days
    store = SentStore(config.store_file)
    sender = EmailSender(config.email)
    cutoff = datetime.now(timezone.utc) + timedelta(days=days)

    all_events: list[Event] = []
    for name in names:
        try:
            options = {**config.options_for(name), "enrichment": config.enrichment}
            source = get_source(name, options)
            events = source.fetch(days)
            logger.info("Source '%s' returned %d event(s)", name, len(events))
            all_events.extend(events)
        except Exception as exc:  # keep going if one source fails
            msg = f"source '{name}' failed: {exc}"
            logger.exception(msg)
            result.errors.append(msg)

    result.fetched = len(all_events)

    processed = 0
    for event in all_events:
        if limit is not None and processed >= limit:
            break
        try:
            if event.start > cutoff:
                continue
            status = store.status(event)
            if not force and status == "unchanged":
                continue
            if status == "updated":
                result.updated += 1
            else:
                result.new += 1
            processed += 1

            # Apply default reminders unless the source provided its own.
            event_out = (
                event if event.alarms else replace(event, alarms=config.default_alarms)
            )
            sequence = store.sequence_for(event)
            ics_path = write_ics(
                event_out,
                config.data_dir,
                sequence=sequence,
                method=config.email.invite_method,
                color=config.event_color,
            )
            logger.info("Prepared invite: %s -> %s", event.title, ics_path.name)

            if dry_run:
                continue

            if not no_email:
                sender.send(event_out, ics_path)
                result.sent += 1

            store.add(event_out)
        except Exception as exc:  # isolate per-event failures
            msg = f"failed to process '{event.title}': {exc}"
            logger.exception(msg)
            result.errors.append(msg)
            continue

    if not dry_run:
        store.save()

    return result
