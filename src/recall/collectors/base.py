from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    """A standard container for any collected activity."""

    timestamp: datetime
    source: str
    description: str
    duration_minutes: Optional[int] = None
    url: Optional[str] = None


class BaseCollector(ABC):
    """An interface ensuring all collectors have the same methods."""

    @abstractmethod
    def name(self) -> str:
        """Return the collector's name, e.g., 'Firefox'."""

    @abstractmethod
    async def collect(self, start_time: datetime, end_time: datetime) -> list[Event]:
        """Gather event data."""
