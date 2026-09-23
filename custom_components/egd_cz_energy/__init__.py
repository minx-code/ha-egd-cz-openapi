import logging
from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api import EgdApi
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
from .coordinator import EgdDataUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_stats"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EG.D from a config entry."""
    session = async_get_clientsession(hass)
    api = EgdApi(entry.data[CONF_CLIENT_ID], entry.data[CONF_CLIENT_SECRET], session)

    try:
        om_list = await api.async_get_om_list()
    except Exception as e:
        _LOGGER.error("Failed to fetch OM list: %s", e)
        return False

    typ_mereni = "C1"
    for om in om_list:
        if om.get("ean") == entry.data[CONF_EAN]:
            typ_mereni = om.get("typMereni", "C1")
            break

    # Extract profiles
    if typ_mereni in ["A", "B"]:
        default_cons = "ICQ2"
        default_prod = "ISQ2"
        profile_shared = "ICQS"
    else:
        default_cons = PROFILE_CONSUMPTION
        default_prod = PROFILE_PRODUCTION
        profile_shared = "DCQS"

    profile_cons = entry.options.get(CONF_PROFILE_CONSUMPTION, default_cons)
    profile_prod = entry.options.get(CONF_PROFILE_PRODUCTION, default_prod)
    profiles = [profile_cons, profile_prod, profile_shared]

    history_start_date_str = entry.data.get("history_start_date")
    unlimited_history = entry.data.get("unlimited_history", False)

    now_utc = datetime.now(UTC)
    max_history = now_utc - timedelta(days=3 * 365)

    if unlimited_history:
        history_start = max_history
    elif history_start_date_str:
        history_start = datetime.fromisoformat(history_start_date_str).replace(tzinfo=UTC)
        if history_start < max_history:
            history_start = max_history
    else:
        history_start = now_utc - timedelta(days=30)

    # Setup storage
    store: storage.Store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}

    coordinator = EgdDataUpdateCoordinator(
        hass, api, entry.data[CONF_EAN], profiles, store, stored_data, history_start, entry.entry_id
    )
    coordinator.typ_mereni = typ_mereni

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "ean": entry.data[CONF_EAN],
        "typ_mereni": typ_mereni,
        "coordinator": coordinator,
    }

    # Setup services
    await async_setup_services(hass, store)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup daily update task
    update_hour = entry.options.get("update_hour", UPDATE_HOUR)
    update_minute = entry.options.get("update_minute", UPDATE_MINUTE)

    async def _scheduled_update(*_):
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(
            hass, _scheduled_update, hour=update_hour, minute=update_minute, second=0
        )
    )

    # Trigger first refresh after short delay
    hass.loop.call_later(10, lambda: hass.async_create_task(coordinator.async_request_refresh()))

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
