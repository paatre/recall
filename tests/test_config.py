import textwrap
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from recall.config import ConfigError, ConfigNotFoundError, load_config


@pytest.fixture
def mock_config_file_content() -> str:
    """Fixture to provide valid config content."""
    return textwrap.dedent("""
        sources:
          - id: "test_source"
            type: "test"
            enabled: true
            config:
              key: "value"
    """)


def test_load_config_success(fs: FakeFilesystem, mock_config_file_content: str):
    """Test that a valid config file is loaded and parsed correctly."""
    config_path = "/fake/path/config.yaml"
    fs.create_file(config_path, contents=mock_config_file_content)

    config = load_config(Path(config_path))

    assert "sources" in config
    assert len(config["sources"]) == 1
    assert config["sources"][0]["id"] == "test_source"


@pytest.mark.usefixtures("fs")
def test_load_config_not_found():
    """Test that ConfigNotFoundError is raised for a non-existent file."""
    non_existent_path = Path("/non/existent/path/config.yaml")

    with pytest.raises(ConfigNotFoundError):
        load_config(non_existent_path)


def test_load_config_yaml_error(fs: FakeFilesystem):
    """Test that ConfigError is raised for a malformed YAML file."""
    config_path = "/fake/path/malformed.yaml"
    malformed_content = "sources: [id: 'test',"
    fs.create_file(config_path, contents=malformed_content)

    with pytest.raises(ConfigError, match="Error loading or parsing config file"):
        load_config(Path(config_path))


def test_load_config_io_permission_error(fs: FakeFilesystem):
    """Test that ConfigError is raised on a file access error."""
    config_path = "/fake/path/restricted.yaml"
    fs.create_file(config_path, contents="sources: []", st_mode=0o000)

    with pytest.raises(ConfigError, match="Error loading or parsing config file"):
        load_config(Path(config_path))
