import re
from datetime import datetime, timezone

from rich.console import Console
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .base import BaseCollector, Event

console = Console()


class SlackCollector(BaseCollector):
    """Collect messages sent by the user from the Slack API using search."""

    def __init__(self, config: dict) -> None:
        """Initialize the Slack collector with its configuration."""
        super().__init__(config)
        self.user_token = self.config.get("user_token")

    def name(self) -> str:
        """Return the name of the collector."""
        return "Slack"

    def _replace_user_mentions(self, text: str, user_map: dict[str, str]) -> str:
        """Replace Slack user ID mentions with their actual usernames."""

        def replace_mention(match: re.Match) -> str:
            user_id = match.group(1)
            username = user_map.get(user_id, user_id)
            return f"@{username}"

        return re.sub(r"<@(U[A-Z0-9]+)(?:\|.*?)?>", replace_mention, text)

    async def collect(self, start_time: datetime, end_time: datetime) -> list[Event]:
        """Fetch user messages and replaces user IDs with usernames."""
        if not self.user_token:
            msg = "Slack 'user_token' must be set in config.yaml."
            raise ValueError(msg)

        client = WebClient(token=self.user_token)

        try:
            client.auth_test()
        except SlackApiError as e:
            msg = f"Slack authentication failed. Check your token: {e}"
            raise ConnectionError(msg) from e

        user_map = {}
        try:
            result = client.users_list()
            for user in result.get("members", []):
                if "id" in user and "name" in user:
                    user_map[user["id"]] = user["name"]
        except SlackApiError as e:
            console.print(
                f"Warning: Could not fetch user list from Slack: {e.response['error']}",
            )

        events = []
        on_date = start_time.strftime("%Y-%m-%d")
        query = f"from:me on:{on_date}"

        try:
            search_results = client.search_messages(
                query=query,
                sort="timestamp",
                count=100,
            )

            for match in search_results.get("messages", {}).get("matches", []):
                event_ts = datetime.fromtimestamp(float(match["ts"]), tz=timezone.utc)

                if not (start_time <= event_ts <= end_time):
                    continue

                channel_name = match["channel"]["name"]
                text = self._replace_user_mentions(match.get("text", ""), user_map)

                events.append(
                    Event(
                        timestamp=event_ts,
                        source=self.name(),
                        description=f"Message in #{channel_name}:\n\n{text}\n",
                        url=match.get("permalink"),
                    ),
                )

        except SlackApiError as e:
            console.print(
                f"Warning: Could not perform Slack search: {e.response['error']}",
            )

        return events
