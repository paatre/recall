from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import time_machine

from recall.collectors.base import BaseCollector, Event
from recall.main import (
    ENABLED_COLLECTORS,
    collect_events,
    is_interactive,
    main,
    parse_arguments,
    print_formatted_event,
)
from tests.utils import make_dt


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


@pytest.fixture
def mock_path():
    """Fixture to mock Path."""
    with patch("recall.main.Path") as mock:
        yield mock


@pytest.fixture
def mock_load_dotenv():
    """Fixture to mock load_dotenv."""
    with patch("recall.main.load_dotenv") as mock:
        yield mock


@patch("recall.main.load_dotenv")
@patch("pathlib.Path.exists")
@patch("recall.main.collect_events")
@patch("recall.main.parse_arguments")
@pytest.mark.asyncio
@pytest.mark.usefixtures("interactive_false")
async def test_main_config_loading(
    mock_parse_args: MagicMock,
    mock_collect: MagicMock,
    mock_path_exists: MagicMock,
    mock_load_dotenv: MagicMock,
):
    """Ensuring load_dotenv is called correctly.

    Checks both the global config path and the override call.
    """
    mock_parse_args.return_value = datetime(2025, 1, 1, tzinfo=timezone.utc)
    mock_collect.return_value = [
        Event(timestamp=make_dt(0), source="Test", description="Test Event"),
    ]
    mock_path_exists.return_value = True

    await main()

    global_path = Path("~/.config/recall/config.env").expanduser()
    mock_load_dotenv.assert_any_call(global_path)
    mock_load_dotenv.assert_any_call(override=True)
    assert mock_load_dotenv.call_count == 2


@patch("recall.main.load_dotenv")
@patch("pathlib.Path.exists")
@patch("recall.main.collect_events")
@patch("recall.main.parse_arguments")
@pytest.mark.asyncio
@pytest.mark.usefixtures("interactive_false")
async def test_main_no_global_config(
    mock_parse_args: MagicMock,
    mock_collect: MagicMock,
    mock_path_exists: MagicMock,
    mock_load_dotenv: MagicMock,
):
    """Test that load_dotenv is only called once when no global config exists."""
    mock_parse_args.return_value = datetime(2025, 1, 1, tzinfo=timezone.utc)
    mock_collect.return_value = [
        Event(timestamp=make_dt(0), source="Test", description="Test Event"),
    ]
    mock_path_exists.return_value = False

    await main()

    mock_load_dotenv.assert_called_once_with(override=True)


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


def test_parse_arguments_invalid_date():
    """Test that an invalid date format raises a ValueError."""
    with (
        patch("sys.argv", ["recall", "invalid-date"]),
        pytest.raises(ValueError, match=r"Invalid date format."),
    ):
        parse_arguments()


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
    event = Event(timestamp=make_dt(10), source="Test", description="No TZ test")

    print_formatted_event(event, "test_date", None)

    expected_time = "11:10:00"
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
@pytest.mark.usefixtures("interactive_false", "mock_load_dotenv", "mock_path")
@patch("recall.main.collect_events")
@patch("recall.main.parse_arguments")
async def test_main_non_interactive_mode(
    mock_parse_args: MagicMock,
    mock_collect: MagicMock,
):
    """Test the main function's successful execution path."""
    mock_parse_args.return_value = make_dt(0).replace(
        year=2025,
        month=10,
        day=12,
    )
    mock_collect.return_value = [Event(make_dt(1), "Test", "Test Event")]

    await main()

    assert mock_collect.call_args[0][0][0].name() == ENABLED_COLLECTORS[0]().name()
    assert mock_collect.called


@patch("recall.main.yaspin")
@patch("recall.main.collect_events")
@patch("recall.main.parse_arguments")
@pytest.mark.asyncio
@pytest.mark.usefixtures("interactive_true", "mock_load_dotenv", "mock_path")
async def test_main_interactive_mode(
    mock_parse_args: MagicMock,
    mock_collect: MagicMock,
    mock_yaspin: MagicMock,
):
    """Tests the interactive path of main with yaspin spinner."""
    target_date = datetime(2025, 10, 12, tzinfo=timezone.utc)
    mock_parse_args.return_value = target_date
    mock_collect.return_value = [Event(make_dt(0), "Test", "Test Event")]
    mock_spinner = MagicMock()
    mock_yaspin.return_value.__enter__.return_value = mock_spinner

    await main()

    expected_text = f"🚀 Collecting activity for {target_date.strftime('%Y-%m-%d')}..."
    mock_yaspin.assert_called_once_with(
        text=expected_text,
        color="yellow",
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("interactive_false", "mock_load_dotenv")
@patch("recall.main.console")
@patch("recall.main.parse_arguments")
async def test_main_handles_parse_error(
    mock_parse_args: MagicMock,
    mock_console: MagicMock,
):
    """Test that main handles a ValueError from argument parsing."""
    mock_parse_args.side_effect = ValueError("Bad Date")
    await main()
    mock_console.print.assert_called_with("❌ Error: Bad Date")


@pytest.mark.asyncio
@pytest.mark.usefixtures("interactive_false", "mock_load_dotenv")
@patch("recall.main.console")
@patch("recall.main.collect_events")
@patch("recall.main.parse_arguments")
async def test_main_no_events_found(
    mock_parse_args: MagicMock,
    mock_collect_events: MagicMock,
    mock_console: MagicMock,
):
    """Test the main function's behavior when no events are found."""
    mock_parse_args.return_value = make_dt(0)
    mock_collect_events.return_value = []
    await main()
    mock_console.print.assert_any_call("\nNo activity found for the specified date.")
