import argparse
import asyncio
import contextlib
import sys
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from yaspin import yaspin
from yaspin.core import Yaspin

from .collectors.base import BaseCollector, Event
from .collectors.firefox import FirefoxCollector
from .collectors.gcalendar import GoogleCalendarCollector
from .collectors.gitlab import GitLabCollector
from .collectors.shell import ShellCollector
from .collectors.slack import SlackCollector
from .config import ConfigError, ConfigNotFoundError, load_config
from .utils.summarizer import summarize_events

console = Console()


def parse_flexible_date(date_str: str) -> date:
    """Parse a date string in YYYY-MM-DD format or with keywords.

    Supports keywords like "today", "yesterday", or a weekday (e.g., "friday" or "fri").
    """
    date_str = date_str.strip().lower()
    local_today = datetime.now().astimezone().date()

    if date_str == "today":
        return local_today
    if date_str == "yesterday":
        return local_today - timedelta(days=1)

    day_map = {
        "monday": 0,
        "mon": 0,
        "tuesday": 1,
        "tue": 1,
        "wednesday": 2,
        "wed": 2,
        "thursday": 3,
        "thu": 3,
        "friday": 4,
        "fri": 4,
        "saturday": 5,
        "sat": 5,
        "sunday": 6,
        "sun": 6,
    }

    if date_str in day_map:
        target_weekday = day_map[date_str]
        today_weekday = local_today.weekday()

        days_ago = (today_weekday - target_weekday + 7) % 7

        return local_today - timedelta(days=days_ago)

    try:
        return date.fromisoformat(date_str)
    except ValueError as e:
        value_error_msg = (
            f"Invalid date '{date_str}'. Use YYYY-MM-DD, today, yesterday, or weekday.",
        )
        raise ValueError(value_error_msg) from e


def parse_flexible_time(time_str: str) -> time:
    """Parse a time string in H, H:M, or H:M:S format."""
    parts = time_str.split(":")

    match parts:
        case [h] if h:
            h_str, m_str, s_str = h, "0", "0"
        case [h, m]:
            h_str, m_str, s_str = h, m, "0"
        case [h, m, s]:
            h_str, m_str, s_str = h, m, s
        case _:
            invalid_time_format_error = (
                f"Invalid time format in '{time_str}'. Expected H, H:M, or H:M:S."
            )
            raise ValueError(invalid_time_format_error)

    try:
        hour = int(h_str)
        minute = int(m_str)
        second = int(s_str)

        return time(hour=hour, minute=minute, second=second)

    except (ValueError, TypeError) as err:
        invalid_time_value_error = f"Invalid time value in '{time_str}'"
        raise ValueError(invalid_time_value_error) from err


