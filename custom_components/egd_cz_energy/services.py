import logging
from datetime import UTC, datetime

import voluptuous as vol
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _setup_fetch_history_service(hass: HomeAssistant) -> None:  # noqa: C901
    """Set up the fetch_history service."""

    async def handle_fetch_history(call):  # noqa: C901
        from homeassistant.helpers import device_registry as dr

        device_ids = call.data.get("device_id")
        start_date_str = call.data.get("start_date")

        custom_start = None
        if start_date_str:
            try:
                custom_start = datetime.fromisoformat(start_date_str).replace(tzinfo=UTC)
            except ValueError:
                pass

        target_eans = set()
        if device_ids:
            if isinstance(device_ids, str):
                device_ids = [device_ids]
            dev_reg = dr.async_get(hass)
            for d_id in device_ids:
                device = dev_reg.async_get(d_id)
                if device:
                    for identifier in device.identifiers:
                        if identifier[0] == DOMAIN:
                            target_eans.add(identifier[1])

        for entry_data in hass.data[DOMAIN].values():
            ean = entry_data.get("ean")
            if target_eans and ean not in target_eans:
                continue

            coord = entry_data.get("coordinator")
            if coord:
                coord.custom_start_date = custom_start
                await coord.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "fetch_history"):
        hass.services.async_register(DOMAIN, "fetch_history", handle_fetch_history)


def _setup_remove_statistics_service(hass: HomeAssistant, store) -> None:
    """Set up the remove_statistics service."""

    async def handle_remove_statistics(call):
        from homeassistant.components.recorder import get_instance

        entry_id = call.data.get("entry_id")
        ean = call.data.get("ean")
        statistic_ids = []

        for e_id, entry_data in hass.data[DOMAIN].items():
            if entry_id and e_id != entry_id:
                continue
            entry_ean = entry_data.get("ean")
            if ean and entry_ean != ean:
                continue

            coord = entry_data.get("coordinator")
            if coord:
                for profile in coord.profiles:
                    statistic_ids.append(f"sensor.egd_{entry_ean}_{profile}".lower())

        if statistic_ids:
            get_instance(hass).async_clear_statistics(statistic_ids)

        await store.async_remove()

    if not hass.services.has_service(DOMAIN, "remove_statistics"):
        schema = vol.Schema(
            {
                vol.Optional("entry_id"): str,
                vol.Optional("ean"): str,
            }
        )
        hass.services.async_register(
            DOMAIN, "remove_statistics", handle_remove_statistics, schema=schema
        )


async def async_setup_services(hass: HomeAssistant, store) -> None:
    """Set up services for the EG.D integration."""
    _setup_fetch_history_service(hass)
    _setup_remove_statistics_service(hass, store)
