import os.path
from datetime import datetime, timezone
from typing import List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import BaseCollector, Event

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class GoogleCalendarCollector(BaseCollector):
    """Collects events from the user's primary Google Calendar."""

    def name(self) -> str:
        return "Calendar"

    def _get_credentials(self) -> Credentials:
        """Handles the OAuth2 flow to get valid user credentials."""
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
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
                # For all-day events, 'dateTime' is not present.
                start_str = event_data["start"].get(
                    "dateTime", event_data["start"].get("date")
                )
                event_ts = datetime.fromisoformat(start_str)

                # Ensure the timestamp is timezone-aware (UTC) for proper comparison
                if event_ts.tzinfo is None:
                    event_ts = event_ts.replace(tzinfo=timezone.utc)

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
