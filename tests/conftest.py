import time
from pathlib import Path

import pytest

from recall.collectors.base import Event

from .utils import make_dt


@pytest.fixture(autouse=True)
def mock_utc_timezone(monkeypatch: pytest.MonkeyPatch):
    """Force the test environment to use UTC timezone to ensure determinism."""
    monkeypatch.setenv("TZ", "UTC")
    if hasattr(time, "tzset"):
        time.tzset()
    yield
    # No need to revert TZ explicitly, monkeypatch handles it.
    # However we need to tzset again to pick up the reverted TZ
    if hasattr(time, "tzset"):
        time.tzset()


@pytest.fixture
def event() -> Event:
    """Create a sample Firefox activity event."""
    return Event(
        timestamp=make_dt(10),
        source="Firefox",
        description="Example.com",
        url="https://example.com",
    )


@pytest.fixture
def mock_temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock Path.home() to point to a temporary directory for file access tests.

    This is essential for testing ShellCollector and FirefoxCollector file lookups.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path
