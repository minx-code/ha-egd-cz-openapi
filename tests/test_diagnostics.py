"""Test diagnostics for EG.D OpenAPI."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.egd_cz_energy.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_EAN,
    DOMAIN,
)
from custom_components.egd_cz_energy.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_get_config_entry_diagnostics(hass: HomeAssistant):
    """Test diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EG.D 123456789012345678",
        data={
            CONF_CLIENT_ID: "my_client_id",
            CONF_CLIENT_SECRET: "my_secret_token",
            CONF_EAN: "123456789012345678",
        },
    )
    entry.add_to_hass(hass)

    # Mock storage
    stored_data = {
        "123456789012345678_DCQC": {
            "last_synced_date": "2026-09-20T00:00:00+00:00",
            "cumulative_sum": 100.5,
        }
    }

    with patch(
        "custom_components.egd_cz_energy.diagnostics.storage.Store.async_load",
        return_value=stored_data,
    ):
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

        # Check redaction of secrets
        assert diagnostics["entry"]["data"][CONF_CLIENT_SECRET] == "**REDACTED**"
        assert diagnostics["entry"]["data"][CONF_CLIENT_ID] == "**REDACTED**"

        # Check redaction of EAN
        assert diagnostics["entry"]["data"][CONF_EAN] == "***5678"

        # Check redaction of EAN in stored data keys
        assert "***5678_DCQC" in diagnostics["stored_data"]
        assert diagnostics["stored_data"]["***5678_DCQC"]["cumulative_sum"] == 100.5
        assert "123456789012345678_DCQC" not in diagnostics["stored_data"]
