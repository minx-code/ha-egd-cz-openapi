from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import aiohttp
import pytest

from custom_components.egd_cz_energy.api import EgdApi


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.mark.asyncio
async def test_find_first_valid_date():
    """Test binary search for the first valid date."""
    session = aiohttp.ClientSession()
    api = EgdApi("client_id", "client_secret", session)

    date_from = datetime(2023, 1, 1, 0, 0, tzinfo=UTC)
    date_to = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)  # 3 years = 1095 days

    # Suppose the real start date is 2024-05-15 (day 500)
    real_start = date_from + timedelta(days=500)

    async def mock_check_day(ean, profile, check_dt, headers):
        return check_dt >= real_start

    with (
        patch("homeassistant.util.dt.get_default_time_zone", return_value=UTC),
        patch.object(api, "_check_day_access", side_effect=mock_check_day) as mock_check,
    ):
        valid_start = await api._find_first_valid_date("123", "ICQ2", date_from, date_to, {})

        # Binary search should find the exact start day
        assert valid_start == real_start
        # It should take roughly log2(1095) ≈ 11 checks
        assert mock_check.call_count <= 12

    await session.close()
