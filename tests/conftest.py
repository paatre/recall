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
