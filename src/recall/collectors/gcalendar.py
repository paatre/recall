from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import BaseCollector, Event

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CONFIG_DIR = Path.home() / ".config" / "recall"
TOKEN_PATH = CONFIG_DIR / "token.json"
CREDS_PATH = CONFIG_DIR / "credentials.json"


class GoogleCalendarCredentialsError(FileNotFoundError):
    """Raised when the credentials.json file is missing or invalid."""

    def __init__(self) -> None:
        super().__init__(
            "Could not find a valid credentials.json. "
            "Please follow setup instructions.",
        )


class GoogleCalendarCollector(BaseCollector):
    """Collects events from the user's primary Google Calendar."""

    def name(self) -> str:
        """Return the name of the collector."""
        return "Calendar"

    def _get_credentials(self) -> Credentials:
        """Handle the OAuth2 flow to get valid user credentials."""
        creds = None

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if Path(TOKEN_PATH).exists():
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)

            with Path.open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
        return creds

    async def collect(self, start_time: datetime, end_time: datetime) -> list[Event]:
        """Collect Google Calendar events for a specified day."""
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
                if "dateTime" in event_data["start"]:
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
                    ),
                )
        except HttpError as http_error:
            msg = f"An API error occurred: {http_error}"
            raise ConnectionError(msg) from http_error
        except FileNotFoundError as file_error:
            raise GoogleCalendarCredentialsError from file_error
        else:
            return events
