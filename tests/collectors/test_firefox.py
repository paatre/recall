import platform
import sqlite3
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from recall.collectors.firefox import (
    FirefoxCollector,
    FirefoxDatabaseNotFoundError,
)
from tests.utils import make_dt


@pytest.fixture
def collector() -> FirefoxCollector:
    """Fixture for the Firefox Collector instance."""
    return FirefoxCollector()


@pytest.fixture
def mock_profiles() -> dict:
    """Provide a mock profiles.ini content for Firefox."""
    return {
        "Profile0": {"Name": "default", "Path": "a.default", "IsRelative": "1"},
        "Profile1": {"Name": "Nightly", "Path": "b.nightly", "IsRelative": "1"},
        "Profile2": {
            "Name": "absolute",
            "Path": "/opt/firefox/absolute",
            "IsRelative": "0",
        },
    }


@pytest.fixture
def mock_platform_system(monkeypatch: pytest.MonkeyPatch):
    """Mock platform.system() to return a mock OS."""

    def _mock_system(os_name: str) -> None:
        monkeypatch.setattr(platform, "system", lambda: os_name)

    return _mock_system


def test_get_base_paths_linux(
    collector: FirefoxCollector,
    mock_platform_system: Callable,
):
    """Verify standard base paths are returned for Linux."""
    mock_platform_system("Linux")
    paths = collector._get_base_paths()
    home = Path.home()

    expected_paths = [
        home / "snap/firefox/common/.mozilla/firefox",
        home / ".mozilla/firefox",
    ]
    assert paths == expected_paths


@patch("configparser.ConfigParser")
def test_parse_profiles_relative_and_priority(
    mock_config_parser: MagicMock,
    mock_profiles: dict,
    collector: FirefoxCollector,
    mock_temp_home: Path,
):
    """Test parsing profiles.ini for relative paths and priority sorting."""

    def mock_get_item(section: str) -> MagicMock:
        mock_section = MagicMock()
        mock_section.get.side_effect = lambda option: mock_profiles.get(
            section,
            {},
        ).get(option)
        mock_section.getint.side_effect = lambda option, default: int(
            mock_profiles.get(section, {}).get(option, default),
        )

        return mock_section

    mock_config_parser.return_value.__getitem__.side_effect = mock_get_item
    mock_config_parser.return_value.sections.return_value = mock_profiles.keys()
    mock_config_parser.return_value.read.return_value = None

    mock_ini_path = mock_temp_home / "firefox-profiles" / "profiles.ini"

    results = collector._parse_profiles(mock_ini_path)

    assert len(results) == 3

    assert results[0][1] == "Nightly"
    assert results[0][0] == 0
    assert results[0][2] == mock_temp_home / "firefox-profiles" / "b.nightly"

    assert results[1][1] == "absolute"
    assert results[1][2] == Path("/opt/firefox/absolute")

    assert results[2][1] == "default"
    assert results[2][2] == mock_temp_home / "firefox-profiles" / "a.default"


@patch.object(FirefoxCollector, "_get_base_paths", return_value=[Path("/mock/path")])
@patch("pathlib.Path.exists")
def test_get_db_path_not_found(
    mock_path_exists: MagicMock,
    mock_get_base_paths: MagicMock,
    collector: FirefoxCollector,
):
    """Test returns None if profiles.ini or places.sqlite are missing."""
    mock_path_exists.return_value = False
    assert collector._get_db_path() is None
    mock_get_base_paths.assert_called_once()


@patch.object(FirefoxCollector, "_get_base_paths")
@patch.object(FirefoxCollector, "_parse_profiles")
@patch.object(Path, "exists")
def test_get_db_path_success(
    mock_path_exists: MagicMock,
    mock_parse_profiles: MagicMock,
    mock_base_paths: MagicMock,
    collector: FirefoxCollector,
):
    """Test returns the correct DB path when files exist."""
    profile_path = Path("/mock/base/profile_dir")
    mock_path_exists.side_effect = [True, True]
    mock_parse_profiles.return_value = [(1, "default", profile_path)]
    mock_base_paths.return_value = [Path("/mock/base")]

    result = collector._get_db_path()
    assert result == profile_path / "places.sqlite"


@pytest.mark.asyncio
async def test_collect_raises_database_not_found(
    collector: FirefoxCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that collect raises the custom error if the DB path is missing."""
    monkeypatch.setattr(collector, "_get_db_path", lambda: None)

    with pytest.raises(FirefoxDatabaseNotFoundError):
        await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("sqlite3.connect")
async def test_collect_raises_connection_error_on_db_fail(
    mock_connect: MagicMock,
    collector: FirefoxCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that SQLite connection/execution errors are wrapped in a ConnectionError."""
    monkeypatch.setattr(collector, "_get_db_path", lambda: Path("/fake/db.sqlite"))
    mock_connect.side_effect = sqlite3.Error("Test DB Error")

    with pytest.raises(ConnectionError, match="Failed to query Firefox history"):
        await collector.collect(make_dt(0), make_dt(60))


@pytest.mark.asyncio
@patch("sqlite3.connect")
async def test_collect_successful_query(
    mock_connect: MagicMock,
    collector: FirefoxCollector,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that successful query results are converted to Event objects correctly."""
    monkeypatch.setattr(collector, "_get_db_path", lambda: Path("/fake/db.sqlite"))

    mock_cursor = MagicMock()
    ts_micros_1 = int(make_dt(10).timestamp() * 1_000_000)
    ts_micros_2 = int(make_dt(15).timestamp() * 1_000_000)

    mock_cursor.execute.return_value = [
        (ts_micros_1, "Project Dashboard - Jira", "https://jira.com"),
        (ts_micros_2, "Async Python Guide", "https://docs.python.org"),
    ]

    mock_con = MagicMock()
    mock_con.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_con

    start_time = make_dt(0)
    end_time = make_dt(60)

    events = await collector.collect(start_time, end_time)

    expected_start_micros = int(start_time.timestamp() * 1_000_000)
    expected_end_micros = int(end_time.timestamp() * 1_000_000)
    mock_cursor.execute.assert_called_once()
    assert mock_cursor.execute.call_args[0][1] == (
        expected_start_micros,
        expected_end_micros,
    )

    assert len(events) == 2
    assert events[0].source == "Firefox"
    assert events[0].description == "Project Dashboard - Jira"
    assert events[1].timestamp == make_dt(15)
