from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from pyfakefs.fake_filesystem_unittest import Patcher

from recall.collectors.gcalendar import (
    GoogleCalendarCollector,
    GoogleCalendarCredentialsError,
)
from tests.utils import make_dt


@pytest.fixture
def collector(fs) -> GoogleCalendarCollector:
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
    """Mock credentials with universe_domain property."""

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


@patch("recall.collectors.gcalendar.InstalledAppFlow.from_client_secrets_file")
def test_get_credentials_no_token(
    mock_flow_from_file: MagicMock,
    collector: GoogleCalendarCollector,
    fs,
):
    """Test the credential loading process when no token file exists."""
    fs.create_file(collector.creds_path, contents='{"installed":{}}')
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = MockCredentials(
        token="new_token",
        to_json=lambda: '{"token": "new_token"}',
    )
    mock_flow_from_file.return_value = mock_flow

    creds = collector._get_credentials()

    assert creds.token == "new_token"
    assert fs.exists(collector.token_path)
    with open(collector.token_path) as f:
        assert '{"token": "new_token"}' in f.read()