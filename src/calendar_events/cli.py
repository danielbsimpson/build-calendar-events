"""Command-line interface for build-calendar-events."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
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
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
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
    )

    print(
        f"Fetched {result.fetched} event(s); "
        f"{result.new} new; "
        f"{result.sent} emailed."
    )
    if result.errors:
        print(f"{len(result.errors)} error(s):", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
