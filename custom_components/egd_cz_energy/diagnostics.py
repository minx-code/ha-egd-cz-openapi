"""Diagnostics support for EG.D OpenAPI."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage

from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_EAN, DOMAIN

TO_REDACT = {
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
}

STORAGE_VERSION = 1


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    # Fetch data from Storage (if they exist)
    storage_key = f"{DOMAIN}_stats"
    store: storage.Store = storage.Store(hass, STORAGE_VERSION, storage_key)
    stored_data = await store.async_load() or {}

    # Redact sensitive data
    redacted_data = async_redact_data(entry.data, TO_REDACT)

    # Safely mask the EAN (show only the last 4 digits)
    ean = entry.data.get(CONF_EAN, "")
    if len(ean) > 4:
        redacted_data[CONF_EAN] = f"***{ean[-4:]}"

    # Anonymize saved sensor states (mask EAN in the keys of saved data)
    sanitized_stored_data = {}
    for key, val in stored_data.items():
        if ean in key and len(ean) > 4:
            safe_key = key.replace(ean, f"***{ean[-4:]}")
            sanitized_stored_data[safe_key] = val
        else:
            sanitized_stored_data[key] = val

    diagnostics = {
        "entry": {
            "title": entry.title,
            "data": redacted_data,
        },
        "stored_data": sanitized_stored_data,
        "entry_id": entry.entry_id,
        "version": entry.version,
    }

    return diagnostics
