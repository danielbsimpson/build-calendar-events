"""Test suite for build-calendar-events.

Ensures the `calendar_events` package (under src/) is importable during tests.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
