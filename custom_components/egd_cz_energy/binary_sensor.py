"""Binary sensor platform for EG.D OpenAPI."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EG.D binary sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    ean = data["ean"]
    coordinator = data["coordinator"]

    sensor = EgdConnectionSensor(coordinator, ean)
    async_add_entities([sensor])


class EgdConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """EG.D Connection Status Sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_translation_key = "connection"

    def __init__(self, coordinator, ean: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._ean = ean
        self._attr_unique_id = f"egd_{ean}_connection"

    @property
    def is_on(self):
        """Return true if the latest update was successful."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._ean)},
            "name": f"Delivery Point {self._ean}",
            "manufacturer": "EG.D",
        }
