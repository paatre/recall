from datetime import timedelta

from recall.collectors.base import Event
from recall.utils.summarizer import (
    MAX_GAP_MINUTES,
    _create_summarized_event,
    _group_events,
    _is_same_activity,
    summarize_events,
)

from .utils import make_dt


def test_is_same_activity_identical_within_gap(event: Event):
    """Test two identical events slightly separated are considered the same activity."""
    next_event = Event(
        timestamp=make_dt(10) + timedelta(minutes=MAX_GAP_MINUTES - 1),
        source=event.source,
        description=event.description,
        url=event.url,
    )
    assert _is_same_activity(event, next_event) is True


def test_is_same_activity_time_gap_exceeded(event: Event):
    """Test two identical events outside the MAX_GAP_MINUTES are NOT the same."""
    next_event = Event(
        timestamp=make_dt(10) + timedelta(minutes=MAX_GAP_MINUTES + 1),
        source=event.source,
        description=event.description,
        url=event.url,
    )
    assert _is_same_activity(event, next_event) is False


def test_is_same_activity_different_description(event: Event):
    """Test different descriptions stop grouping."""
    next_event = Event(
        timestamp=make_dt(11),
        source=event.source,
        description="git push",
        url=event.url,
    )
    assert _is_same_activity(event, next_event) is False


def test_is_same_activity_different_source(event: Event):
    """Test different sources stop grouping."""
    next_event = Event(
        timestamp=make_dt(11),
        source="GitLab",
        description=event.description,
        url=event.url,
    )
    assert _is_same_activity(event, next_event) is False


def test_is_same_activity_different_url(event: Event):
    """Test different URLs stop grouping."""
    next_event = Event(
        timestamp=make_dt(11),
        source=event.source,
        description=event.description,
        url="https://different.com",
    )
    assert _is_same_activity(event, next_event) is False


def test_create_summarized_event_min_duration():
    """Test that the minimum duration is 1 minute for a single event."""
    start_ts = make_dt(10, 0)
    end_ts = make_dt(10, 30)
    events = [
        Event(timestamp=start_ts, source="S", description="D"),
        Event(timestamp=end_ts, source="S", description="D"),
    ]
    summary = _create_summarized_event(events)
    assert summary.duration_minutes == 1


def test_group_events_yields_correct_groups():
    """Test that _group_events correctly chunks a complex sequence into groups."""
    events = [
        Event(timestamp=make_dt(10), source="S", description="A", url=None),
        Event(timestamp=make_dt(11), source="S", description="A", url=None),
        Event(
            timestamp=make_dt(18),
            source="F",
            description="B",
            url=None,
        ),
        Event(
            timestamp=make_dt(25),
            source="S",
            description="A",
            url=None,
        ),
    ]
    groups = list(_group_events(events))
    assert len(groups) == 3
    assert len(groups[0]) == 2
    assert len(groups[1]) == 1
    assert len(groups[2]) == 1


def test_summarize_events_empty():
    """Test that an empty event list returns an empty list."""
    assert summarize_events([]) == []


def test_summarize_events_full_pipeline_duration():
    """Test the full summary pipeline calculates the correct overall duration."""
    events = [
        Event(timestamp=make_dt(10), source="S", description="D", url=None),
        Event(timestamp=make_dt(12), source="S", description="D", url=None),
        Event(timestamp=make_dt(19), source="F", description="D2", url=None),
    ]
    result = summarize_events(events)
    assert len(result) == 2
    assert result[0].duration_minutes == 2
    assert result[1].duration_minutes == 1
