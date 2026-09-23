from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.egd_cz_energy.api import EgdApiAuthError
from custom_components.egd_cz_energy.coordinator import EgdDataUpdateCoordinator


@pytest.mark.asyncio
async def test_coordinator_update_data(hass: HomeAssistant):
    """Test the data update coordinator."""
    api_mock = MagicMock()

    now = datetime.now(UTC)
    p1 = now - timedelta(days=2)
    api_mock.async_get_profile_data = AsyncMock(
        return_value=[{"timestamp": p1.isoformat(), "value": 1.5}]
    )

    store_mock = MagicMock()
    store_mock.async_save = AsyncMock()

    history_start = now - timedelta(days=5)
    stored_data = {}

    coordinator = EgdDataUpdateCoordinator(
        hass, api_mock, "123456", ["ICQ2"], store_mock, stored_data, history_start, "fake_entry_id"
    )

    assert "123456_ICQ2" in coordinator.stored_data

    data = await coordinator._async_update_data()
    assert "ICQ2" in data
    assert "parsed_data" in data["ICQ2"]

    # Test Auth error fallback saving status
    api_mock.async_get_profile_data.side_effect = EgdApiAuthError("Auth error")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert "123456_sync_status" in coordinator.stored_data
    assert coordinator.stored_data["123456_sync_status"]["status"] == "error"
