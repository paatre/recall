from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from pyfakefs.fake_filesystem_unittest import FakeFilesystem

from recall.collectors.gcalendar import (
    GoogleCalendarCollector,
    GoogleCalendarCredentialsError,
)
from tests.utils import make_dt


@pytest.fixture
def collector(fs: FakeFilesystem) -> GoogleCalendarCollector:
    """Fixture for the GoogleCalendar Collector instance."""
    config_dir = "/fake/config"
    fs.create_dir(config_dir)
    config = {
        "config_dir": config_dir,
        "credentials_filename": "creds.json",
        "token_filename": "token.json",
    }
    return GoogleCalendarCollector(config=config)


@pytest.mark.asyncio
@patch.object(
    GoogleCalendarCollector,
    "_get_credentials",
    side_effect=FileNotFoundError,
)
async def test_collect_raises_credentials_error(
    mock_get_credentials: MagicMock,
    collector: GoogleCalendarCollector,
):
    """Test that collect raises the custom error if credentials.json is missing."""
    start_time, end_time = make_dt(0), make_dt(60)

    with pytest.raises(GoogleCalendarCredentialsError):
        await collector.collect(start_time, end_time)
    mock_get_credentials.assert_called_once()


class MockCredentials(MagicMock):
    """Mock credentials with universe_domain property.

    This is needed because the collector checks for this property during mocked tests.
    """

    @property
    def universe_domain(self):
        """Mock universe_domain property."""
        return "googleapis.com"


@pytest.mark.asyncio
@patch("recall.collectors.gcalendar.build")
@patch.object(GoogleCalendarCollector, "_get_credentials")
async def test_collect_successful(
    mock_get_credentials: MagicMock,
    mock_build: MagicMock,
    collector: GoogleCalendarCollector,
):
    """Test successful collection of events."""
    mock_get_credentials.return_value = MockCredentials()
    mock_service = MagicMock()
    mock_events_result = {
        "items": [
            {
                "summary": "Test Event",
                "start": {"dateTime": "2025-01-01T10:00:00Z"},
                "end": {"dateTime": "2025-01-01T11:00:00Z"},
                "htmlLink": "https://calendar.google.com/event",
            },
        ],
    }
    mock_service.events.return_value.list.return_value.execute.return_value = (
        mock_events_result
    )
    mock_build.return_value = mock_service

    start_time, end_time = make_dt(0), make_dt(60)
    events = await collector.collect(start_time, end_time)

    assert len(events) == 1
    assert events[0].description == "Meeting: Test Event"
    assert events[0].url == "https://calendar.google.com/event"


@pytest.mark.asyncio
@patch("recall.collectors.gcalendar.build")
@patch.object(GoogleCalendarCollector, "_get_credentials")
async def test_collect_no_events(
    mock_get_credentials: MagicMock,
    mock_build: MagicMock,
    collector: GoogleCalendarCollector,
):
    """Test that an empty list is returned when there are no events."""
    mock_get_credentials.return_value = MockCredentials()
    mock_service = MagicMock()
    mock_events_result = {"items": []}
    mock_service.events.return_value.list.return_value.execute.return_value = (
        mock_events_result
    )
    mock_build.return_value = mock_service

    start_time, end_time = make_dt(0), make_dt(60)
    events = await collector.collect(start_time, end_time)

    assert len(events) == 0


@pytest.mark.asyncio
@patch("recall.collectors.gcalendar.build")
@patch.object(GoogleCalendarCollector, "_get_credentials")
async def test_collect_all_day_event(
    mock_get_credentials: MagicMock,
    mock_build: MagicMock,
    collector: GoogleCalendarCollector,
):
    """Test that all-day events are parsed correctly."""
    mock_get_credentials.return_value = MockCredentials()
    mock_service = MagicMock()
    mock_events_result = {
        "items": [
            {
                "summary": "All-day Event",
                "start": {"date": "2025-01-01"},
                "end": {"date": "2025-01-02"},
                "htmlLink": "https://calendar.google.com/event",
            },
        ],
    }
    mock_service.events.return_value.list.return_value.execute.return_value = (
        mock_events_result
    )
    mock_build.return_value = mock_service

    start_time, end_time = make_dt(0), make_dt(1440)
    events = await collector.collect(start_time, end_time)

    assert len(events) == 1
    assert events[0].description == "Meeting: All-day Event"


