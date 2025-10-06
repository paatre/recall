from datetime import timedelta

from recall.collectors.base import Event

MAX_GAP_MINUTES = 5


def summarize_events(events: list[Event]) -> list[Event]:
    """Summarize a list of events by grouping consecutive identical events.

    Events are considered identical if they have the same source, description, and URL.
    """
    if not events:
        return []

    summarized_events: list[Event] = []

    current_group_start_event = events[0]
    last_event_timestamp = events[0].timestamp

    for i in range(1, len(events)):
        current_event = events[i]
        time_gap = current_event.timestamp - last_event_timestamp

        is_same_activity = (
            current_event.source == current_group_start_event.source
            and current_event.description == current_group_start_event.description
            and current_event.url == current_group_start_event.url
            and time_gap < timedelta(minutes=MAX_GAP_MINUTES)
        )

        if is_same_activity:
            last_event_timestamp = current_event.timestamp
        else:
            duration = last_event_timestamp - current_group_start_event.timestamp

            summarized_event = Event(
                timestamp=current_group_start_event.timestamp,
                source=current_group_start_event.source,
                description=current_group_start_event.description,
                duration_minutes=max(1, int(duration.total_seconds() / 60)),
                url=current_group_start_event.url,
            )
            summarized_events.append(summarized_event)

            current_group_start_event = current_event
            last_event_timestamp = current_event.timestamp

    duration = last_event_timestamp - current_group_start_event.timestamp
    summarized_events.append(
        Event(
            timestamp=current_group_start_event.timestamp,
            source=current_group_start_event.source,
            description=current_group_start_event.description,
            duration_minutes=max(1, int(duration.total_seconds() / 60)),
            url=current_group_start_event.url,
        ),
    )

    return summarized_events
