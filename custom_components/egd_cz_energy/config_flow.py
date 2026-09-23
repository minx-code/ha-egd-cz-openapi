import datetime
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    DateSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import EgdApi, EgdApiAuthError, EgdApiError
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_EAN,
    CONF_PROFILE_CONSUMPTION,
    CONF_PROFILE_PRODUCTION,
    DOMAIN,
    PROFILE_CONSUMPTION,
    PROFILE_PRODUCTION,
    UPDATE_HOUR,
    UPDATE_MINUTE,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_EAN): str,
        vol.Optional("unlimited_history", default=False): bool,
    }
)


class EgdEnergyOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for EG.D OpenAPI."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        typ_mereni = "C1"
        if DOMAIN in self.hass.data and self._config_entry.entry_id in self.hass.data[DOMAIN]:
            typ_mereni = self.hass.data[DOMAIN][self._config_entry.entry_id].get("typ_mereni", "C1")
        elif "typ_mereni" in self._config_entry.data:
            typ_mereni = self._config_entry.data["typ_mereni"]

        if typ_mereni in ["A", "B"]:
            default_cons = "ICQ2"
            default_prod = "ISQ2"
        else:
            default_cons = PROFILE_CONSUMPTION
            default_prod = PROFILE_PRODUCTION

        profile_options = ["ICQ2", "ICC1", "DCQC", "ISQ2", "ISC1", "DSQC", "DCQS", "ICQS"]

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_PROFILE_CONSUMPTION,
                    default=self._config_entry.options.get(CONF_PROFILE_CONSUMPTION, default_cons),
                ): SelectSelector(
                    SelectSelectorConfig(options=profile_options, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Optional(
                    CONF_PROFILE_PRODUCTION,
                    default=self._config_entry.options.get(CONF_PROFILE_PRODUCTION, default_prod),
                ): SelectSelector(
                    SelectSelectorConfig(options=profile_options, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Optional(
                    "update_hour",
                    default=self._config_entry.options.get("update_hour", UPDATE_HOUR),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Optional(
                    "update_minute",
                    default=self._config_entry.options.get("update_minute", UPDATE_MINUTE),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


class EgdEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EG.D OpenAPI."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EgdEnergyOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize."""
        self._user_input = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            ean = user_input[CONF_EAN]
            if not ean.isdigit() or len(ean) != 18:
                errors["ean"] = "invalid_ean"
            else:
                session = async_get_clientsession(self.hass)
                api = EgdApi(user_input[CONF_CLIENT_ID], user_input[CONF_CLIENT_SECRET], session)

                try:
                    await api.async_get_access_token()
                except EgdApiAuthError:
                    errors["base"] = "invalid_auth"
                except EgdApiError:
                    errors["base"] = "cannot_connect"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(user_input[CONF_EAN])
                    self._abort_if_unique_id_configured()

                    self._user_input = user_input

                    if user_input.get("unlimited_history", False):
                        return self.async_create_entry(
                            title=f"EG.D {user_input[CONF_EAN]}", data=self._user_input
                        )

                    return await self.async_step_history()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_history(self, user_input=None):
        """Handle the history start date step."""
        if user_input is not None:
            self._user_input.update(user_input)
            return self.async_create_entry(
                title=f"EG.D {self._user_input[CONF_EAN]}", data=self._user_input
            )

        schema = vol.Schema(
            {vol.Optional("history_start_date", default=str(datetime.date.today())): DateSelector()}
        )
        return self.async_show_form(step_id="history", data_schema=schema)

    async def async_step_reconfigure(self, user_input=None):
        """Handle a reconfiguration flow."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = EgdApi(user_input[CONF_CLIENT_ID], user_input[CONF_CLIENT_SECRET], session)
            try:
                await api.async_get_access_token()
            except EgdApiAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, **user_input},
                    reason="reconfigure_successful",
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID, default=entry.data[CONF_CLIENT_ID]): str,
                vol.Required(CONF_CLIENT_SECRET, default=entry.data[CONF_CLIENT_SECRET]): str,
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)
