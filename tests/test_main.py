from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import time_machine

from recall.collectors.base import BaseCollector, Event
from recall.config import ConfigError, ConfigNotFoundError
from recall.main import (
    collect_events,
    get_collector_map,
    init_collectors_from_config,
    is_interactive,
    main,
    parse_arguments,
    print_formatted_event,
)
from tests.utils import make_dt


@pytest.fixture
def mock_load_config():
    """Fixture to mock load_config."""
    with patch("recall.main.load_config") as mock:
        yield mock


@pytest.fixture
def mock_collect_events():
    """Fixture to mock collect_events."""
    with patch("recall.main.collect_events") as mock:
        yield mock


@pytest.fixture
def mock_parse_arguments():
    """Fixture to mock parse_arguments."""
    with patch("recall.main.parse_arguments") as mock:
        mock.return_value = make_dt(0)
        yield mock


@pytest.fixture
def interactive_true():
    """Fixture to mock interactive terminal."""
    with patch("sys.stdout.isatty", return_value=True):
        yield


@pytest.fixture
def interactive_false():
    """Fixture to mock non-interactive terminal."""
    with patch("sys.stdout.isatty", return_value=False):
        yield


@patch("recall.main.argparse.ArgumentParser")
def test_parse_arguments_no_date(mock_arg_parser: MagicMock):
    """Test that the default date (today) is used when none is provided."""
    mock_args = MagicMock()
    mock_args.date = "2025-10-12"
    mock_arg_parser.return_value.parse_args.return_value = mock_args

    with patch("recall.main.datetime") as mock_datetime:
        mock_datetime.now.return_value.astimezone.return_value.tzinfo = timezone.utc
        mock_datetime.strptime.return_value.replace.return_value = "fake_datetime"

        result = parse_arguments()
        assert result == "fake_datetime"
        mock_datetime.strptime.assert_called_with("2025-10-12", "%Y-%m-%d")


@patch("recall.main.argparse.ArgumentParser")
def test_parse_arguments_with_date(mock_arg_parser: MagicMock):
    """Test parsing a specific, valid date."""
    mock_args = MagicMock()
    mock_args.date = "2023-05-20"
    mock_arg_parser.return_value.parse_args.return_value = mock_args

    with patch("recall.main.datetime") as mock_datetime:
        mock_datetime.now.return_value.astimezone.return_value.tzinfo = timezone.utc
        parse_arguments()
        mock_datetime.strptime.assert_called_with("2023-05-20", "%Y-%m-%d")


@pytest.mark.asyncio
@pytest.mark.usefixtures("interactive_false")
@patch("recall.main.sys.argv", ["recall", "invalid-date"])
@patch("recall.main.console")
async def test_main_handles_parse_error(
    mock_console: MagicMock,
    mock_load_config: MagicMock,
):
    """Test that main handles a ValueError from argument parsing."""
    await main()

    expected_msg = "❌ Error: Invalid date format. Please use YYYY-MM-DD."
    mock_console.print.assert_called_with(expected_msg)
    mock_load_config.assert_not_called()


@pytest.mark.asyncio
async def test_main_succeeds_with_valid_config(
    mock_load_config: MagicMock,
    mock_collect_events: MagicMock,
    mock_parse_arguments: MagicMock,
):
    """Test the main function's successful execution with a valid config."""
    mock_load_config.return_value = {
        "sources": [
            {"type": "firefox", "enabled": True, "config": {}},
            {"type": "gitlab", "enabled": False, "config": {}},
        ],
    }
    mock_collect_events.return_value = [Event(make_dt(0), "Test", "Test Event")]

    await main()

    mock_load_config.assert_called_once()
    mock_parse_arguments.assert_called_once()
    mock_collect_events.assert_awaited_once()

    collectors_passed = mock_collect_events.call_args[0][0]
    assert len(collectors_passed) == 1
    assert collectors_passed[0].name() == "Firefox"


@pytest.mark.asyncio
@patch("recall.main.console")
async def test_main_config_not_found(
    mock_console: MagicMock,
    mock_load_config: MagicMock,
):
    """Test that main handles ConfigNotFoundError gracefully."""
    test_path = Path("/non/existent/config.yaml")
    mock_load_config.side_effect = ConfigNotFoundError(test_path)

    await main()

    expected_message = (
        f"❌ Error loading config: Configuration file not found at {test_path}"
    )
    mock_console.print.assert_called_with(expected_message)


