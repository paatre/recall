from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("~/.config/recall/config.yaml").expanduser()


class ConfigError(Exception):
    """Base exception for configuration errors."""


class ConfigNotFoundError(ConfigError, FileNotFoundError):
    """Raised when the configuration file cannot be found."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Configuration file not found at {path}")


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
