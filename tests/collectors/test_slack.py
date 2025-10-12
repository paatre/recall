from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from recall.collectors.slack import SlackCollector
from tests.utils import make_dt


@pytest.fixture
def collector():
    """Fixture for the Slack Collector instance."""
    return SlackCollector()


@pytest.fixture
def mock_slack_user_map() -> dict:
    """Provide a mock user ID to username mapping for Slack."""
    return {
        "U01A": "alice",
        "U02B": "bob",
        "U03C": "carl_the_dev",
        "W123": "workspace_user",
    }


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


def test_replace_user_mentions_with_optional_name(
    collector: SlackCollector,
    mock_slack_user_map: dict,
):
    """Test replacing a user ID mention that includes an optional display name."""
    text = "Thanks <@U03C|carl> for the review!"
    expected = "Thanks @carl_the_dev for the review!"
    assert collector._replace_user_mentions(text, mock_slack_user_map) == expected


def test_replace_user_mentions_unmapped_id(
    collector: SlackCollector,
    mock_slack_user_map: dict,
):
    """Test that an unknown user ID falls back to showing the ID."""
    text = "Review needed by <@U9999>."
    expected = "Review needed by @U9999."
    assert collector._replace_user_mentions(text, mock_slack_user_map) == expected


def test_replace_user_mentions_multiple_and_mixed(
    collector: SlackCollector,
    mock_slack_user_map: dict,
):
    """Test replacing multiple different user IDs and standard text."""
    text = "Meeting at 10:00 with <@U02B> and team <@U03C|carl>. Finalize the doc."
    expected = "Meeting at 10:00 with @bob and team @carl_the_dev. Finalize the doc."
    assert collector._replace_user_mentions(text, mock_slack_user_map) == expected


def test_replace_user_mentions_no_mentions(
    collector: SlackCollector,
    mock_slack_user_map: dict,
):
    """Test text with no mentions remains unchanged."""
    text = "This is a normal message about code refactoring."
    assert collector._replace_user_mentions(text, mock_slack_user_map) == text


@pytest.mark.asyncio
async def test_collect_missing_token(
    collector: SlackCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that a ValueError is raised if the Slack token is not set."""
    monkeypatch.delenv("SLACK_USER_TOKEN", raising=False)
    with pytest.raises(
        ValueError,
        match=r"SLACK_USER_TOKEN environment variable must be set.",
    ):
        await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("recall.collectors.slack.WebClient")
async def test_collect_auth_failure(
    mock_web_client: MagicMock,
    collector: SlackCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that a ConnectionError is raised on Slack authentication failure."""
    monkeypatch.setenv("SLACK_USER_TOKEN", "fake-token")
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
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that a warning is printed if fetching the user list fails."""
    monkeypatch.setenv("SLACK_USER_TOKEN", "fake-token")
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
async def test_collect_handles_users_without_id_or_name(
    mock_web_client: MagicMock,
    collector: SlackCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that users without an id or name are skipped gracefully."""
    monkeypatch.setenv("SLACK_USER_TOKEN", "fake-token")
    mock_client = mock_web_client.return_value
    mock_client.users_list.return_value = {
        "members": [
            {"id": "U01A", "name": "alice"},
            {"name": "user_without_id"},
            {"id": "U02B"},
        ],
    }
    mock_client.search_messages.return_value = {"messages": {"matches": []}}
    await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("recall.collectors.slack.console")
@patch("recall.collectors.slack.WebClient")
async def test_collect_search_fails(
    mock_web_client: MagicMock,
    mock_console: MagicMock,
    collector: SlackCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that a warning is printed if the message search fails."""
    monkeypatch.setenv("SLACK_USER_TOKEN", "fake-token")
    mock_client = mock_web_client.return_value

    mock_response = MagicMock()
    mock_response.__getitem__.return_value = "search_error"
    mock_client.search_messages.side_effect = SlackApiError(
        "search failed",
        mock_response,
    )

    await collector.collect(make_dt(0), make_dt(60))

    mock_console.print.assert_called_with(
        "Warning: Could not perform Slack search: search_error",
    )


@pytest.mark.asyncio
@patch("recall.collectors.slack.WebClient")
async def test_collect_successful_with_messages(
    mock_web_client: MagicMock,
    collector: SlackCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test a successful collection run with messages found."""
    monkeypatch.setenv("SLACK_USER_TOKEN", "fake-token")
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


@pytest.mark.asyncio
@patch("recall.collectors.slack.WebClient")
async def test_collect_skips_messages_outside_time_range(
    mock_web_client: MagicMock,
    collector: SlackCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that messages outside the specified time range are skipped."""
    monkeypatch.setenv("SLACK_USER_TOKEN", "fake-token")
    mock_client = mock_web_client.return_value
    mock_client.users_list.return_value = {"members": []}
    mock_client.search_messages.return_value = {
        "messages": {
            "matches": [
                {
                    "ts": str(make_dt(70).timestamp()),
                    "channel": {"name": "general"},
                    "text": "This message should be skipped",
                    "permalink": "https://example.com/message2",
                },
            ],
        },
    }

    events = await collector.collect(make_dt(0), make_dt(60))

    assert len(events) == 0
