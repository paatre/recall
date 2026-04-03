import argparse
import asyncio
import contextlib
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.tree import Tree
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


def parse_arguments() -> tuple[datetime, datetime, Path | None, bool, str | None, bool]:
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
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output the raw event timeline instead of generating a timesheet.",
    )
    parser.add_argument(
        "--model",
        help="LLM model to use for timesheets (e.g. gpt-4o, gpt-4o-mini).",
        default=None,
    )
    parser.add_argument(
        "--no-events",
        action="store_true",
        help="Hide the underlying raw events beneath each timesheet block.",
    )
    args = parser.parse_args()

    try:
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
        ).astimezone()
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
        return (
            start_datetime,
            end_datetime,
            args.config,
            args.raw,
            args.model,
            args.no_events,
        )


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


def _get_source_color(source: str) -> str:
    """Return a distinct rich color for a given event source."""
    color_map = {
        "Slack": "#ECB22E",
        "Firefox": "#FF6611",
        "GitLab": "#FC6D2D",
        "Shell": "#4eaa25",
        "Calendar": "#4285F4",
    }
    return color_map.get(source, "white")


def print_formatted_event(event: Event, date_str: str) -> None:
    """Print a formatted event, with special handling for Slack and GitLab."""
    local_timestamp = event.timestamp.astimezone()
    color = _get_source_color(event.source)
    source = f"[[{color}]{event.source}[/]]"
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


async def process_and_display_date(  # noqa: PLR0913
    start_time: datetime,
    end_time: datetime,
    collectors: list[BaseCollector],
    *,
    raw_output: bool,
    model: str | None,
    no_events: bool,
    llm_config: dict[str, Any],
) -> None:
    """Process and display events for a given date."""
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

    day_abbr = target_date.strftime("%a")
    target_date_str = target_date.strftime("%Y-%m-%d")
    date_str = f"{day_abbr} {target_date_str}"

    if raw_output:
        _display_raw_events(summarized, target_date_str, date_str)
    else:
        _generate_and_display_timesheet(
            summarized,
            target_date_str,
            model,
            llm_config,
            no_events,
        )


def _display_raw_events(
    summarized: list[Event],
    target_date_str: str,
    date_str: str,
) -> None:
    with console.pager(styles=True):
        console.print(
            f"\n--- Summarized Activity Timeline for {target_date_str} ---\n",
        )
        for event in summarized:
            print_formatted_event(event, date_str)


def _generate_and_display_timesheet(
    summarized: list[Event],
    target_date_str: str,
    model: str | None,
    llm_config: dict[str, Any],
    no_events: bool,  # noqa: FBT001
) -> None:
    timesheet = None
    provider = llm_config.get("provider", "github").capitalize()

    if is_interactive():
        with yaspin(
            text=f"🤖 Generating timesheet with {provider}...",
            color="cyan",
        ) as spinner:
            try:
                from .llm import generate_timesheet  # noqa: PLC0415

                timesheet = generate_timesheet(
                    summarized,
                    target_date_str,
                    llm_config,
                    model,
                )
                spinner.ok("✅ ")
            except Exception as e:  # noqa: BLE001
                spinner.fail("❌ ")
                console.print(f"Error generating timesheet: {e}")
                return
    else:
        console.print(f"🤖 Generating timesheet with {provider}...")
        try:
            from .llm import generate_timesheet  # noqa: PLC0415

            timesheet = generate_timesheet(
                summarized,
                target_date_str,
                llm_config,
                model,
            )
        except Exception as e:  # noqa: BLE001
            console.print(f"❌ Error generating timesheet: {e}")
            return

    with console.pager(styles=True):
        console.print(
            f"\n--- Timesheet Draft for {target_date_str} ---\n",
        )
        if not timesheet:
            console.print("No timesheet blocks were generated.")
        else:
            for block in timesheet:
                start = block.get("start_time", "??:??")
                end = block.get("end_time", "??:??")
                dur = block.get("duration_hours", 0)
                ctx = block.get("context", "Unknown")
                desc = block.get("description", "")

                header_text = f"[{start} - {end}] ({dur}h) | Context: {ctx}"

                tree = Tree(f'↳ "{desc}"')
                if not no_events:
                    for e in block.get("_events", []):
                        time_str = e.timestamp.astimezone().strftime("%H:%M:%S")
                        color = _get_source_color(e.source)
                        tree.add(
                            f"[{time_str}] [[{color}]{e.source}[/]] {e.description}",
                        )

                panel = Panel(
                    tree,
                    title=header_text,
                    title_align="left",
                    border_style="cyan",
                )
                console.print(panel)
                console.print()


async def main() -> None:  # noqa: C901
    """Run all enabled collectors for a given date.

    Prints a unified, chronologically sorted timeline of events.
    """
    os.environ["PAGER"] = "less -X -F -R"
    try:
        (
            start_time,
            end_time,
            config_path,
            raw_output,
            model,
            no_events,
        ) = parse_arguments()
    except ValueError as e:
        console.print(f"❌ Error: {e}")
        return

    try:
        config = load_config(config_path)
    except ConfigNotFoundError as e:
        if config_path is None:
            from .config import (  # noqa: PLC0415
                DEFAULT_CONFIG_PATH,
                create_default_config,
            )

            create_default_config(DEFAULT_CONFIG_PATH)
            console.print(
                f"✨ Created default config at [bold cyan]{DEFAULT_CONFIG_PATH}[/].\n"
                "Please edit it to enable your sources, then run recall again.",
            )
            return

        console.print(f"❌ Error loading config: {e}")
        return
    except ConfigError as e:
        console.print(f"❌ Error loading config: {e}")
        return

    collectors = init_collectors_from_config(config)
    if len(collectors) == 0:
        console.print("No collectors are enabled in the configuration.")
        return

    llm_config = config.get("llm", {})

    current_start_time = start_time
    current_end_time = end_time

    while True:
        await process_and_display_date(
            current_start_time,
            current_end_time,
            collectors,
            raw_output=raw_output,
            model=model,
            no_events=no_events,
            llm_config=llm_config,
        )

        if not is_interactive():
            break

        prev_date = (current_start_time - timedelta(days=1)).strftime("%Y-%m-%d")
        next_date = (current_start_time + timedelta(days=1)).strftime("%Y-%m-%d")

        answer = Prompt.ask(
            f"\nView another day? \\[p]revious ({prev_date}) | "
            f"\\[n]ext ({next_date}) | \\[q]uit",
            choices=["p", "n", "q"],
            default="q",
        )

        if answer == "q":
            break
        if answer == "p":
            current_start_time -= timedelta(days=1)
            current_end_time -= timedelta(days=1)
        elif answer == "n":
            current_start_time += timedelta(days=1)
            current_end_time += timedelta(days=1)


def _main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())  # pragma: no cover


if __name__ == "__main__":
    _main()  # pragma: no cover
