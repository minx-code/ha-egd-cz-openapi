from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.egd_cz_energy.sensor import EgdEnergySensor


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def test_sensor_update_data(hass: HomeAssistant):
    """Test sensor async_update_data calls API and handles data."""
    api_mock = MagicMock()
    from unittest.mock import AsyncMock

    api_mock.async_get_profile_data = AsyncMock()

    # Return 2 points of data for the API mock
    now = datetime.now(UTC)
    p1_time = now - timedelta(hours=2)
    p2_time = now - timedelta(hours=1)

    coordinator_mock = MagicMock()
    coordinator_mock.data = {
        "ICQ2": {
            "parsed_data": {
                p1_time: 0.5,
                p2_time: 1.2,
            },
            "newest_dt": p2_time,
        }
    }
    coordinator_mock.stored_data = {
        "123456_ICQ2": {
            "cumulative_sum": 0.0,
            "last_synced_date": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
        },
        "123456_sync_status": {
            "status": "waiting_for_data",
            "last_update": None,
        },
    }

    store_mock = MagicMock()
    store_mock.async_save = AsyncMock()
    import asyncio

    coordinator_mock.store_lock = asyncio.Lock()
    coordinator_mock.store = store_mock

    sensor = EgdEnergySensor(
        coordinator=coordinator_mock,
        ean="123456",
        profile="ICQ2",
        translation_key="consumption",
    )
    sensor.hass = hass

    assert sensor.native_value == 0.0

    with (
        patch("custom_components.egd_cz_energy.sensor.async_import_statistics") as mock_import,
        patch("custom_components.egd_cz_energy.sensor.EgdEnergySensor.async_write_ha_state"),
    ):
        await sensor._async_process_data()

        # Check that it tried to import statistics
        assert mock_import.called

        # The sum should be updated to 1.7 (0.5 + 1.2)
        assert sensor.native_value == 1.7

        # It should have saved the state
        assert store_mock.async_save.called
