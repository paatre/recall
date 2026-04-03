# AI Agent Guidelines

This file contains instructions and rules for AI agents operating within this repository.

## Core Rules

1. **NO-COMMIT RULE (CRITICAL)**
   - You must **NEVER** create git commits unless explicitly and directly instructed to do so by the user.
   - Always leave your modifications in the working directory (unstaged or staged) so the user can review them before committing.

2. **Testing**
   - The project uses `pytest`. Run tests using `uv run pytest`. Run `uv run nox` to run all tests across all Python versions.
   - Ensure all tests pass before presenting your solution.
   - If you add a feature or fix a bug, add or update relevant tests.
   - For tests involving time, ensure timezone independence by using `time_machine` or mocking the `TZ` environment variable (with `time.tzset()`).

3. **Linting and Formatting**
   - The project uses `ruff` for linting and formatting.
   - Run `uv run ruff check .` to check for linting errors.
   - Run `uv run ruff check --fix .` to automatically fix linting errors.
   - Run `uv run ruff format .` to format the code.

4. **Environment and Dependency Management**
   - This project is managed using `uv`.
   - Do not use `pip` or `poetry` directly unless necessary. Rely on `uv run` for executing commands within the virtual environment.

5. **Style and Architecture**
   - Follow existing code style and conventions.
   - Use Python type hints thoroughly.
   - Match the tone and architecture of existing collectors and utilities.

## Project Structure

Below is an overview of the project's file hierarchy:

```text
.
├── src/
│   └── recall/
│       ├── collectors/      # Modules that fetch data from different sources
│       │   ├── base.py      # Abstract base class for all collectors
│       │   ├── firefox.py   # Firefox history collector
│       │   ├── gcalendar.py # Google Calendar events collector
│       │   ├── gitlab.py    # GitLab activity collector
│       │   ├── shell.py     # Shell history collector
│       │   └── slack.py     # Slack message collector
│       ├── prompts/         # Templates for LLM prompts
│       │   └── timesheet.md # Prompt for generating timesheets
│       ├── utils/           # Helper functions
│       │   └── summarizer.py# Logic for grouping and summarizing events
│       ├── config.py        # Configuration loading and parsing
│       ├── llm.py           # LLM interaction logic
│       └── main.py          # CLI entry point and main orchestrator
├── tests/                   # Unit tests mirroring the src/ structure
│   ├── collectors/          # Tests for individual collectors
│   ├── conftest.py          # Pytest fixtures
│   ├── test_config.py       # Tests for configuration parsing
│   ├── test_main.py         # Tests for main execution flow
│   └── test_summarizer.py   # Tests for event summarization
├── config.yaml.tpl          # Template for the user configuration file
├── noxfile.py               # Configuration for testing across Python versions
├── pyproject.toml           # Project metadata and dependencies
└── uv.lock                  # Locked dependencies managed by uv
```

### Explanations:
* **`src/recall/collectors/`**: The core data gathering logic. To add a new source (e.g., Jira, GitHub), you create a new file here that inherits from `BaseCollector` (in `base.py`).
* **`src/recall/main.py`**: The entry point. It parses CLI arguments, loads the configuration, initializes the active collectors, gathers the events, and formats the output (or passes it to the LLM).
* **`tests/`**: Uses `pytest`. The structure perfectly mirrors `src/recall/`, ensuring every collector and utility has corresponding test coverage.
* **`pyproject.toml` / `uv.lock`**: Define the project environment and dependencies, using `uv` as the package manager.
* **`noxfile.py`**: Configures `nox` to run the test suite across multiple Python versions (3.10 through 3.14).
