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
