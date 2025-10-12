from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from recall.config import ConfigError, ConfigNotFoundError, load_config


@pytest.fixture
def mock_config_file(tmp_path: Path) -> Path:
    """Fixture to create a temporary config file."""
    config_content = """
sources:
  - id: "test_source"
    type: "test"
    enabled: true
    config:
      key: "value"
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)
    return config_path


def test_load_config_success(mock_config_file: Path):
    """Test that a valid config file is loaded and parsed correctly."""
    config = load_config(mock_config_file)
    assert "sources" in config
    assert len(config["sources"]) == 1
    assert config["sources"][0]["id"] == "test_source"


def test_load_config_not_found():
    """Test that ConfigNotFoundError is raised for a non-existent file."""
    non_existent_path = Path("/non/existent/path/config.yaml")
    with pytest.raises(ConfigNotFoundError):
        load_config(non_existent_path)


def test_load_config_yaml_error(tmp_path: Path):
    """Test that ConfigError is raised for a malformed YAML file."""
    malformed_content = "sources: [id: 'test',"
    config_path = tmp_path / "malformed.yaml"
    config_path.write_text(malformed_content)
    with pytest.raises(ConfigError, match="Error loading or parsing config file"):
        load_config(config_path)


@patch("pathlib.Path.open", new_callable=mock_open)
@patch("pathlib.Path.exists", return_value=True)
def test_load_config_io_error(mock_exists, mock_open_file):
    """Test that ConfigError is raised on IOError."""
    mock_open_file.side_effect = yaml.YAMLError("yaml error")
    with pytest.raises(ConfigError):
        load_config(Path("/fake/path.yaml"))