@pytest.mark.asyncio
@patch("recall.collectors.gcalendar.build")
@patch.object(GoogleCalendarCollector, "_get_credentials")
async def test_collect_http_error(
    mock_get_credentials: MagicMock,
    mock_build: MagicMock,
    collector: GoogleCalendarCollector,
):
    """Test that an HttpError is wrapped in a ConnectionError."""
    mock_get_credentials.return_value = MockCredentials()
    mock_service = MagicMock()
    mock_service.events.return_value.list.return_value.execute.side_effect = HttpError(
        MagicMock(status=500),
        b"Internal Server Error",
    )
    mock_build.return_value = mock_service

    start_time, end_time = make_dt(0), make_dt(60)

    with pytest.raises(ConnectionError, match="An API error occurred"):
        await collector.collect(start_time, end_time)


@patch("recall.collectors.gcalendar.Path.open")
@patch("recall.collectors.gcalendar.InstalledAppFlow.from_client_secrets_file")
@patch("recall.collectors.gcalendar.Credentials.from_authorized_user_file")
def test_get_credentials_no_token(
    mock_creds_from_file: MagicMock,
    mock_flow_from_file: MagicMock,
    mock_path_open: MagicMock,
    fs: FakeFilesystem,
    collector: GoogleCalendarCollector,
):
    """Test the credential loading process when no token file exists."""
    fs.create_file(collector.creds_path, contents="{}")
    assert not collector.token_path.exists()

    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = MockCredentials(
        token="new_token",
        to_json=lambda: '{"token": "new_token"}',
    )
    mock_flow_from_file.return_value = mock_flow

    creds = collector._get_credentials()

    assert creds.token == "new_token"
    mock_creds_from_file.assert_not_called()
    mock_path_open.assert_called_once_with(collector.token_path, "w")


@patch("recall.collectors.gcalendar.Path.open")
@patch("recall.collectors.gcalendar.Credentials.from_authorized_user_file")
def test_get_credentials_valid_token(
    mock_creds_from_file: MagicMock,
    mock_path_open: MagicMock,
    fs: FakeFilesystem,
    collector: GoogleCalendarCollector,
):
    """Test that a valid, existing token is loaded correctly."""
    fs.create_file(collector.token_path, contents="{'token': 'old_token'}")
    fs.create_file(collector.creds_path, contents="{}")
    assert collector.token_path.exists()

    mock_creds = MockCredentials(valid=True)
    mock_creds_from_file.return_value = mock_creds

    creds = collector._get_credentials()

    assert creds == mock_creds
    mock_path_open.assert_not_called()


@patch("recall.collectors.gcalendar.Path.open")
@patch("recall.collectors.gcalendar.Credentials.from_authorized_user_file")
@patch("recall.collectors.gcalendar.InstalledAppFlow.from_client_secrets_file")
def test_get_credentials_expired_token(
    mock_flow_from_file: MagicMock,
    mock_creds_from_file: MagicMock,
    mock_path_open: MagicMock,
    fs: FakeFilesystem,
    collector: GoogleCalendarCollector,
):
    """Test that an expired token is refreshed."""
    fs.create_file(collector.token_path, contents='{"token": "expired_token"}')
    fs.create_file(collector.creds_path, contents="{}")
    assert collector.token_path.exists()

    mock_creds = MagicMock(
        spec=Credentials,
        valid=False,
        expired=True,
        refresh_token="refresh_token",
    )
    mock_creds_from_file.return_value = mock_creds
    mock_creds.to_json.return_value = '{"token": "refreshed_token"}'

    creds = collector._get_credentials()

    mock_creds.refresh.assert_called_once()
    mock_path_open.assert_called_once_with(collector.token_path, "w")
    assert creds == mock_creds
    mock_flow_from_file.assert_not_called()