def parse_arguments() -> tuple[datetime, datetime, Path | None]:
    """Parse command-line arguments to get the target date."""
    parser = argparse.ArgumentParser(
        description="Collect activity data from various sources for a specific date.",
    )
    parser.add_argument(
        "date",
        nargs="?",
        help="The date to collect data for in YYYY-MM-DD format. Defaults to today.",
        default=(datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to the configuration file.",
        default=None,
    )
    parser.add_argument(
        "-s",
        "--start-time",
        help="The start time in HH:MM:SS format. Defaults to 00:00:00.",
        default="00:00:00",
    )
    parser.add_argument(
        "-e",
        "--end-time",
        help="The end time in HH:MM:SS format. Defaults to 23:59:59.",
        default="23:59:59",
    )
    args = parser.parse_args()

    try:
        local_tz = datetime.now().astimezone().tzinfo
        target_date = parse_flexible_date(args.date)
        start_time = parse_flexible_time(args.start_time)
        end_time = parse_flexible_time(args.end_time)
    except ValueError as e:
        msg = "Invalid date/time format. Please use YYYY-MM-DD and HH:MM:SS formats."
        raise ValueError(msg) from e
    else:
        base_datetime = datetime(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
            tzinfo=local_tz,
        )
        start_datetime = base_datetime.replace(
            hour=start_time.hour,
            minute=start_time.minute,
            second=start_time.second,
        )
        end_datetime = base_datetime.replace(
            hour=end_time.hour,
            minute=end_time.minute,
            second=end_time.second,
        )
        return start_datetime, end_datetime, args.config


def get_collector_map() -> dict[str, type[BaseCollector]]:
    """Return a mapping from collector type names to collector classes."""
    return {
        "firefox": FirefoxCollector,
        "gcalendar": GoogleCalendarCollector,
        "gitlab": GitLabCollector,
        "shell": ShellCollector,
        "slack": SlackCollector,
    }


def init_collectors_from_config(config: dict[str, Any]) -> list[BaseCollector]:
    """Initialize collectors based on the provided configuration."""
    collectors = []
    collector_map = get_collector_map()
    for source in config.get("sources", []):
        if source.get("enabled", False):
            collector_type = source.get("type")
            if collector_type in collector_map:
                collector_class = collector_map[collector_type]
                collector_config = source.get("config", {})
                collectors.append(collector_class(collector_config))
            else:
                console.print(f"Warning: Unknown collector type '{collector_type}'")
    return collectors


def is_interactive() -> bool:
    """Check if the script is running in an interactive terminal."""
    return sys.stdout.isatty()


def print_formatted_event(event: Event, date_str: str, local_tz: tzinfo | None) -> None:
    """Print a formatted event, with special handling for Slack and GitLab."""
    if local_tz:
        local_timestamp = event.timestamp.astimezone(local_tz)
    else:
        local_timestamp = event.timestamp.astimezone()
    source = f"[{event.source}]"
    duration_str = (
        f"({event.duration_minutes} min)"
        if event.duration_minutes and event.duration_minutes > 1
        else ""
    )
    description_short = event.description or ""

    has_user_content_and_interactive = (
        "Message in" in description_short or "Commented on" in description_short
    ) and is_interactive()

    if has_user_content_and_interactive:
        try:
            header, content = description_short.split("\n\n", 1)
            time_str = local_timestamp.strftime("%H:%M:%S")
            console.print(
                rf"\[{date_str} {time_str}] {source} {header.strip()}",
            )

            text_to_render = Text(content.strip(), justify="left")
            panel = Panel(text_to_render, border_style="cyan", expand=False)
            console.print(panel)
        except ValueError:
            has_user_content_and_interactive = False

    if not has_user_content_and_interactive:
        text_to_print = (
            rf"\[{date_str} {local_timestamp.strftime('%H:%M:%S')}] "
            f"{source} "
            f"{description_short.strip()} "
            f"{duration_str} "
        )

        console.print(text_to_print.strip())

    if event.url:
        console.print(f"↳ {event.url}")

    console.print()


async def collect_events(
    collectors: list[BaseCollector],
    start_time: datetime,
    end_time: datetime,
    spinner: Yaspin | None = None,
) -> list[Event]:
    """Gather events from all collectors."""
    tasks = [collector.collect(start_time, end_time) for collector in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_events = []
    for i, result in enumerate(results):
        collector_name = collectors[i].name()
        message = ""
        if isinstance(result, (Exception, BaseException)):
            message = f"    - ❌ Error in {collector_name} collector: {result}"
        else:
            message = f"    - ✅ {collector_name} collector found {len(result)} events."
            all_events.extend(result)

        if spinner:
            spinner.write(message)
        else:
            console.print(message)

    return all_events


async def main() -> None:
    """Run all enabled collectors for a given date.

    Prints a unified, chronologically sorted timeline of events.
    """
    try:
        start_time, end_time, config_path = parse_arguments()
    except ValueError as e:
        console.print(f"❌ Error: {e}")
        return

    try:
        config = load_config(config_path)
    except (ConfigError, ConfigNotFoundError) as e:
        console.print(f"❌ Error loading config: {e}")
        return

    collectors = init_collectors_from_config(config)
    if len(collectors) == 0:
        console.print("No collectors are enabled in the configuration.")
        return

    target_date = start_time

    if is_interactive():
        with yaspin(
            text=f"🚀 Collecting activity for {target_date.strftime('%Y-%m-%d')}...",
            color="yellow",
        ) as spinner:
            all_events = await collect_events(collectors, start_time, end_time, spinner)
    else:
        console.print(
            f"🚀 Collecting activity for {target_date.strftime('%Y-%m-%d')}...",
        )
        all_events = await collect_events(collectors, start_time, end_time)

    if not all_events:
        console.print("\nNo activity found for the specified date.")
        return

    all_events.sort(key=lambda x: x.timestamp)
    summarized = summarize_events(all_events)

    day_map = {0: "ma", 1: "ti", 2: "ke", 3: "to", 4: "pe", 5: "la", 6: "su"}
    day_abbr = day_map[target_date.weekday()]
    target_date_str = target_date.strftime("%Y-%m-%d")
    date_str = f"{day_abbr} {target_date_str}"

    console.print(
        f"\n--- Summarized Activity Timeline for {target_date_str} ---\n",
    )
    local_tz = target_date.tzinfo
    for event in summarized:
        print_formatted_event(event, date_str, local_tz)


def _main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())  # pragma: no cover


if __name__ == "__main__":
    _main()  # pragma: no cover
