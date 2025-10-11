from datetime import datetime
from pathlib import Path
from typing import Union

from rich.console import Console

from .base import BaseCollector, Event

SMALLEST_VALID_TIMESTAMP_LENGTH = 10
PARTS_IN_HISTORY_LINE = 2

console = Console()


class ShellCollector(BaseCollector):
    """Collects shell commands from a custom, timestamped history file."""

    def name(self) -> str:
        """Return the name of the collector."""
        return "Shell"

    def _parse_line(self, line: str) -> Union[tuple[datetime, str], None]:
        """Parse a line from the log file into a timestamp and command."""
        parts = line.strip().split(" ", 1)
        if len(parts) != PARTS_IN_HISTORY_LINE:
            return None
        timestamp_str, command = parts
        try:
            event_ts = datetime.fromisoformat(timestamp_str).astimezone()
        except ValueError:
            return None
        return event_ts, command.strip()

    async def collect(self, start_time: datetime, end_time: datetime) -> list[Event]:
        """Read the custom log file and parse commands within the time range."""
        log_file = Path.home() / ".recall_shell_history.log"
        if not log_file.exists():
            console.print(
                "Shell history log file ~/.recall_shell_history.log not found.",
            )
            return []

        events = []
        try:
            with Path.open(log_file, encoding="utf-8") as f:
                for line in f:
                    result = self._parse_line(line)
                    if not result:
                        continue

                    event_ts, command = result

                    if start_time <= event_ts <= end_time:
                        events.append(
                            Event(
                                timestamp=event_ts,
                                source=self.name(),
                                description=command,
                                url=None,
                            ),
                        )
        except (OSError, ValueError) as e:
            console.print(f"Warning: Could not read or parse shell history file: {e}")

        return events
