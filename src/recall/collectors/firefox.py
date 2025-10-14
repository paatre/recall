import configparser
import platform
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BaseCollector, Event


class FirefoxDatabaseNotFoundError(FileNotFoundError):
    """Raised when no valid Firefox places.sqlite database can be found."""

    def __init__(self) -> None:
        super().__init__(
            "Could not find a valid Firefox places.sqlite database from profiles.ini.",
        )


class FirefoxCollector(BaseCollector):
    """Collects Firefox browsing history.

    Reads profiles.ini from standard locations based on the OS to find
    the places.sqlite database, then queries it for history entries within
    the specified time range.
    """

    def __init__(self, config: dict) -> None:
        """Initialize the Firefox collector with its configuration."""
        super().__init__(config)

    def name(self) -> str:
        """Return the name of the collector."""
        return "Firefox"

    def _get_base_paths(self) -> list[Path]:
        """Return possible base paths for Firefox profiles based on the OS."""
        home = Path.home()
        system = platform.system()

        if system == "Linux":
            return [
                home / "snap/firefox/common/.mozilla/firefox",
                home / ".mozilla/firefox",
            ]
        if system == "Darwin":
            return [home / "Library/Application Support/Firefox"]
        if system == "Windows":
            return [home / "AppData/Roaming/Mozilla/Firefox"]
        return []

    def _parse_profiles(self, profiles_ini: Path) -> list[tuple[int, str, Path]]:
        """Parse a profiles.ini file and return candidate profiles."""
        ini_config = configparser.ConfigParser()
        ini_config.read(profiles_ini)

        results: list[tuple[int, str, Path]] = []
        firefox_base_path = profiles_ini.parent

        for section in ini_config.sections():
            if not section.startswith("Profile"):
                continue

            profile_path_str = ini_config[section].get("Path")
            profile_name = ini_config[section].get("Name")
            if not profile_path_str or not profile_name:
                continue

            is_relative = ini_config[section].getint("IsRelative", 1) == 1
            profile_path = (
                firefox_base_path / profile_path_str
                if is_relative
                else Path(profile_path_str)
            )
            priority = 0 if "nightly" in profile_name.lower() else 1
            results.append((priority, profile_name, profile_path))

        results.sort()
        return results

    def _get_db_path(self) -> Optional[Path]:
        """Find the places.sqlite file by parsing profiles.ini."""
        for base_path in self._get_base_paths():
            profiles_ini = base_path / "profiles.ini"
            if not profiles_ini.exists():
                continue

            for _, _, path in self._parse_profiles(profiles_ini):
                db_file = path / "places.sqlite"
                if db_file.exists():
                    return db_file

        return None

    async def collect(self, start_time: datetime, end_time: datetime) -> list[Event]:
        """Connect to the DB and fetches history within the time range."""
        db_path = self._get_db_path()
        if not db_path:
            raise FirefoxDatabaseNotFoundError

        start_micros = int(start_time.timestamp() * 1_000_000)
        end_micros = int(end_time.timestamp() * 1_000_000)

        query = """
            SELECT
                h.visit_date,
                p.title,
                p.url
            FROM moz_historyvisits AS h
            JOIN moz_places AS p ON h.place_id = p.id
            WHERE h.visit_date BETWEEN ? AND ?
            AND p.title IS NOT NULL AND p.title != '';
        """

        events = []
        try:
            con = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
            cur = con.cursor()
            for row in cur.execute(query, (start_micros, end_micros)):
                visit_date_micro, title, url = row
                ts = datetime.fromtimestamp(
                    visit_date_micro / 1_000_000,
                    tz=timezone.utc,
                )
                events.append(
                    Event(
                        timestamp=ts,
                        source=self.name(),
                        description=f"{title}",
                        url=url,
                    ),
                )
            con.close()
        except sqlite3.Error as e:
            msg = f"Failed to query Firefox history: {e}"
            raise ConnectionError(msg) from e

        return events
