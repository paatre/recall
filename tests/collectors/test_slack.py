import pytest

from recall.collectors.slack import SlackCollector


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
    """Test replacing a user ID mention that includes an optional display name.

    The optional display name is possible on an older Slack message format.
    """
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
