import configparser
import platform
import sqlite3

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .base import BaseCollector, Event


class FirefoxCollector(BaseCollector):
    """Collects browsing history by reading profiles.ini to find the correct database."""

    def name(self) -> str:
        return "Firefox"

    def _get_db_path(self) -> Optional[Path]:
        """Finds the places.sqlite file by parsing profiles.ini."""
        system = platform.system()
        home = Path.home()

        possible_base_paths = []
        if system == "Linux":
            possible_base_paths.append(home / "snap/firefox/common/.mozilla/firefox")
            possible_base_paths.append(home / ".mozilla/firefox")
        elif system == "Darwin":
            possible_base_paths.append(home / "Library/Application Support/Firefox")
        elif system == "Windows":
            possible_base_paths.append(home / "AppData/Roaming/Mozilla/Firefox")
        else:
            return None

        for firefox_base_path in possible_base_paths:
            profiles_ini = firefox_base_path / "profiles.ini"
            if not profiles_ini.exists():
                continue

            config = configparser.ConfigParser()
            config.read(profiles_ini)

            found_profiles = []
            for section in config.sections():
                if section.startswith("Profile"):
                    profile_path_str = config[section].get("Path")
                    profile_name = config[section].get("Name")
                    if not profile_path_str or not profile_name:
                        continue

                    is_relative = config[section].getint("IsRelative", 1) == 1
                    profile_path = (
                        firefox_base_path / profile_path_str
                        if is_relative
                        else Path(profile_path_str)
                    )

                    priority = 0 if "nightly" in profile_name.lower() else 1
                    found_profiles.append((priority, profile_name, profile_path))

            found_profiles.sort()

            for priority, name, path in found_profiles:
                db_file = path / "places.sqlite"
                if db_file.exists():
                    return db_file  # Success! We found it.

        return None  # If we loop through all paths and find nothing.

    async def collect(self, start_time: datetime, end_time: datetime) -> List[Event]:
        """Connects to the DB and fetches history within the time range."""
        db_path = self._get_db_path()
        if not db_path:
            raise FileNotFoundError(
                "Could not find a valid Firefox places.sqlite database from profiles.ini."
            )

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
                    visit_date_micro / 1_000_000, tz=timezone.utc
                )
                events.append(
                    Event(
                        timestamp=ts,
                        source=self.name(),
                        description=f"{title}",
                        url=url,
                    )
                )
            con.close()
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to query Firefox history: {e}") from e

        return events
