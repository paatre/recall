from datetime import datetime
from pathlib import Path

from rich.console import Console

from .base import BaseCollector, Event

SMALLEST_VALID_TIMESTAMP_LENGTH = 10
PARTS_IN_HISTORY_LINE = 2

console = Console()


class ShellCollector(BaseCollector):
    """Collects shell commands from a custom, timestamped history file."""

    def __init__(self, config: dict) -> None:
        """Initialize the Shell collector with its configuration."""
        super().__init__(config)
        self.log_file_path = Path(
            self.config.get("log_file_path", "~/.recall_shell_history.log"),
        ).expanduser()

    def name(self) -> str:
        """Return the name of the collector."""
        return "Shell"

    def _parse_line(self, line: str) -> tuple[datetime, str] | None:
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
        if not self.log_file_path.exists():
            console.print(f"Shell history log file {self.log_file_path} not found.")
            return []

        events = []
        try:
            with Path.open(self.log_file_path, encoding="utf-8") as f:
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
