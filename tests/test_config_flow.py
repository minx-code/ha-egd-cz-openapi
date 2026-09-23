from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.egd_cz_energy.api import EgdApiAuthError, EgdApiError
from custom_components.egd_cz_energy.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for testing."""
    yield


async def test_successful_config_flow(hass: HomeAssistant):
    """Test a successful config flow."""
    # Initialize the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that the first step is a form
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Simulate user submitting valid data
    with (
        patch(
            "custom_components.egd_cz_energy.config_flow.EgdApi.async_get_access_token",
            return_value=True,
        ),
        patch(
            "custom_components.egd_cz_energy.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "ean": "859182400123456789",
                "unlimited_history": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "history"

    import datetime

    today_str = str(datetime.date.today())

    with patch(
        "custom_components.egd_cz_energy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "history_start_date": today_str,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["title"] == "EG.D 859182400123456789"

    assert result3["data"] == {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "ean": "859182400123456789",
        "unlimited_history": False,
        "history_start_date": today_str,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_failed_config_flow_invalid_auth(hass: HomeAssistant):
    """Test a failed config flow due to invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.egd_cz_energy.config_flow.EgdApi.async_get_access_token",
        side_effect=EgdApiAuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "ean": "859182400123456789",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_failed_config_flow_cannot_connect(hass: HomeAssistant):
    """Test a failed config flow due to connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.egd_cz_energy.config_flow.EgdApi.async_get_access_token",
        side_effect=EgdApiError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "ean": "859182400123456789",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow(hass: HomeAssistant):
    """Test the reconfiguration flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EG.D 123456",
        data={
            "client_id": "old_id",
            "client_secret": "old_secret",
            "ean": "123456",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
        data=entry.data,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "custom_components.egd_cz_energy.config_flow.EgdApi.async_get_access_token",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "client_id": "new_id",
                "client_secret": "new_secret",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data["client_id"] == "new_id"
    assert entry.data["client_secret"] == "new_secret"


async def test_options_flow(hass: HomeAssistant):
    """Test the options flow."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="EG.D 123456",
        data={
            "client_id": "test_id",
            "client_secret": "test_secret",
            "ean": "123456",
        },
        options={"update_hour": 10, "update_minute": 15},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"update_hour": 14, "update_minute": 30},
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"]["update_hour"] == 14
    assert result2["data"]["update_minute"] == 30


async def test_failed_config_flow_invalid_ean(hass: HomeAssistant):
    """Test a failed config flow due to invalid ean."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.egd_cz_energy.config_flow.EgdApi.async_get_access_token",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "client_id": "test_client_id",
                "client_secret": "test_client_secret",
                "ean": "invalid_ean_string",
                "unlimited_history": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"ean": "invalid_ean"}
