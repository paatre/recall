import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
from rich.console import Console

from recall.collectors.shell import ShellCollector
from tests.utils import make_dt, strip_ansi


@pytest.fixture
def collector():
    """Fixture for the Shell Collector instance."""
    return ShellCollector(config={})


@pytest.fixture
def capture_rich_text(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Fixture to capture the plain text output from rich.console.print().

    Uses monkeypatching the global 'console' object in the shell collector module.
    Returns a StringIO buffer object containing the captured text.
    """
    output_buffer = io.StringIO()
    capturing_console = Console(
        file=output_buffer,
        force_terminal=True,
        width=80,
        record=True,
    )
    monkeypatch.setattr("recall.collectors.shell.console", capturing_console)
    return output_buffer


def test_name(collector: ShellCollector):
    """Test that the collector's name is correct."""
    assert collector.name() == "Shell"


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


@pytest.mark.asyncio
async def test_collect_no_log_file(
    fs: FakeFilesystem,
    collector: ShellCollector,
    capture_rich_text: io.StringIO,
):
    """Empty list is returned and text printed when the log file does not exist."""
    expected_path = collector.log_file_path

    events = await collector.collect(make_dt(0), make_dt(60))

    output = strip_ansi(capture_rich_text.getvalue()).strip()
    expected_message = f"Shell history log file {expected_path} not found."
    assert expected_message == output
    assert events == []
    assert fs.exists(expected_path) is False


@pytest.mark.asyncio
@patch("recall.collectors.shell.Path.open")
@patch("recall.collectors.shell.Path.home")
async def test_collect_os_error(
    mock_home: MagicMock,
    mock_open: MagicMock,
    collector: ShellCollector,
):
    """Test that an empty list is returned on OSError."""
    mock_home.return_value.joinpath.return_value.exists.return_value = True
    mock_open.side_effect = OSError
    events = await collector.collect(make_dt(0), make_dt(60))
    assert events == []


@pytest.mark.asyncio
async def test_collect_skips_invalid_lines(
    fs: FakeFilesystem,
    collector: ShellCollector,
):
    """Test that invalid lines in the log file are skipped."""
    log_path = collector.log_file_path
    log_content = [
        "this is not a valid line",
        "2025-01-01T09:00:00Z valid_command",
    ]
    fs.create_file(log_path, contents="\n".join(log_content))

    start_time, end_time = make_dt(0), make_dt(60)
    events = await collector.collect(start_time, end_time)

    assert len(events) == 1
    assert events[0].description == "valid_command"


@pytest.mark.asyncio
async def test_collect_filters_by_time(
    fs: FakeFilesystem,
    collector: ShellCollector,
):
    """Test that events are correctly filtered by the given time range."""
    log_path = collector.log_file_path
    log_content = [
        "2025-01-01T08:59:59Z command_before",
        "2025-01-01T09:00:00Z command_within",
        "2025-01-01T09:00:01Z another_within",
        "2025-01-01T10:00:01Z command_after",
    ]
    fs.create_file(log_path, contents="\n".join(log_content))

    start_time, end_time = make_dt(0), make_dt(60)
    events = await collector.collect(start_time, end_time)

    assert len(events) == 2
    assert events[0].description == "command_within"
    assert events[1].description == "another_within"
