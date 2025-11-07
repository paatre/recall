# Recall

This tool collects your activity from various sources and generates a
summarized, chronological timeline for a specific day. It's designed to give
you a "perfect memory" of what you've worked on, making it easier to fill out
timesheets, write progress reports, or simply reflect on your day.

## Prerequisites

- Python 3.10 or higher
- `uv` tool for building and installing the package, and also for development
  purposes
- Access to the data sources you want to collect activity from (e.g., Google
Calendar, GitLab, Slack, etc.) and the necessary permissions to read the data

## Collectors

These are the data sources currently supported:

- Firefox browsing history
- Google Calendar events
- GitLab activity
- Slack messages
- Shell command history

## Installation and usage

### Clone the repository

```bash
git clone https://github.com/paatre/recall.git
cd recall
```

### Install the package

There are multiple ways to install the package but the recommended way is to
is to use `uv tool`.

Using `uv tool`:
```
uv tool install .
```

This will create a command line tool called `recall` which
gets installed into your `$HOME/.local/bin` directory so you can run it from
anywhere.

Alternatively, you can install the tool with something like `pipx`.

### Usage

After installation, you can run the tool using:

```bash
recall
```

The tool will generate a timeline for today's activity by default. You can also
specify a date in `YYYY-MM-DD` format to get the activity for that specific day.

```bash
recall 2025-01-01
```

### Example output

```
$ recall YYYY-MM-DD
    - ✅ Firefox collector found X events.
    - ✅ Calendar collector found X events.
    - ✅ GitLab collector found X events.
    - ✅ Shell collector found X events.
    - ✅ Slack collector found X events.

--- Summarized Activity Timeline for YYYY-MM-DD ---

[day YYYY-MM-DD 09:02:15] [Calendar] Meeting: Daily Stand-up (15 min)
↳ https://calendar.google.com/calendar/r/eventedit/xxxxxxxx

[day YYYY-MM-DD 09:17:30] [Shell] git status

[day YYYY-MM-DD 09:18:05] [GitLab] Pushed 2 commit(s) to branch 'feature/new-api-endpoint'
↳ https://gitlab.com/your-group/your-project/-/commits/feature/new-api-endpoint

[day YYYY-MM-DD 09:25:11] [Firefox] How to implement asyncio in Python - Google Search
↳ https://www.google.com/search?q=how+to+implement+asyncio+in+python

[day YYYY-MM-DD 10:45:03] [Slack] Message in #development-team:
┌───────────────────────────────────────────────────────────────────────────┐
│ @here Could someone please review my latest merge request? It's ready for │
│ testing.                                                                  │
└───────────────────────────────────────────────────────────────────────────┘
↳ https://your-workspace.slack.com/archives/C0XXXXXXX/p1664811903000000

[day YYYY-MM-DD 11:30:55] [GitLab] Commented on merge_request:
┌───────────────────────────────────────────────────────────────────────────┐
│ Looks good overall! Just one minor suggestion regarding the error         │
│ handling.                                                                 │
└───────────────────────────────────────────────────────────────────────────┘
↳ https://gitlab.com/your-group/your-project/-/merge_requests/123#note_987654

[day YYYY-MM-DD 14:00:20] [Shell] docker-compose up --build -d

[day YYYY-MM-DD 14:10:48] [Firefox] Project Dashboard - Jira
↳ https://your-company.atlassian.net/jira/software/projects/PROJ/boards/1
```

## Configuration

The tool uses a combination of environment variables and configuration files.

### Global configuration file

Create a global configuration file to the `.config` directory in your home
directory:

```bash
mkdir -p ~/.config/recall
touch ~/.config/recall/config.env
```

Add your secrets to this `config.env` file. Read the following section section
for collector-specific setup instructions.

The tool also supports loading environment variables from a `.env` file in the
current working directory. This is useful for testing and development purposes.

### Collector-specific configurations

This section describes the setup required for each collector.

#### Google Calendar

- Follow the [Google Calendar API Python Quickstart](https://developers.google.com/calendar/api/quickstart/python)
to enable the API, configure the OAuth consent screen and download your
`credentials.json`.
- Place the `credentials.json` file in `~/.config/recall/`.
- The first time you run the tool, it will open a browser window for you to
authorize access. This will create a `token.json` and store it in the
`~/.config/recall/` directory for future runs so that you
don't need to authorize again.

#### GitLab

Add the following to your `config.env` file:

```
GITLAB_URL="https://your.gitlab-instance.com"
GITLAB_PRIVATE_TOKEN="your_personal_access_token"
GITLAB_USER_ID="your_gitlab_user_id"
```

#### Slack

> [!note]
> This collector is not available yet to public use. This is currently being
> tested internally.

- You need a Slack User Token. You can generate one for your workspace.
- Add the following to your `config.env` file:

```
SLACK_USER_TOKEN="xoxp-..."
```

#### Shell history

This collector reads from a custom history file located at
`~/.recall.log` by default. This is required to generate
timestamps even if the commands are executed in different shells (e.g., when
using `tmux`). It is recommended to add these lines to your `.bashrc` to
ensure this:

```bash
HISTTIMEFORMAT="%Y-%m-%dT%H:%M:%S%z "

export PROMPT_LOG_FILE="$HOME/.recall_shell_history.log"

log_prompt_command() {
    local last_command=$(history 1)
    if [[ "$last_command" =~ ^[[:space:]]*[0-9]+[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+?[0-9]{4}[[:space:]]+(.*) ]]; then
        local command_to_log="${BASH_REMATCH[1]}"
        local current_time=$(date +"%Y-%m-%dT%H:%M:%S%z")
        echo "$current_time $command_to_log" >> "$PROMPT_LOG_FILE"
    fi
}

export PROMPT_COMMAND="log_prompt_command"
```

#### Firefox

No special configuration is needed. The collector automatically tries to find
your Firefox `places.sqlite` database.

Here are the default locations that are supported currently:

- Linux: `~/.mozilla/firefox/` or `snap/firefox/common/.mozilla/firefox`
- macOS: `Library/Application Support/Firefox`
- Windows: `AppData/Roaming/Mozilla/Firefox/Profiles`

## Extending the Tool

You can easily add new data sources by creating a new collector.

1. Create a new file in the `src/recall/collectors/` directory (e.g., `my_collector.py`).
2. In this file, create a class that inherits from `BaseCollector` (from `collectors/base.py`).
3. Implement the `name()` and `collect()` methods. The `collect()` method must be `async` and return a list of `Event` objects.
4. Add your new collector class to the `ENABLED_COLLECTORS` list in `src/recall/main.py`.

## Contributing

Contributions are welcome! Especially in the form of new collectors for new
data sources. This project started as a personal tool but hopefully others will
find it useful too with more data sources.

Please fork the repository and create a pull request with your changes. Make
sure to follow the existing code style. For example, use Ruff for linting and
formatting. Keeping test coverage high and writing tests for new features is
also appreciated. You can run the tests using:

```bash
uv run pytest
```

You can also use the convenient `pytest-watcher` to automatically run tests on
file changes:

```bash
uv run ptw
```
