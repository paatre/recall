from datetime import datetime, timedelta, timezone


def make_dt(minutes: int, seconds: int = 0) -> datetime:
    """Create a timezone-aware datetime object relative to a base time."""
    base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
    return base_time + timedelta(minutes=minutes, seconds=seconds)

