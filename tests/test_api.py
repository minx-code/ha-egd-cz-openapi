from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.egd_cz_energy.api import EgdApi, EgdApiPermissionError, EgdApiRateLimitError
from custom_components.egd_cz_energy.const import URL_SPOTREBY


@pytest.fixture
def mock_aioresponse():
    with aioresponses() as m:
        yield m


@pytest.mark.asyncio
async def test_fetch_profile_data_permission_fallback(mock_aioresponse):
    """Test that api correctly falls back to 1-day chunks on permission error."""

    session = aiohttp.ClientSession()
    api = EgdApi("client_id", "client_secret", session)
    api._access_token = "fake_token"

    # Mock timezone to UTC for predictable test
    with patch("homeassistant.util.dt.get_default_time_zone", return_value=UTC):
        # Setup: Requesting from 10th to 12th
        date_from = datetime(2026, 9, 10, 0, 0, tzinfo=UTC)
        date_to = datetime(2026, 9, 12, 0, 0, tzinfo=UTC)

        # Mock 1: The large chunk request fails with permission error
        mock_aioresponse.get(
            URL_SPOTREBY,
            status=400,
            payload={"message": "V požadovaném období nemáte oprávnění"},
            repeat=True,
        )

        # We need to catch the requests inside _fetch_chunk to simulate
        # failure on the large chunk and success on the 1-day chunks.
        # But aioresponses matches by URL, and the params differ.
        # It's easier to mock `_fetch_chunk` directly.

        with (
            patch.object(api, "_fetch_chunk") as mock_fetch,
            patch.object(api, "async_get_access_token", return_value="fake_token"),
        ):
            # Mock behavior: first call (large chunk) raises error
            # Subsequent calls (1-day chunks) succeed

            def side_effect(ean, profile, d_from, d_to, headers):
                if (d_to - d_from).days > 1:
                    raise EgdApiPermissionError("nemáte oprávnění")
                return [
                    {
                        "data": [
                            {
                                "timestamp": d_from.isoformat().replace("+00:00", "Z"),
                                "value": "1.0",
                                "status": "W",
                            }
                        ]
                    }
                ]

            mock_fetch.side_effect = side_effect

            results = await api.async_get_profile_data("ean123", "ICQ2", date_from, date_to)

            # The large chunk failed, so it fell back to 1-day chunks.
            # 10th to 12th = 2 days, so 2 successful 1-day chunk fetches.
            assert len(results) == 2
            assert mock_fetch.call_count == 3  # 1 large failure + 2 day fetches

    await session.close()


@pytest.mark.asyncio
async def test_fetch_chunk_permission_error(mock_aioresponse):
    """Test that _fetch_chunk raises EgdApiPermissionError on 400 with specific message."""
    session = aiohttp.ClientSession()
    api = EgdApi("client_id", "client_secret", session)
    api._access_token = "fake_token"

    from unittest.mock import AsyncMock

    mock_resp = AsyncMock()
    mock_resp.status = 400
    mock_resp.json = AsyncMock(return_value={"message": "V požadovaném období nemáte oprávnění"})

    mock_get = MagicMock()
    mock_get.return_value.__aenter__.return_value = mock_resp

    date_from = datetime(2026, 9, 10, 0, 0, tzinfo=UTC)
    date_to = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)

    from unittest.mock import patch

    with patch.object(api._session, "get", new=mock_get):
        with pytest.raises(EgdApiPermissionError):
            await api._fetch_chunk("123", "ICQ2", date_from, date_to, {})

    await session.close()


@pytest.mark.asyncio
async def test_fetch_chunk_rate_limit():
    """Test that _fetch_chunk raises EgdApiRateLimitError on 429."""
    session = aiohttp.ClientSession()
    api = EgdApi("client_id", "client_secret", session)
    api._access_token = "fake_token"

    from unittest.mock import AsyncMock, patch

    mock_resp = AsyncMock()
    mock_resp.status = 429
    mock_resp.json = AsyncMock(return_value={})

    mock_get = MagicMock()
    mock_get.return_value.__aenter__.return_value = mock_resp

    date_from = datetime(2026, 9, 10, 0, 0, tzinfo=UTC)
    date_to = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)

    with patch.object(api._session, "get", new=mock_get):
        with pytest.raises(EgdApiRateLimitError):
            await api._fetch_chunk("123", "ICQ2", date_from, date_to, {})

    await session.close()


@pytest.mark.asyncio
async def test_check_day_access():
    """Test _check_day_access method."""
    session = aiohttp.ClientSession()
    api = EgdApi("client_id", "client_secret", session)

    date_check = datetime(2026, 9, 10, 0, 0, tzinfo=UTC)
    headers: dict[str, str] = {}

    from unittest.mock import patch

    with patch.object(api, "_fetch_chunk") as mock_fetch:
        # 1. Success
        mock_fetch.return_value = []
        res = await api._check_day_access("123", "ICQ2", date_check, headers)
        assert res is True

        # 2. Permission error -> False
        mock_fetch.side_effect = EgdApiPermissionError("nemáte oprávnění")
        res = await api._check_day_access("123", "ICQ2", date_check, headers)
        assert res is False

        # 3. Rate limit -> Bubbles up
        mock_fetch.side_effect = EgdApiRateLimitError("Too Many Requests")
        with pytest.raises(EgdApiRateLimitError):
            await api._check_day_access("123", "ICQ2", date_check, headers)

        # 4. Other error -> False
        mock_fetch.side_effect = Exception("Some network issue")
        res = await api._check_day_access("123", "ICQ2", date_check, headers)
        assert res is False

    await session.close()


@pytest.mark.asyncio
async def test_get_access_token():
    """Test getting access token."""
    session = aiohttp.ClientSession()
    api = EgdApi("client_id", "client_secret", session)

    from unittest.mock import AsyncMock, patch

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"access_token": "new_token"})
    mock_post = MagicMock()
    mock_post.return_value.__aenter__.return_value = mock_resp

    with patch.object(api._session, "post", new=mock_post):
        token = await api.async_get_access_token()
        assert token == "new_token"
        assert api._access_token == "new_token"

    await session.close()


@pytest.mark.asyncio
async def test_get_om_list():
    """Test getting OM list."""
    session = aiohttp.ClientSession()
    api = EgdApi("client_id", "client_secret", session)
    api._access_token = "fake_token"

    from unittest.mock import AsyncMock, patch

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=[{"ean": "123"}])
    mock_get = MagicMock()
    mock_get.return_value.__aenter__.return_value = mock_resp

    with (
        patch.object(api._session, "get", new=mock_get),
        patch.object(api, "async_get_access_token", return_value="fake_token"),
    ):
        om_list = await api.async_get_om_list()
        assert om_list == [{"ean": "123"}]

    await session.close()
