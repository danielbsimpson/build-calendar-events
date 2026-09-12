"""Ties the flow together: scrape sources, dedup, build .ics, email, record."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
) -> RunResult:
    """Execute the pipeline once.

    Args:
        config: Loaded configuration.
        source_names: Subset of sources to run; defaults to config.sources.
        dry_run: Do not send email or update the store; just report.
        no_email: Build .ics files but do not send email.
        force: Ignore the dedup store and process all fetched events.
    """
    result = RunResult()
    names = source_names or config.sources
    store = SentStore(config.store_file)
    sender = EmailSender(config.email)
    cutoff = datetime.now(timezone.utc) + timedelta(days=config.look_ahead_days)

    all_events: list[Event] = []
    for name in names:
        try:
            source = get_source(name, config.options_for(name))
            events = source.fetch(config.look_ahead_days)
            logger.info("Source '%s' returned %d event(s)", name, len(events))
            all_events.extend(events)
        except Exception as exc:  # keep going if one source fails
            msg = f"source '{name}' failed: {exc}"
            logger.exception(msg)
            result.errors.append(msg)

    result.fetched = len(all_events)

    for event in all_events:
        if event.start > cutoff:
            continue
        if not force and store.has(event):
            continue
        result.new += 1

        ics_path = write_ics(event, config.data_dir)
        logger.info("Prepared invite: %s -> %s", event.title, ics_path.name)

        if dry_run:
            continue

        if not no_email:
            try:
                sender.send(event, ics_path)
                result.sent += 1
            except Exception as exc:
                msg = f"failed to email '{event.title}': {exc}"
                logger.exception(msg)
                result.errors.append(msg)
                continue

        store.add(event)

    if not dry_run:
        store.save()

    return result
