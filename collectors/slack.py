import os
import re
from datetime import datetime, timezone
from typing import List, Dict

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .base import BaseCollector, Event


class SlackCollector(BaseCollector):
    """Collects messages sent by the user from the Slack API using search."""

    def name(self) -> str:
        return "Slack"

    def _replace_user_mentions(self, text: str, user_map: Dict[str, str]) -> str:
        """Replaces Slack user ID mentions with their actual usernames."""

        def replace_mention(match):
            user_id = match.group(1)
            username = user_map.get(user_id, user_id)  # Fallback to ID if not found
            return f"@{username}"

        return re.sub(r"<@(U[A-Z0-9]+)(?:\|.*?)?>", replace_mention, text)

    async def collect(self, start_time: datetime, end_time: datetime) -> List[Event]:
        """Fetches user messages and replaces user IDs with usernames."""
        token = os.environ.get("SLACK_USER_TOKEN")
        if not token:
            raise ValueError("SLACK_USER_TOKEN environment variable must be set.")

        client = WebClient(token=token)

        try:
            client.auth_test()
        except SlackApiError as e:
            raise ConnectionError(f"Slack authentication failed. Check your token: {e}")

        user_map = {}
        try:
            result = client.users_list()
            for user in result.get("members", []):
                if "id" in user and "name" in user:
                    user_map[user["id"]] = user["name"]
        except SlackApiError as e:
            print(f"Warning: Could not fetch user list from Slack: {e.response['error']}")

        events = []
        on_date = start_time.strftime("%Y-%m-%d")
        query = f"from:me on:{on_date}"

        try:
            search_results = client.search_messages(
                query=query, sort="timestamp", count=100
            )

            for match in search_results.get("messages", {}).get("matches", []):
                event_ts = datetime.fromtimestamp(float(match["ts"]), tz=timezone.utc)

                if not (start_time <= event_ts <= end_time):
                    continue

                text = self._replace_user_mentions(match.get("text", ""), user_map)

                events.append(
                    Event(
                        timestamp=event_ts,
                        source=self.name(),
                        description=f"Message in #{match['channel']['name']}:\n\n{text}\n",
                        url=match.get("permalink"),
                    )
                )

        except SlackApiError as e:
            print(f"Warning: Could not perform Slack search: {e.response['error']}")

        return events
