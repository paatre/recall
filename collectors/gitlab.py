import os
import gitlab

from gitlab.exceptions import GitlabAuthenticationError, GitlabError
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from .base import BaseCollector, Event


class GitLabCollector(BaseCollector):
    """Collects activity events from the GitLab API."""

    def name(self) -> str:
        return "GitLab"

    def _get_event_url(
        self, event, project_url_cache: dict, gl_client: gitlab.Gitlab
    ) -> Optional[str]:
        """
        Constructs a direct URL to the event's target (MR, issue, comment, etc.).
        Uses a cache to avoid redundant API calls for project URLs.
        """
        if event.action_name == "commented on":
            note = event.note
            if note and "web_url" in note:
                return note["web_url"]

        project_id = event.project_id
        if not project_id:
            return None

        if project_id not in project_url_cache:
            try:
                project = gl_client.projects.get(project_id)
                project_url_cache[project_id] = project.web_url
            except GitlabError:
                project_url_cache[project_id] = None
                return None

        base_url = project_url_cache.get(project_id)
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

    async def collect(self, start_time: datetime, end_time: datetime) -> List[Event]:
        """Fetches user events from the GitLab API within the time range."""

        gitlab_url = os.environ.get("GITLAB_URL", "https://gitlab.com")
        private_token = os.environ.get("GITLAB_PRIVATE_TOKEN")
        user_id = os.environ.get("GITLAB_USER_ID")

        if not private_token or not user_id:
            raise ValueError(
                "GITLAB_PRIVATE_TOKEN and GITLAB_USER_ID environment variables must be set."
            )

        gl = gitlab.Gitlab(gitlab_url, private_token=private_token)

        try:
            gl.auth()
            user = gl.users.get(user_id)
        except GitlabAuthenticationError:
            raise ConnectionError("GitLab authentication failed. Check your token.")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to GitLab: {e}") from e

        since = start_time - timedelta(seconds=1)

        api_events = user.events.list(all=True, after=since.strftime("%Y-%m-%d"))

        events = []
        project_url_cache = {}

        for event in api_events:
            event_ts = datetime.fromisoformat(event.created_at).replace(
                tzinfo=timezone.utc
            )

            if event_ts > end_time:
                continue

            summary = self._format_event_summary(event)
            url = self._get_event_url(event, project_url_cache, gl)

            events.append(
                Event(
                    timestamp=event_ts, source=self.name(), description=summary, url=url
                )
            )

        return events

    def _format_event_summary(self, event) -> str:
        """Creates a human-readable summary from a GitLab event object."""
        action = event.action_name
        target = event.target_type or ""

        if action == "pushed to" and event.push_data:
            commit_count = event.push_data.get("commit_count", 0)
            branch = event.push_data.get("ref", "").split("/")[-1]
            return f"Pushed {commit_count} commit(s) to branch '{branch}'"

        elif action == "commented on":
            body = event.note.get("body", "")
            return f"Commented on {target.lower()}:\n\n{body}\n"

        elif action == "opened" or action == "closed" or action == "merged":
            return f"{action.capitalize()} {target.lower()}: {event.target_title}"

        return f"{action} {target}"
