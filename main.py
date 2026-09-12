"""Entry point: `python main.py`.

Loads .env if python-dotenv is available, then hands off to the CLI. The src/
layout means we add src/ to the path so `calendar_events` is importable without
installation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_dotenv() -> None:
    """Minimal .env loader so SMTP secrets are picked up without extra deps."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


if __name__ == "__main__":
    _load_dotenv()
    from calendar_events.cli import main

    raise SystemExit(main())
