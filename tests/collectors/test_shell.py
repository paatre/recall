from datetime import datetime, timezone

import pytest

from recall.collectors.shell import ShellCollector


@pytest.fixture
def collector():
    """Fixture for the Shell Collector instance."""
    return ShellCollector()


def test_parse_line_valid_iso_line(collector: ShellCollector):
    """Test a correctly formatted line with a timezone offset."""
    line = "2025-09-28T10:30:15+03:00 git status"

    result = collector._parse_line(line)
    assert result is not None

    timestamp, command = result
    assert timestamp.tzinfo is not None
    assert command == "git status"


def test_parse_line_with_utc_time(collector: ShellCollector):
    """Test a correctly formatted line with UTC time."""
    line = "2025-10-08T14:45:00Z uv build"
    expected_utc = datetime(2025, 10, 8, 14, 45, 0, tzinfo=timezone.utc)

    result = collector._parse_line(line)
    assert result is not None

    timestamp, command = result
    assert timestamp.astimezone(timezone.utc) == expected_utc
    assert command == "uv build"


def test_parse_line_invalid_timestamp_format(collector: ShellCollector):
    """Test a line with an invalid or ambiguous timestamp format (e.g., missing T)."""
    line = "2025-09-28TXX:30:15+03:00 invalid command"
    assert collector._parse_line(line) is None


def test_parse_line_missing_command_part(collector: ShellCollector):
    """Test a line that contains only the timestamp (missing the second part)."""
    line = "2025-09-28T10:30:15+03:00"
    assert collector._parse_line(line) is None


def test_parse_line_command_with_internal_quotes_and_whitespace(
    collector: ShellCollector,
):
    """Test a command that contains extra whitespace is handled correctly."""
    line = "2025-09-28T10:30:15+03:00  docker-compose up --build -d "
    result = collector._parse_line(line)
    assert result is not None

    _, command = result
    assert command == "docker-compose up --build -d"
