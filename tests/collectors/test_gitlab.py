from typing import Callable
from unittest.mock import MagicMock

import pytest

from recall.collectors.gitlab import GitLabCollector, GitlabError


@pytest.fixture
def collector():
    """Fixture for the GitLab Collector instance."""
    return GitLabCollector()


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
