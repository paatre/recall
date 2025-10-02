import os.path
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import BaseCollector, Event

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CONFIG_DIR = Path.home() / ".config" / "work-activity-aggregator"
TOKEN_PATH = CONFIG_DIR / "token.json"
CREDS_PATH = CONFIG_DIR / "credentials.json"


class GoogleCalendarCollector(BaseCollector):
    """Collects events from the user's primary Google Calendar."""

    def name(self) -> str:
        return "Calendar"

    def _get_credentials(self) -> Credentials:
        """Handles the OAuth2 flow to get valid user credentials."""
        creds = None

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)

            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return creds

    async def collect(self, start_time: datetime, end_time: datetime) -> List[Event]:
        """
        Connects to the Google Calendar API and fetches events for the specified day.
        """
        try:
            creds = self._get_credentials()
            service = build("calendar", "v3", credentials=creds)

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=start_time.isoformat(),
                    timeMax=end_time.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            api_events = events_result.get("items", [])

            if not api_events:
                return []

            events = []
            for event_data in api_events:
                if 'dateTime' in event_data["start"]:
                    start_str = event_data["start"]["dateTime"]
                    event_ts = datetime.fromisoformat(start_str)
                else:
                    date_str = event_data["start"]["date"]
                    event_ts = datetime.fromisoformat(f"{date_str}T12:00:00Z")

                events.append(
                    Event(
                        timestamp=event_ts,
                        source=self.name(),
                        description=f"Meeting: {event_data['summary']}",
                        url=event_data.get("htmlLink"),
                    )
                )
            return events

        except HttpError as error:
            raise ConnectionError(f"An API error occurred: {error}") from error
        except FileNotFoundError:
            raise FileNotFoundError(
                "Could not find credentials.json. Please follow setup instructions."
            )
