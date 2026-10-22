"""Build the subscription feed: fetch, validate, diff, and render.

This is the feed counterpart to :mod:`calendar_events.pipeline`. Where the email
pipeline isolates per-source failures and emails discrete new events, the feed
publishes the *complete* upcoming collection as one calendar and fails closed:
if any enabled source errors or returns nothing unexpectedly, the whole run is
rejected so the last-good feed stays hosted untouched.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from .config import Config
from .feed_store import FeedState
from .ics import build_feed_calendar, serialize_calendar
from .models import Event
from .sources import get_source

logger = logging.getLogger(__name__)


class FeedError(Exception):
    """Base class for failures that must prevent publication."""


class SourceFetchError(FeedError):
    """A source failed to fetch, so the collection cannot be trusted."""


class EmptySourceError(FeedError):
    """A source returned no events and emptiness was not authorized."""


@dataclass
class FeedResult:
    """Outcome of building a candidate feed.

    ``ics`` is the serialized candidate calendar; it is not yet the last-good
    feed. ``state`` is the updated :class:`FeedState`, prepared but not saved so
    the caller decides whether to persist (e.g. skipped on a dry run).
    """

    total: int = 0
    sources: dict[str, int] = field(default_factory=dict)
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    ics: str = ""
    state: FeedState | None = None


def build_feed(
    config: Config,
    source_names: list[str] | None = None,
    *,
    allow_empty: bool = False,
    look_ahead_days: int | None = None,
) -> FeedResult:
    """Build a validated candidate feed from the enabled sources.

    Raises:
        SourceFetchError: if any enabled source raises while fetching.
        EmptySourceError: if a source returns no events and ``allow_empty`` is
            False.
    """
    names = source_names or config.sources
    days = look_ahead_days if look_ahead_days is not None else config.look_ahead_days
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)

    result = FeedResult()
    collection: list[Event] = []
    for name in names:
        try:
            options = {**config.options_for(name), "enrichment": config.enrichment}
            source = get_source(name, options)
            events = source.fetch(days)
        except Exception as exc:  # fail closed: do not publish a partial feed
            raise SourceFetchError(f"source '{name}' failed: {exc}") from exc

        in_window = [
            e for e in events if e.start <= cutoff and e.resolved_end >= now
        ]
        logger.info(
            "Source '%s' returned %d event(s), %d in window",
            name,
            len(events),
            len(in_window),
        )
        if not in_window and not allow_empty:
            raise EmptySourceError(
                f"source '{name}' returned no in-window events; refusing to "
                f"publish without explicit authorization"
            )
        result.sources[name] = len(in_window)
        collection.extend(in_window)

    collection.sort(key=lambda e: (e.start, e.title))

    state = FeedState(config.feed_state_file)
    sequences: dict[str, int] = {}
    for event in collection:
        status = state.status(event)
        sequences[event.uid] = state.sequence_for(event)
        if status == "new":
            result.added.append(event.uid)
        elif status == "changed":
            result.changed.append(event.uid)
        else:
            result.unchanged.append(event.uid)
    result.removed = sorted(state.removed_uids(collection))

    calendar = build_feed_calendar(
        _with_default_alarms(collection, config.default_alarms),
        sequences=sequences,
        color=config.event_color,
        calendar_name=config.calendar_name,
    )
    result.ics = serialize_calendar(calendar)
    result.total = len(collection)

    state.record_all(collection)
    result.state = state
    return result


def _with_default_alarms(
    events: list[Event], default_alarms: tuple[int, ...]
) -> list[Event]:
    """Apply the configured default reminders to events that have none."""
    return [e if e.alarms else replace(e, alarms=default_alarms) for e in events]
