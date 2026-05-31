from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("~/.config/recall/config.yaml").expanduser()

DEFAULT_CONFIG_CONTENT = """\
sources:
  - id: "Firefox"
    type: "firefox"
    enabled: true
    config: {}

  - id: "Calendar"
    type: "gcalendar"
    enabled: true
    config: {}

  - id: "GitLab"
    type: "gitlab"
    enabled: true
    config:
      url: ""
      private_token: ""
      user_id: 0

  - id: "Shell"
    type: "shell"
    enabled: true
    config: {}

  - id: "Slack"
    type: "slack"
    enabled: true
    config:
      user_token: ""

llm:
  provider: "github" # "github", "openai", or "custom"
  model: ""          # Optional. Model to use (e.g. gpt-4o, llama3).
  api_key: ""        # Optional. If empty, uses 'gh' CLI for github, or OPENAI_API_KEY
  base_url: ""       # Optional. Set to override default API endpoint
  events_per_chunk: 150
  max_event_description_length: 200
  custom_instructions: ""
"""


class ConfigError(Exception):
    """Base exception for configuration errors."""


class ConfigNotFoundError(ConfigError, FileNotFoundError):
    """Raised when the configuration file cannot be found."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Configuration file not found at {path}")


def create_default_config(path: Path) -> None:
    """Create the default configuration file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_CONTENT)


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load and parse the YAML configuration file."""
    if not config_path:
        config_path = DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise ConfigNotFoundError(config_path)

    try:
        with config_path.open("r") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        msg = f"Error loading or parsing config file at {config_path}: {e}"
        raise ConfigError(msg) from e
