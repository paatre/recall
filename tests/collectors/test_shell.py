import io
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from recall.collectors.shell import ShellCollector
from tests.utils import make_dt, strip_ansi


@pytest.fixture
def collector(tmp_path: Path):
    """Fixture for the Shell Collector instance."""
    log_file = tmp_path / "history.log"
    return ShellCollector(config={"log_file_path": str(log_file)})


@pytest.fixture
def capture_rich_text(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Fixture to capture plain text output from rich.console.print()."""
    output_buffer = io.StringIO()
    capturing_console = Console(file=output_buffer, force_terminal=True, width=80)
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


@pytest.mark.asyncio
async def test_collect_no_log_file(
    collector: ShellCollector,
    capture_rich_text: io.StringIO,
):
    """Test that an empty list is returned and a message printed if the log file is not found."""
    events = await collector.collect(make_dt(0), make_dt(60))
    output = strip_ansi(capture_rich_text.getvalue()).replace("\n", "").strip()
    assert f"Shell history log file {collector.log_file_path} not found." == output
    assert events == []


@pytest.mark.asyncio
@patch("recall.collectors.shell.Path.open")
async def test_collect_os_error(
    mock_open: MagicMock,
    collector: ShellCollector,
):
    """Test that an empty list is returned on OSError."""
    collector.log_file_path.touch()  # Make the file exist
    mock_open.side_effect = OSError
    events = await collector.collect(make_dt(0), make_dt(60))
    assert events == []


@pytest.mark.asyncio
async def test_collect_filters_by_time(collector: ShellCollector):
    """Test that events are correctly filtered by the given time range."""
    log_content = [
        "2025-01-01T08:59:59Z command_before",
        "2025-01-01T09:00:00Z command_within",
        "2025-01-01T09:00:01Z another_within",
        "2025-01-01T10:00:01Z command_after",
    ]
    collector.log_file_path.write_text("\n".join(log_content))

    start_time, end_time = make_dt(0), make_dt(60)
    events = await collector.collect(start_time, end_time)

    assert len(events) == 2
    assert events[0].description == "command_within"
    assert events[1].description == "another_within"