@pytest.mark.asyncio
@patch("recall.main.console")
async def test_main_config_error(
    mock_console: MagicMock,
    mock_load_config: MagicMock,
):
    """Test that main handles a generic ConfigError."""
    mock_load_config.side_effect = ConfigError("YAML parsing error")

    await main()

    expected_msg = "❌ Error loading config: YAML parsing error"
    mock_console.print.assert_called_with(expected_msg)


@pytest.mark.asyncio
async def test_main_no_collectors_enabled(
    mock_load_config: MagicMock,
    mock_collect_events: MagicMock,
):
    """Test main's behavior when the config has no enabled collectors."""
    mock_load_config.return_value = {
        "sources": [{"type": "firefox", "enabled": False, "config": {}}],
    }

    await main()

    mock_collect_events.assert_not_called()


def test_init_collectors_from_config():
    """Test collector initialization from a valid config."""
    config = {
        "sources": [
            {"type": "firefox", "enabled": True, "config": {"path": "/fake"}},
            {"type": "slack", "enabled": True, "config": {"token": "123"}},
            {"type": "gitlab", "enabled": False, "config": {}},
            {"type": "unknown", "enabled": True, "config": {}},
        ],
    }

    with patch("recall.main.console") as mock_console:
        collectors = init_collectors_from_config(config)
        assert len(collectors) == 2
        assert collectors[0].name() == "Firefox"
        assert collectors[0].config == {"path": "/fake"}
        assert collectors[1].name() == "Slack"
        assert collectors[1].config == {"token": "123"}
        mock_console.print.assert_called_with(
            "Warning: Unknown collector type 'unknown'",
        )


def test_get_collector_map():
    """Test that the collector map is structured correctly."""
    collector_map = get_collector_map()
    assert "firefox" in collector_map
    assert "slack" in collector_map
    assert issubclass(collector_map["firefox"], BaseCollector)


@patch("sys.stdout.isatty", return_value=True)
def test_is_interactive_true(mock_isatty: MagicMock):
    """Test that is_interactive returns True when in a TTY."""
    assert is_interactive() is True
    mock_isatty.assert_called_once()


@patch("sys.stdout.isatty", return_value=False)
def test_is_interactive_false(mock_isatty: MagicMock):
    """Test that is_interactive returns False when not in a TTY."""
    assert is_interactive() is False
    mock_isatty.assert_called_once()


@patch("recall.main.console")
def test_print_formatted_event_simple(mock_console: MagicMock):
    """Test printing a basic event."""
    event = Event(timestamp=make_dt(10), source="Test", description="Simple event")
    print_formatted_event(event, "test_date", timezone.utc)
    mock_console.print.assert_any_call(
        r"\[test_date 09:10:00] [Test] Simple event",
    )


@pytest.mark.usefixtures("interactive_false")
@patch("recall.main.console")
def test_print_formatted_event_with_url_and_duration(
    mock_console: MagicMock,
):
    """Test printing an event with a URL and duration."""
    event = Event(
        timestamp=make_dt(15),
        source="Test",
        description="Event with URL",
        url="http://example.com",
        duration_minutes=5,
    )
    print_formatted_event(event, "test_date", timezone.utc)
    mock_console.print.assert_any_call(
        r"\[test_date 09:15:00] [Test] Event with URL (5 min)",
    )
    mock_console.print.assert_any_call("↳ http://example.com")


@pytest.mark.usefixtures("interactive_true")
@patch("recall.main.console")
def test_print_formatted_event_special_case_slack(mock_console: MagicMock):
    """Test the special panel formatting for Slack messages."""
    event = Event(
        timestamp=make_dt(20),
        source="Slack",
        description="Message in #channel:\n\nHello world",
    )
    print_formatted_event(event, "test_date", timezone.utc)
    assert any("Panel" in str(call) for call in mock_console.print.call_args_list)


@patch("recall.main.console")
@pytest.mark.usefixtures("interactive_false")
@time_machine.travel("2025-01-01 09:00:00 +0200")
def test_print_formatted_event_no_tz_fixed(
    mock_console: MagicMock,
):
    """Test printing an event without a local timezone provided."""
    local_tz = datetime.now().astimezone().tzinfo
    event = Event(timestamp=make_dt(10), source="Test", description="No TZ test")

    print_formatted_event(event, "test_date", None)

    local_timestamp = event.timestamp.astimezone(local_tz)
    expected_time = local_timestamp.strftime("%H:%M:%S")
    mock_console.print.assert_any_call(
        rf"\[test_date {expected_time}] [Test] No TZ test",
    )


