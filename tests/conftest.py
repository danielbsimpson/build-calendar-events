"""Shared pytest fixtures and path setup."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from calendar_events.models import Event  # noqa: E402


@pytest.fixture
def sample_event() -> Event:
    start = datetime.now(timezone.utc) + timedelta(days=7)
    return Event(
        source="test",
        title="Test Event",
        start=start,
        end=start + timedelta(hours=3),
        location="Somewhere",
        description="A test event.",
        url="https://example.com/event",
        external_id="evt-123",
    )
