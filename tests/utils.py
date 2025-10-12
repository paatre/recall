import re
from datetime import datetime, timedelta, timezone

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return ANSI_ESCAPE.sub("", text)


def make_dt(minutes: int, seconds: int = 0) -> datetime:
    """Create a timezone-aware datetime object relative to a base time."""
    base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
    return base_time + timedelta(minutes=minutes, seconds=seconds)