@pytest.mark.usefixtures("interactive_true")
@patch("recall.main.console")
def test_print_formatted_event_split_failure(mock_console: MagicMock):
    """Test that improper splitting in user content cases is handled gracefully."""
    description = "Message in #dev. Malformed message without proper split."
    event = Event(
        timestamp=make_dt(25),
        source="Slack",
        description=description,
    )

    print_formatted_event(event, "test_date", timezone.utc)

    mock_console.print.assert_any_call(
        rf"\[test_date 09:25:00] [Slack] {description}",
    )
    mock_console.print.assert_called_with()


@pytest.mark.asyncio
async def test_collect_events_success():
    """Test successful event gathering from multiple collectors."""
    mock_collector_1 = MagicMock(spec=BaseCollector)
    mock_collector_1.name.return_value = "Collector1"
    mock_collector_1.collect = AsyncMock(return_value=[Event(make_dt(1), "C1", "E1")])

    mock_collector_2 = MagicMock(spec=BaseCollector)
    mock_collector_2.name.return_value = "Collector2"
    mock_collector_2.collect = AsyncMock(return_value=[Event(make_dt(2), "C2", "E2")])

    collectors: list[BaseCollector] = [mock_collector_1, mock_collector_2]
    events = await collect_events(collectors, make_dt(0), make_dt(60))

    assert len(events) == 2
    mock_collector_1.collect.assert_awaited_once()
    mock_collector_2.collect.assert_awaited_once()


@pytest.mark.asyncio
async def test_collect_events_with_error_and_spinner():
    """Test that collector errors are handled and reported to the spinner."""
    mock_collector_1 = MagicMock(spec=BaseCollector)
    mock_collector_1.name.return_value = "SuccessCollector"
    mock_collector_1.collect = AsyncMock(return_value=[])

    mock_collector_2 = MagicMock(spec=BaseCollector)
    mock_collector_2.name.return_value = "ErrorCollector"
    mock_collector_2.collect = AsyncMock(side_effect=ValueError("Test Error"))

    mock_spinner = MagicMock()
    collectors: list[BaseCollector] = [mock_collector_1, mock_collector_2]
    await collect_events(collectors, make_dt(0), make_dt(60), spinner=mock_spinner)

    mock_spinner.write.assert_any_call(
        "    - ❌ Error in ErrorCollector collector: Test Error",
    )
    mock_spinner.write.assert_any_call(
        "    - ✅ SuccessCollector collector found 0 events.",
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("interactive_false")
async def test_main_non_interactive_mode(
    mock_load_config: MagicMock,
    mock_collect_events: MagicMock,
):
    """Test the main function's successful execution path."""
    mock_load_config.return_value = {
        "sources": [{"type": "firefox", "enabled": True, "config": {}}],
    }
    mock_collect_events.return_value = [Event(make_dt(1), "Test", "Test Event")]

    await main()

    mock_collect_events.assert_awaited_once()


@patch("recall.main.yaspin")
@pytest.mark.asyncio
@pytest.mark.usefixtures("interactive_true")
async def test_main_interactive_mode(
    mock_yaspin: MagicMock,
    mock_collect_events: MagicMock,
    mock_parse_arguments: MagicMock,
    mock_load_config: MagicMock,
):
    """Tests the interactive path of main with yaspin spinner."""
    mock_load_config.return_value = {
        "sources": [{"type": "firefox", "enabled": True, "config": {}}],
    }
    mock_collect_events.return_value = [Event(make_dt(0), "Test", "Test Event")]
    mock_spinner = MagicMock()
    mock_yaspin.return_value.__enter__.return_value = mock_spinner

    await main()

    expected_date = mock_parse_arguments.return_value.strftime("%Y-%m-%d")
    expected_text = f"🚀 Collecting activity for {expected_date}..."
    mock_yaspin.assert_called_once_with(
        text=expected_text,
        color="yellow",
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures(
    "interactive_false",
    "mock_load_config",
    "mock_parse_arguments",
)
@patch("recall.main.console")
async def test_main_no_events_found(
    mock_console: MagicMock,
    mock_collect_events: MagicMock,
    mock_load_config: MagicMock,
):
    """Test the main function's behavior when no events are found."""
    mock_load_config.return_value = {
        "sources": [{"type": "firefox", "enabled": True, "config": {}}],
    }
    mock_collect_events.return_value = []
    await main()
    mock_console.print.assert_any_call("\nNo activity found for the specified date.")
