from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .base import BaseCollector, Event


class ShellCollector(BaseCollector):
    """Collects shell commands from a custom, timestamped history file."""

    def name(self) -> str:
        return "Shell"

    async def collect(self, start_time: datetime, end_time: datetime) -> List[Event]:
        """Reads the custom log file and parses commands within the time range."""
        log_file = Path.home() / ".work_activity_history.log"
        if not log_file.exists():
            print(
                "Warning: Shell history log file ~/.work_activity_history.log not found."
            )
            return []

        events = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        timestamp_str, command = line.split(" ", 1)
                        event_ts = datetime.fromisoformat(timestamp_str)
                        event_ts = event_ts.astimezone()
                        if start_time <= event_ts <= end_time:
                            events.append(
                                Event(
                                    timestamp=event_ts,
                                    source=self.name(),
                                    description=command.strip(),
                                    url=None,
                                )
                            )
                    except (ValueError, IndexError):
                        continue
        except IOError as e:
            print(f"Warning: Could not read shell history file: {e}")

        return events
