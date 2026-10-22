"""Command-line interface for build-calendar-events."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .config import load_config
from .feed import FeedError, FeedResult, build_feed
from .pipeline import run
from .sources import available_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build-calendar-events",
        description="Scrape sporting events and email yourself calendar invites.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML config file (default: config.yaml).",
    )
    parser.add_argument(
        "--source",
        dest="sources",
        action="append",
        metavar="NAME",
        help=(
            "Only run this source (repeatable). "
            f"Available: {', '.join(available_sources()) or 'none'}."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be sent without emailing or updating the store.",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Build .ics files but do not send email.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the dedup store and reprocess all fetched events.",
    )
    parser.add_argument(
        "--look-ahead-days",
        type=int,
        default=None,
        metavar="N",
        help="Override the look-ahead window (days) from the config for this run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N events this run (handy for a first test send).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def build_feed_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build-calendar-events feed",
        description="Build and publish the combined subscription calendar feed.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML config file (default: config.yaml).",
    )
    parser.add_argument(
        "--source",
        dest="sources",
        action="append",
        metavar="NAME",
        help=(
            "Only include this source (repeatable). "
            f"Available: {', '.join(available_sources()) or 'none'}."
        ),
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Authorize publishing even when a source returns no in-window events.",
    )
    parser.add_argument(
        "--look-ahead-days",
        type=int,
        default=None,
        metavar="N",
        help="Override the look-ahead window (days) from the config for this run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate the feed without writing the feed or state.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def email_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    result = run(
        config,
        source_names=args.sources,
        dry_run=args.dry_run,
        no_email=args.no_email,
        force=args.force,
        look_ahead_days=args.look_ahead_days,
        limit=args.limit,
    )

    print(
        f"Fetched {result.fetched} event(s); "
        f"{result.new} new; "
        f"{result.updated} updated; "
        f"{result.sent} emailed."
    )
    if result.errors:
        print(f"{len(result.errors)} error(s):", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


def _diff_summary(result: FeedResult) -> str:
    """One-line counts of the diff against the previously published feed."""
    return (
        f"added {len(result.added)}, changed {len(result.changed)}, "
        f"unchanged {len(result.unchanged)}, removed {len(result.removed)}"
    )


def _console_summary(result: FeedResult, *, dry_run: bool) -> list[str]:
    counts = ", ".join(f"{name}={n}" for name, n in result.sources.items())
    verb = "Would publish" if dry_run else "Published"
    return [f"{verb} {result.total} event(s) [{counts}]", f"  {_diff_summary(result)}"]


def _write_step_summary(
    *,
    outcome: str,
    result: FeedResult | None = None,
    published_to: str | None = None,
    error: str | None = None,
) -> None:
    """Append a run summary to the GitHub Actions step summary, if present."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["### Sports feed run", "", f"- Outcome: {outcome}"]
    if error:
        lines.append(f"- Error: {error}")
    if result is not None:
        counts = " ".join(f"`{name}`={n}" for name, n in result.sources.items())
        lines.append(f"- Events in feed: **{result.total}** ({counts})")
        lines.append(f"- {_diff_summary(result)}")
    if published_to:
        lines.append(f"- Feed file: `{published_to}`")
    lines.append("")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def feed_main(argv: list[str] | None = None) -> int:
    args = build_feed_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    try:
        result = build_feed(
            config,
            source_names=args.sources,
            allow_empty=args.allow_empty,
            look_ahead_days=args.look_ahead_days,
        )
    except FeedError as exc:
        print(f"Feed not published: {exc}", file=sys.stderr)
        _write_step_summary(outcome="not published — build failed", error=str(exc))
        return 1

    published_to: str | None = None
    if not args.dry_run:
        feed_path = Path(config.feed_file)
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        # newline="" keeps the serializer's CRLF intact (Windows adds \r\r\n).
        feed_path.write_text(result.ics, encoding="utf-8", newline="")
        if result.state is not None:
            result.state.save()
        published_to = str(feed_path)

    for line in _console_summary(result, dry_run=args.dry_run):
        print(line)
    _write_step_summary(
        outcome="dry run (nothing written)" if args.dry_run else "published",
        result=result,
        published_to=published_to,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "feed":
        return feed_main(argv[1:])
    return email_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
