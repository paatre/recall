from datetime import datetime, timedelta, timezone

import gitlab
from gitlab.exceptions import GitlabAuthenticationError, GitlabError
from gitlab.v4.objects import Event as GitLabEvent

from .base import BaseCollector, Event


class GitLabCollector(BaseCollector):
    """Collect activity events from the GitLab API."""

    def __init__(self, config: dict) -> None:
        """Initialize the GitLab collector with its configuration."""
        super().__init__(config)
        self.gitlab_url = self.config.get("url", "https://gitlab.com")
        self.private_token = self.config.get("private_token")
        self.user_id = self.config.get("user_id")

    def name(self) -> str:
        """Return the name of the collector."""
        return "GitLab"

    def _get_project_base_url(
        self,
        project_id: int,
        project_url_cache: dict,
        gl_client: gitlab.Gitlab,
    ) -> str | None:
        """Fetch and cache the base URL of a GitLab project."""
        if not project_id:
            return None

        if project_id not in project_url_cache:
            try:
                project = gl_client.projects.get(project_id)
                project_url_cache[project_id] = project.web_url
            except GitlabError:
                project_url_cache[project_id] = None
                return None

        return project_url_cache.get(project_id)

    def _get_event_url(
        self,
        event: GitLabEvent,
        project_url_cache: dict,
        gl_client: gitlab.Gitlab,
    ) -> str | None:
        """Construct a direct URL to the event's target (MR, issue, comment, etc.).

        Uses a cache to avoid redundant API calls for project URLs.
        """
        if event.action_name == "commented on":
            note = event.note
            if note and "web_url" in note:
                return note["web_url"]

        base_url = self._get_project_base_url(
            event.project_id,
            project_url_cache,
            gl_client,
        )
        if not base_url:
            return None

        target_type = event.target_type
        target_iid = event.target_iid

        if target_type == "MergeRequest" and target_iid:
            return f"{base_url}/-/merge_requests/{target_iid}"
        if target_type == "Issue" and target_iid:
            return f"{base_url}/-/issues/{target_iid}"
        if event.action_name == "pushed to" and event.push_data:
            branch = event.push_data.get("ref", "").split("/")[-1]
            return f"{base_url}/-/commits/{branch}"

        return base_url

    async def collect(self, start_time: datetime, end_time: datetime) -> list[Event]:
        """Fetch user events from the GitLab API within the time range."""
        if not self.private_token or not self.user_id:
            msg = "GitLab 'private_token' and 'user_id' must be set in config.yaml."
            raise ValueError(msg)

        gl = gitlab.Gitlab(self.gitlab_url, private_token=self.private_token)

        try:
            gl.auth()
            user = gl.users.get(self.user_id)
        except GitlabAuthenticationError as gitlab_auth_err:
            msg = f"GitLab authentication error: {gitlab_auth_err}"
            raise ConnectionError(msg) from gitlab_auth_err
        except Exception as e:
            msg = f"Failed to connect to GitLab: {e}"
            raise ConnectionError(msg) from e

        since = start_time - timedelta(seconds=1)

        api_events = user.events.list(all=True, after=since.strftime("%Y-%m-%d"))

        events = []
        project_url_cache = {}

        for event in api_events:
            event_ts = datetime.fromisoformat(event.created_at).replace(
                tzinfo=timezone.utc,
            )

            if event_ts > end_time:
                continue

            summary = self._format_event_summary(event)
            url = self._get_event_url(event, project_url_cache, gl)

            events.append(
                Event(
                    timestamp=event_ts,
                    source=self.name(),
                    description=summary,
                    url=url,
                ),
            )

        return events

    def _format_event_summary(self, event: GitLabEvent) -> str:
        """Create a human-readable summary from a GitLab event object."""
        action = event.action_name
        target = event.target_type or ""

        if action == "pushed to" and event.push_data:
            commit_count = event.push_data.get("commit_count", 0)
            branch = event.push_data.get("ref", "").split("/")[-1]
            return f"Pushed {commit_count} commit(s) to branch '{branch}'"

        if action == "commented on":
            body = event.note.get("body", "")
            return f"Commented on {target.lower()}:\n\n{body}\n"

        if action in {"opened", "closed", "merged"}:
            return f"{action.capitalize()} {target.lower()}: {event.target_title}"

        return f"{action} {target}"
