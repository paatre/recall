from collections.abc import Iterator
from datetime import timedelta

from recall.collectors.base import Event

MAX_GAP_MINUTES = 5


def _is_same_activity(event: Event, next_event: Event) -> bool:
    """Check if two consecutive events are part of the same activity."""
    time_gap = next_event.timestamp - event.timestamp
    return (
        event.source == next_event.source
        and event.description == next_event.description
        and event.url == next_event.url
        and time_gap < timedelta(minutes=MAX_GAP_MINUTES)
    )


def _create_summarized_event(event_group: list[Event]) -> Event:
    """Create a single event summary from a group of events."""
    start_event = event_group[0]
    last_event = event_group[-1]
    duration = last_event.timestamp - start_event.timestamp
    return Event(
        timestamp=start_event.timestamp,
        source=start_event.source,
        description=start_event.description,
        duration_minutes=max(1, int(duration.total_seconds() / 60)),
        url=start_event.url,
    )


def _group_events(events: list[Event]) -> Iterator[list[Event]]:
    """Group consecutive events that are part of the same activity."""
    if not events:
        return

    events_iter = iter(events)
    current_group = [next(events_iter)]

    for event in events_iter:
        if _is_same_activity(current_group[-1], event):
            current_group.append(event)
        else:
            yield current_group
            current_group = [event]

    yield current_group


def summarize_events(events: list[Event]) -> list[Event]:
    """Summarize a list of events by grouping consecutive identical events.

    Events are considered identical if they have the same source, description,
    and URL, and occur within a few minutes of each other.
    """
    if not events:
        return []

    return [_create_summarized_event(group) for group in _group_events(events)]
