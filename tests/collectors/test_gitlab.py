from typing import Callable
from unittest.mock import MagicMock, patch

import pytest
from gitlab import GitlabAuthenticationError

from recall.collectors.gitlab import GitLabCollector, GitlabError
from tests.utils import make_dt


@pytest.fixture
def valid_config():
    """Fixture for a valid GitLab collector configuration."""
    return {
        "url": "https://gitlab.com",
        "private_token": "fake_token",
        "user_id": 123,
    }


@pytest.fixture
def collector(valid_config: dict):
    """Fixture for the GitLab Collector instance."""
    return GitLabCollector(config=valid_config)


@pytest.fixture
def mock_gitlab_event_builder():
    """Create mock GitLab Event objects for formatting tests."""

    def _builder(
        action_name: str,
        target_type: str | None = None,
        target_title: str | None = None,
        target_iid: int | None = None,
        push_data: dict | None = None,
        note: dict | None = None,
    ) -> MagicMock:
        mock = MagicMock()
        mock.action_name = action_name
        mock.target_type = target_type
        mock.target_title = target_title
        mock.target_iid = target_iid
        mock.push_data = push_data
        mock.note = note
        mock.project_id = 123
        mock.created_at = "2025-01-01T09:00:00.000Z"
        return mock

    return _builder


@pytest.fixture
def mock_gl_client_with_project():
    """Mock the GitLab client and project lookup helper."""
    mock_gl = MagicMock()
    mock_project = MagicMock()
    mock_project.web_url = "https://gitlab.com/group/project"
    mock_gl.projects.get.return_value = mock_project
    return mock_gl


def test_format_summary_pushed_to(
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test summary formatting for a push event."""
    event = mock_gitlab_event_builder(
        "pushed to",
        push_data={"commit_count": 3, "ref": "refs/heads/feature/awesome-feature"},
    )
    summary = collector._format_event_summary(event)
    assert summary == "Pushed 3 commit(s) to branch 'awesome-feature'"


def test_get_event_url_for_merge_request(
    collector: GitLabCollector,
    mock_gl_client_with_project: MagicMock,
    mock_gitlab_event_builder: Callable,
):
    """Test URL construction for a Merge Request with IID."""
    project_cache = {}
    event = mock_gitlab_event_builder(
        "opened",
        target_type="MergeRequest",
        target_iid=15,
    )
    url = collector._get_event_url(event, project_cache, mock_gl_client_with_project)
    assert url == "https://gitlab.com/group/project/-/merge_requests/15"


@pytest.mark.asyncio
async def test_collect_missing_config():
    """Test that a ValueError is raised if config values are missing."""
    with pytest.raises(
        ValueError,
        match=r"GitLab 'private_token' and 'user_id' must be set in config.yaml.",
    ):
        collector = GitLabCollector(config={})
        await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("gitlab.Gitlab")
async def test_collect_auth_error(
    mock_gitlab: MagicMock,
    collector: GitLabCollector,
):
    """Test that a ConnectionError is raised on authentication failure."""
    mock_gl_instance = mock_gitlab.return_value
    mock_gl_instance.auth.side_effect = GitlabAuthenticationError

    with pytest.raises(ConnectionError, match="GitLab authentication error"):
        await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("gitlab.Gitlab")
async def test_collect_general_error(
    mock_gitlab: MagicMock,
    collector: GitLabCollector,
):
    """Test that a ConnectionError is raised on a general GitLab connection failure."""
    mock_gl_instance = mock_gitlab.return_value
    mock_gl_instance.auth.side_effect = Exception("Some other error")

    with pytest.raises(ConnectionError, match="Failed to connect to GitLab"):
        await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("gitlab.Gitlab")
async def test_collect_skips_future_events(
    mock_gitlab: MagicMock,
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test that events with timestamps after the end_time are skipped."""
    mock_user = MagicMock()
    future_event = mock_gitlab_event_builder("pushed to", push_data={"commit_count": 1, "ref": "main"})
    future_event.created_at = "2025-01-01T10:00:00.000Z"
    mock_user.events.list.return_value = [future_event]

    mock_gl_instance = mock_gitlab.return_value
    mock_gl_instance.users.get.return_value = mock_user

    start_time, end_time = make_dt(0), make_dt(59)
    events = await collector.collect(start_time, end_time)

    assert len(events) == 0


@pytest.mark.asyncio
@patch("gitlab.Gitlab")
async def test_collect_successful(
    mock_gitlab: MagicMock,
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test a successful event collection run."""
    mock_user = MagicMock()
    mock_event = mock_gitlab_event_builder(
        "pushed to",
        push_data={"commit_count": 1, "ref": "main"},
    )
    mock_user.events.list.return_value = [mock_event]
    mock_gl_instance = mock_gitlab.return_value
    mock_gl_instance.users.get.return_value = mock_user

    events = await collector.collect(make_dt(0), make_dt(60))

    assert len(events) == 1
    assert events[0].description == "Pushed 1 commit(s) to branch 'main'"