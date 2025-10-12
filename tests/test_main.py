from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from recall.collectors.base import BaseCollector, Event
from recall.config import ConfigError, ConfigNotFoundError
from recall.main import (
    collect_events,
    get_collector_map,
    init_collectors_from_config,
    main,
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


@pytest.mark.asyncio
@patch("recall.main.console")
async def test_main_happy_path(
    mock_console: MagicMock,
    mock_load_config: MagicMock,
    mock_collect_events: MagicMock,
    mock_parse_arguments: MagicMock,
):
    """Test the main function's successful execution with a valid config."""
    mock_load_config.return_value = {
        "sources": [
            {"type": "firefox", "enabled": True, "config": {}},
            {"type": "gitlab", "enabled": False, "config": {}},
        ]
    }
    mock_collect_events.return_value = [Event(make_dt(1), "Test", "Test Event")]

    await main()

    mock_load_config.assert_called_once()
    mock_parse_arguments.assert_called_once()
    mock_collect_events.assert_awaited_once()
    # Check that only the enabled collector was passed to collect_events
    collectors_passed = mock_collect_events.call_args[0][0]
    assert len(collectors_passed) == 1
    assert collectors_passed[0].name() == "Firefox"
    mock_console.print.assert_any_call(
        "\n--- Summarized Activity Timeline for 2025-01-01 ---\n"
    )


@pytest.mark.asyncio
@patch("recall.main.console")
async def test_main_config_not_found(
    mock_console: MagicMock,
    mock_load_config: MagicMock,
    mock_parse_arguments: MagicMock,
):
    """Test that main handles ConfigNotFoundError gracefully."""
    mock_load_config.side_effect = ConfigNotFoundError(MagicMock())
    await main()
    assert "❌ Error: Configuration file not found at" in mock_console.print.call_args[0][0]


@pytest.mark.asyncio
@patch("recall.main.console")
async def test_main_config_error(
    mock_console: MagicMock,
    mock_load_config: MagicMock,
    mock_parse_arguments: MagicMock,
):
    """Test that main handles a generic ConfigError."""
    mock_load_config.side_effect = ConfigError("YAML parsing error")
    await main()
    mock_console.print.assert_called_with("❌ Error: YAML parsing error")


@pytest.mark.asyncio
@patch("recall.main.console")
async def test_main_no_collectors_enabled(
    mock_console: MagicMock,
    mock_load_config: MagicMock,
    mock_parse_arguments: MagicMock,
    mock_collect_events: MagicMock,
):
    """Test main's behavior when the config has no enabled collectors."""
    mock_load_config.return_value = {
        "sources": [{"type": "firefox", "enabled": False}]
    }
    await main()
    mock_console.print.assert_called_with(
        "No collectors enabled in the configuration file."
    )
    mock_collect_events.assert_not_called()


def test_init_collectors_from_config():
    """Test collector initialization from a valid config."""
    config = {
        "sources": [
            {"type": "firefox", "enabled": True, "config": {"path": "/tmp"}},
            {"type": "slack", "enabled": True, "config": {"token": "123"}},
            {"type": "gitlab", "enabled": False, "config": {}},
            {"type": "unknown", "enabled": True, "config": {}},
        ]
    }
    with patch("recall.main.console") as mock_console:
        collectors = init_collectors_from_config(config)
        assert len(collectors) == 2
        assert collectors[0].name() == "Firefox"
        assert collectors[0].config == {"path": "/tmp"}
        assert collectors[1].name() == "Slack"
        assert collectors[1].config == {"token": "123"}
        mock_console.print.assert_called_with("Warning: Unknown collector type 'unknown'")


def test_get_collector_map():
    """Test that the collector map is structured correctly."""
    collector_map = get_collector_map()
    assert "firefox" in collector_map
    assert "slack" in collector_map
    assert issubclass(collector_map["firefox"], BaseCollector)


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
@patch("recall.main.console")
async def test_collect_events_with_error(mock_console: MagicMock):
    """Test that collector errors are handled and reported."""
    mock_collector_1 = MagicMock(spec=BaseCollector)
    mock_collector_1.name.return_value = "SuccessCollector"
    mock_collector_1.collect = AsyncMock(return_value=[])

    mock_collector_2 = MagicMock(spec=BaseCollector)
    mock_collector_2.name.return_value = "ErrorCollector"
    mock_collector_2.collect = AsyncMock(side_effect=ValueError("Test Error"))

    collectors: list[BaseCollector] = [mock_collector_1, mock_collector_2]
    await collect_events(collectors, make_dt(0), make_dt(60))

    mock_console.print.assert_any_call(
        "    - ❌ Error in ErrorCollector collector: Test Error"
    )
    mock_console.print.assert_any_call(
        "    - ✅ SuccessCollector collector found 0 events."
    )