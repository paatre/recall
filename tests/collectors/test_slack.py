from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from recall.collectors.slack import SlackCollector
from tests.utils import make_dt


@pytest.fixture
def valid_config():
    """Fixture for a valid Slack collector configuration."""
    return {"user_token": "fake-token"}


@pytest.fixture
def collector(valid_config: dict):
    """Fixture for the Slack Collector instance."""
    return SlackCollector(config=valid_config)


@pytest.fixture
def mock_slack_user_map() -> dict:
    """Provide a mock user ID to username mapping for Slack."""
    return {"U01A": "alice", "U02B": "bob"}


def test_name(collector: SlackCollector):
    """Test that the collector name is correct."""
    assert collector.name() == "Slack"


def test_replace_user_mentions_basic(
    collector: SlackCollector,
    mock_slack_user_map: dict,
):
    """Test replacing a simple user ID mention."""
    text = "Hey <@U01A>, can you look at this?"
    expected = "Hey @alice, can you look at this?"
    assert collector._replace_user_mentions(text, mock_slack_user_map) == expected


@pytest.mark.asyncio
async def test_collect_missing_token():
    """Test that a ValueError is raised if the Slack token is not set."""
    with pytest.raises(ValueError, match=r"Slack 'user_token' must be set in config.yaml."):
        collector = SlackCollector(config={})
        await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("recall.collectors.slack.WebClient")
async def test_collect_auth_failure(
    mock_web_client: MagicMock,
    collector: SlackCollector,
):
    """Test that a ConnectionError is raised on Slack authentication failure."""
    mock_web_client.return_value.auth_test.side_effect = SlackApiError(
        "auth failed",
        MagicMock(),
    )

    with pytest.raises(ConnectionError, match="Slack authentication failed"):
        await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("recall.collectors.slack.console")
@patch("recall.collectors.slack.WebClient")
async def test_collect_users_list_fails(
    mock_web_client: MagicMock,
    mock_console: MagicMock,
    collector: SlackCollector,
):
    """Test that a warning is printed if fetching the user list fails."""
    mock_client = mock_web_client.return_value

    mock_response = MagicMock()
    mock_response.__getitem__.return_value = "test_error"
    mock_client.users_list.side_effect = SlackApiError(
        "users list failed",
        mock_response,
    )

    mock_client.search_messages.return_value = {"messages": {"matches": []}}

    await collector.collect(make_dt(0), make_dt(60))

    mock_console.print.assert_called_with(
        "Warning: Could not fetch user list from Slack: test_error",
    )


@pytest.mark.asyncio
@patch("recall.collectors.slack.WebClient")
async def test_collect_successful_with_messages(
    mock_web_client: MagicMock,
    collector: SlackCollector,
):
    """Test a successful collection run with messages found."""
    mock_client = mock_web_client.return_value

    mock_client.users_list.return_value = {
        "members": [{"id": "U01A", "name": "alice"}],
    }

    mock_client.search_messages.return_value = {
        "messages": {
            "matches": [
                {
                    "ts": str(make_dt(15).timestamp()),
                    "channel": {"name": "general"},
                    "text": "Hello <@U01A>",
                    "permalink": "https://example.com/message1",
                },
            ],
        },
    }

    events = await collector.collect(make_dt(0), make_dt(60))

    assert len(events) == 1
    assert events[0].source == "Slack"
    assert "Message in #general" in events[0].description
    assert "@alice" in events[0].description
    assert events[0].url == "https://example.com/message1"
    assert events[0].timestamp == make_dt(15)