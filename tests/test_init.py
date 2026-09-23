from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.egd_cz_energy.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def test_setup_and_unload_entry(hass: HomeAssistant):
    """Test setting up and unloading the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "client_id": "test_id",
            "client_secret": "test_secret",
            "ean": "123456789012345678",
            "typ_mereni": "C1",
        },
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.egd_cz_energy.api.EgdApi.async_get_access_token", return_value=True
        ),
        patch(
            "custom_components.egd_cz_energy.api.EgdApi.async_get_om_list",
            return_value=[{"ean": "123456789012345678", "kodOM": "1", "typMereni": "C1"}],
        ),
        patch("custom_components.egd_cz_energy.async_track_time_change"),
        patch.object(hass.loop, "call_later"),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ) as mock_forward,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        # Verify it was forwarded to sensor platform
        mock_forward.assert_called_once_with(entry, ["sensor", "binary_sensor"])

    assert hass.data[DOMAIN][entry.entry_id]["ean"] == "123456789012345678"
    assert hass.data[DOMAIN][entry.entry_id]["typ_mereni"] == "C1"

    # Test the service is registered
    assert hass.services.has_service(DOMAIN, "fetch_history")

    # Add dummy coordinator to test service execution
    mock_coord = MagicMock()
    mock_coord.async_request_refresh = AsyncMock()
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = mock_coord

    # Call service
    await hass.services.async_call(DOMAIN, "fetch_history", blocking=True)

    # Assert update was called with None (default)
    mock_coord.async_request_refresh.assert_called_once_with()

    # Test service call with parameters
    mock_coord.async_request_refresh.reset_mock()

    with patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get:
        mock_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.identifiers = {(DOMAIN, "123456789012345678")}
        mock_registry.async_get.return_value = mock_device
        mock_dr_get.return_value = mock_registry

        await hass.services.async_call(
            DOMAIN,
            "fetch_history",
            {"device_id": ["dummy_id"], "start_date": "2023-01-01"},
            blocking=True,
        )

    mock_coord.async_request_refresh.assert_called_once_with()

    # Unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert "test_entry_id" not in hass.data[DOMAIN]
