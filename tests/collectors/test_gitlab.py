from typing import Callable
from unittest.mock import MagicMock, patch

import pytest
from gitlab import GitlabAuthenticationError

from recall.collectors.gitlab import GitLabCollector, GitlabError
from tests.utils import make_dt


@pytest.fixture
def collector():
    """Fixture for the GitLab Collector instance."""
    return GitLabCollector(
        config={
            "private_token": "fake_token",
            "user_id": 123,
            "gitlab_url": "https://fake-gitlab.com",
        },
    )


@pytest.fixture
def mock_gitlab_event_builder():
    """Create mock GitLab Event objects for formatting tests.

    This abstracts away the complexity of mock objects used in GitLab parsing tests.
    """

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
    """Test summary formatting for a push event, extracting commit count and branch."""
    event = mock_gitlab_event_builder(
        "pushed to",
        push_data={"commit_count": 3, "ref": "refs/heads/feature/awesome-feature"},
    )
    summary = collector._format_event_summary(event)
    assert summary == "Pushed 3 commit(s) to branch 'awesome-feature'"


def test_format_summary_commented_on(
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test summary formatting for a comment event."""
    note_body = "Looks great, please confirm the timezone handling."
    event = mock_gitlab_event_builder(
        "commented on",
        target_type="Issue",
        note={"body": note_body},
    )
    summary = collector._format_event_summary(event)
    assert summary == f"Commented on issue:\n\n{note_body}\n"


def test_format_summary_opened_merge_request(
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test summary formatting for opening a merge request."""
    event = mock_gitlab_event_builder(
        "opened",
        target_type="MergeRequest",
        target_title="CI/CD Setup",
    )
    summary = collector._format_event_summary(event)
    assert summary == "Opened mergerequest: CI/CD Setup"


def test_format_summary_closed_issue(
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test summary formatting for closing an issue."""
    event = mock_gitlab_event_builder(
        "closed",
        target_type="Issue",
        target_title="Bug: Summarizer edge case",
    )
    summary = collector._format_event_summary(event)
    assert summary == "Closed issue: Bug: Summarizer edge case"


def test_format_summary_default_fallback(
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test the default summary format for unhandled event types."""
    event = mock_gitlab_event_builder("approved", target_type="MergeRequest")
    summary = collector._format_event_summary(event)
    assert summary == "approved MergeRequest"


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


def test_get_event_url_for_issue(
    collector: GitLabCollector,
    mock_gl_client_with_project: MagicMock,
    mock_gitlab_event_builder: Callable,
):
    """Test URL construction for an Issue with IID."""
    project_cache = {}
    event = mock_gitlab_event_builder("opened", target_type="Issue", target_iid=20)
    url = collector._get_event_url(event, project_cache, mock_gl_client_with_project)
    assert url == "https://gitlab.com/group/project/-/issues/20"


def test_get_event_url_for_pushed_to(
    collector: GitLabCollector,
    mock_gl_client_with_project: MagicMock,
    mock_gitlab_event_builder: Callable,
):
    """Test URL construction for a push event (links to the branch commits)."""
    project_cache = {}
    event = mock_gitlab_event_builder(
        "pushed to",
        push_data={"ref": "refs/heads/dev"},
        target_type=None,
    )
    url = collector._get_event_url(event, project_cache, mock_gl_client_with_project)
    assert url == "https://gitlab.com/group/project/-/commits/dev"


def test_get_event_url_for_comment_direct_link(
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test URL generation uses the direct link if available in the note."""
    expected_url = "https://gitlab.com/group/project/-/issues/1#note_1234"
    event = mock_gitlab_event_builder("commented on", note={"web_url": expected_url})
    url = collector._get_event_url(event, {}, MagicMock())
    assert url == expected_url


def test_get_event_url_for_comment_no_direct_link(
    collector: GitLabCollector,
    mock_gl_client_with_project: MagicMock,
    mock_gitlab_event_builder: Callable,
):
    """Test URL generation for a comment without a direct link."""
    project_cache = {}
    event = mock_gitlab_event_builder(
        "commented on",
        target_type="Issue",
        target_iid=25,
        note={"body": "A comment"},
    )
    url = collector._get_event_url(event, project_cache, mock_gl_client_with_project)
    assert url == "https://gitlab.com/group/project/-/issues/25"


def test_get_event_url_project_lookup_failure(
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test that URL returns None if project ID lookup fails (e.g., deleted project)."""
    mock_gl_client = MagicMock()
    mock_gl_client.projects.get.side_effect = GitlabError("Project not found")
    project_cache = {}
    event = mock_gitlab_event_builder("opened", target_type="Issue", target_iid=5)
    url = collector._get_event_url(event, project_cache, mock_gl_client)
    assert url is None


def test_get_event_url_no_project_id(
    collector: GitLabCollector,
    mock_gitlab_event_builder: Callable,
):
    """Test that URL returns None if the event has no project ID."""
    event = mock_gitlab_event_builder("pushed to")
    event.project_id = None
    url = collector._get_event_url(event, {}, MagicMock())
    assert url is None


def test_get_event_url_default_fallback(
    collector: GitLabCollector,
    mock_gl_client_with_project: MagicMock,
    mock_gitlab_event_builder: Callable,
):
    """Test the default URL fallback returns the project's base URL."""
    project_cache = {}
    event = mock_gitlab_event_builder("joined")
    url = collector._get_event_url(event, project_cache, mock_gl_client_with_project)
    assert url == "https://gitlab.com/group/project"


def test_get_project_base_url_caches_result(
    collector: GitLabCollector,
    mock_gl_client_with_project: MagicMock,
):
    """Test that _get_project_base_url caches the project URL after the first lookup."""
    project_url_cache = {}
    project_id = 123

    url1 = collector._get_project_base_url(
        project_id,
        project_url_cache,
        mock_gl_client_with_project,
    )
    assert url1 == "https://gitlab.com/group/project"
    assert project_id in project_url_cache

    mock_gl_client_with_project.projects.get.return_value.web_url = (
        "https://changed-url.com"
    )

    url2 = collector._get_project_base_url(
        project_id,
        project_url_cache,
        mock_gl_client_with_project,
    )
    assert url2 == "https://gitlab.com/group/project"
    assert mock_gl_client_with_project.projects.get.call_count == 1


def test_get_project_base_url_handles_gitlab_error(collector: GitLabCollector):
    """Test that _get_project_base_url returns None when a GitlabError is raised."""
    mock_gl_client = MagicMock()
    mock_gl_client.projects.get.side_effect = GitlabError
    project_url_cache = {}
    project_id = 999

    result = collector._get_project_base_url(
        project_id,
        project_url_cache,
        mock_gl_client,
    )

    assert result is None
    assert project_url_cache[project_id] is None


@pytest.mark.asyncio
async def test_collect_missing_config_keys():
    """Test that a ValueError is raised if environment variables are missing."""
    collector = GitLabCollector(config={"url": "https://fake-gitlab.com"})

    with pytest.raises(
        ValueError,
        match=r"GitLab 'private_token' and 'user_id' must be set in config.yaml.",
    ):
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
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that a ConnectionError is raised on a general GitLab connection failure."""
    monkeypatch.setenv("GITLAB_PRIVATE_TOKEN", "fake_token")
    monkeypatch.setenv("GITLAB_USER_ID", "123")
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
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that events with timestamps after the end_time are skipped."""
    monkeypatch.setenv("GITLAB_PRIVATE_TOKEN", "fake_token")
    monkeypatch.setenv("GITLAB_USER_ID", "123")

    mock_user = MagicMock()
    future_event = mock_gitlab_event_builder(
        "pushed to",
        push_data={"commit_count": 1, "ref": "main"},
    )
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
    monkeypatch: pytest.MonkeyPatch,
):
    """Test a successful event collection run."""
    monkeypatch.setenv("GITLAB_PRIVATE_TOKEN", "fake_token")
    monkeypatch.setenv("GITLAB_USER_ID", "123")

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
