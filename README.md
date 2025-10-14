# Recall

This tool collects your activity from various sources and generates a
summarized, chronological timeline for a specific day. It's designed to give
you a "perfect memory" of what you've worked on, making it easier to fill out
timesheets, write progress reports, or simply reflect on your day.

## Prerequisites

- Python 3.9 or higher
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

## Configuration

The tool is configured using a single YAML file located at
`~/.config/recall/config.yaml`.

A template for this file is provided as `config.yaml.tpl`. You can copy this
template to `~/.config/recall/config.yaml` and edit it to your needs:

```bash
mkdir -p ~/.config/recall
cp config.yaml.tpl ~/.config/recall/config.yaml
```

The configuration file consists of a list of `sources`, where each source is a
collector with its own specific settings. You can enable or disable collectors
and provide the necessary credentials or parameters for each one.

### Collector-specific configurations

This section describes the setup required for each collector within the
`config.yaml` file.

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

Add your GitLab instance URL, private access token, and user ID to the `config`
section of the GitLab source in your `config.yaml`:

```yaml
- id: "GitLab"
  type: "gitlab"
  enabled: true
  config:
    url: "https://your.gitlab-instance.com"
    private_token: "your_personal_access_token"
    user_id: 12345
```

#### Slack

- You need a Slack User Token. You can generate one for your workspace.
- Add your Slack user token to the `config` section of the Slack source in your
`config.yaml`:

```yaml
- id: "Slack"
  type: "slack"
  enabled: true
  config:
    user_token: "xoxp-..."
```

#### Firefox

No special configuration is needed in your `config.yaml`. The collector will
automatically try to find your Firefox `places.sqlite` database.

```yaml
- id: "Firefox"
  type: "firefox"
  enabled: true
  config: {}
```

Here are the default locations that are supported currently:

- Linux: `~/.mozilla/firefox/` or `snap/firefox/common/.mozilla/firefox`
- macOS: `Library/Application Support/Firefox`
- Windows: `AppData/Roaming/Mozilla/Firefox/Profiles`

#### Shell history

This collector reads from a custom history file. By default, this is located at
`~/.recall_shell_history.log`. You can override this path in your
`config.yaml`.

```yaml
- id: "Shell"
  type: "shell"
  enabled: true
  config:
    log_file_path: "/path/to/your/custom_history.log" # Optional
```

To generate timestamps for your shell commands, it is recommended to add the
following lines to your `.bashrc` or equivalent shell configuration file:

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
