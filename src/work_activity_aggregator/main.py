import os
import asyncio
import argparse
from datetime import datetime, timezone
import sys

from dotenv import load_dotenv
from yaspin import yaspin
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .collectors.base import BaseCollector, Event
from .collectors.firefox import FirefoxCollector
from .collectors.gcalendar import GoogleCalendarCollector
from .collectors.gitlab import GitLabCollector
from .collectors.shell import ShellCollector
from .collectors.slack import SlackCollector
from .utils.summarizer import summarize_events

ENABLED_COLLECTORS: list[type[BaseCollector]] = [
    FirefoxCollector,
    GoogleCalendarCollector,
    GitLabCollector,
    ShellCollector,
    SlackCollector,
]
GLOBAL_CONFIG_PATH = os.path.expanduser("~/.config/work-activity-aggregator/config.env")

console = Console()


def parse_arguments() -> datetime:
    """
    Parses command-line arguments to get the target date.
    """
    parser = argparse.ArgumentParser(
        description="Collect activity data from various sources for a specific date."
    )
    parser.add_argument(
        "date",
        nargs="?",
        help="The date to collect data for in YYYY-MM-DD format. Defaults to today.",
        default=(datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
    )
    args = parser.parse_args()

    try:
        return datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Please use YYYY-MM-DD.")


def is_interactive() -> bool:
    """
    Checks if the script is running in an interactive terminal.
    """
    return sys.stdout.isatty()


def print_formatted_event(event: Event, date_str: str, local_tz):
    """Prints a formatted event, with special handling for Slack and GitLab."""
    local_timestamp = event.timestamp.astimezone(local_tz)
    source_padded = f"[{event.source}]"
    duration_str = (
        f"({event.duration_minutes} min)"
        if event.duration_minutes and event.duration_minutes > 1
        else ""
    )
    description_short = event.description or ""

    is_special_case = (
        "Message in" in description_short or "Commented on" in description_short
    ) and is_interactive()

    if is_special_case:
        try:
            header, content = description_short.split("\n\n", 1)
            print(
                f"[{date_str} {local_timestamp.strftime('%H:%M:%S')}] {source_padded} {header.strip()}"
            )

            text_to_render = Text(content.strip(), justify="left")
            panel = Panel(text_to_render, border_style="cyan", expand=False)
            console.print(panel)
        except ValueError:
            is_special_case = False

    if not is_special_case:
        print(
            f"[{date_str} {local_timestamp.strftime('%H:%M:%S')}] "
            f"{source_padded} "
            f"{description_short.strip()} "
            f"{duration_str} "
        )

    if event.url:
        print(f"↳ {event.url}")

    print()


async def collect_events(
    collectors: list[BaseCollector],
    start_time: datetime,
    end_time: datetime,
    spinner=None,
) -> list[Event]:
    """
    Gathers events from all collectors.
    """
    tasks = [collector.collect(start_time, end_time) for collector in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_events = []
    for i, result in enumerate(results):
        collector_name = collectors[i].name()
        message = ""
        if isinstance(result, Exception) or isinstance(result, BaseException):
            message = f"    - ❌ Error in {collector_name} collector: {result}"
        else:
            message = f"    - ✅ {collector_name} collector found {len(result)} events."
            all_events.extend(result)

        if spinner:
            spinner.write(message)
        else:
            print(message)

    return all_events


async def main():
    """
    Initializes and runs all enabled collectors for a given date,
    then prints a unified, chronologically sorted timeline of events.
    """
    # Load global config file if it exists, meant to read user-specific setting
    if os.path.exists(GLOBAL_CONFIG_PATH):
        load_dotenv(GLOBAL_CONFIG_PATH)

    # Load local .env file if it exists, meant to read project-specific setting
    # during development or testing
    load_dotenv(override=True)

    try:
        target_date = parse_arguments()
    except ValueError as e:
        print(f"❌ Error: {e}")
        return

    start_time = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )
    end_time = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        23,
        59,
        59,
        tzinfo=timezone.utc,
    )

    collectors = [cls() for cls in ENABLED_COLLECTORS]

    if is_interactive():
        with yaspin(
            text=f"🚀 Collecting activity for {target_date.strftime('%Y-%m-%d')}...",
            color="yellow",
        ) as spinner:
            all_events = await collect_events(collectors, start_time, end_time, spinner)
    else:
        print(f"🚀 Collecting activity for {target_date.strftime('%Y-%m-%d')}...")
        all_events = await collect_events(collectors, start_time, end_time)

    if not all_events:
        print("\nNo activity found for the specified date.")
        return

    all_events.sort(key=lambda x: x.timestamp)
    summarized = summarize_events(all_events)

    day_map = {0: "ma", 1: "ti", 2: "ke", 3: "to", 4: "pe", 5: "la", 6: "su"}
    day_abbr = day_map[target_date.weekday()]
    date_str = f"{day_abbr} {target_date.strftime('%Y-%m-%d')}"

    print(
        f"\n--- Summarized Activity Timeline for {target_date.strftime('%Y-%m-%d')} ---\n"
    )
    local_tz = datetime.now().astimezone().tzinfo
    for event in summarized:
        print_formatted_event(event, date_str, local_tz)


def _main():
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
