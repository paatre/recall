from pathlib import Path

import pytest

from recall.collectors.base import Event

from .utils import make_dt


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
