import logging
from datetime import UTC, datetime

from homeassistant.components.recorder.statistics import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
    async_import_statistics,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EgdDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EG.D sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    ean = data["ean"]
    coordinator = data["coordinator"]

    sensors = [
        EgdEnergySensor(coordinator, ean, coordinator.profiles[0], "consumption"),
        EgdEnergySensor(coordinator, ean, coordinator.profiles[1], "production"),
        EgdEnergySensor(coordinator, ean, coordinator.profiles[2], "shared"),
        EgdSyncStatusSensor(coordinator, ean),
    ]

    async_add_entities(sensors)


class EgdEnergySensor(CoordinatorEntity, SensorEntity):
    """EG.D Sensor extracting historical data."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:flash"
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EgdDataUpdateCoordinator, ean: str, profile: str, translation_key: str
    ):
        super().__init__(coordinator)
        self.coordinator: EgdDataUpdateCoordinator = coordinator
        self._ean = ean
        self._profile = profile
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"egd_{ean}_{profile}"

        # Initialize from stored data
        self._storage_key = f"{self._ean}_{self._profile}"
        self._state = self.coordinator.stored_data.get(self._storage_key, {}).get(
            "cumulative_sum", 0.0
        )

    @property
    def native_value(self):
        return self._state

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._ean)},
            "name": f"Delivery Point {self._ean}",
            "manufacturer": "EG.D",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.hass.async_create_task(self._async_process_data())

    async def _async_process_data(self) -> None:
        """Process data as a background task."""
        if not self.coordinator.data:
            return

        profile_data = self.coordinator.data.get(self._profile)
        if profile_data and profile_data.get("parsed_data"):
            parsed_data = profile_data["parsed_data"]

            hourly_data: dict[datetime, float] = {}
            for bucket in sorted(parsed_data.keys()):
                val = parsed_data[bucket]
                if self._profile in ["ICC1", "ISC1"]:
                    val = val / 4.0
                hour_bucket = bucket.replace(minute=0, second=0, microsecond=0)
                hourly_data[hour_bucket] = hourly_data.get(hour_bucket, 0.0) + val

            statistics = []
            cumulative_sum = self.coordinator.stored_data[self._storage_key]["cumulative_sum"]

            for hour_bucket in sorted(hourly_data.keys()):
                cumulative_sum += hourly_data[hour_bucket]
                statistics.append(
                    StatisticData(
                        start=hour_bucket,
                        state=cumulative_sum,
                        sum=cumulative_sum,
                    )
                )

            if statistics:
                metadata = StatisticMetaData(
                    has_mean=False,
                    mean_type=StatisticMeanType.NONE,
                    has_sum=True,
                    name=None,  # Name doesn't need to be set according to modern HA standard
                    source="recorder",
                    statistic_id=self.entity_id,
                    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                    unit_class="energy",
                )

                async_import_statistics(self.hass, metadata, statistics)

                self._state = cumulative_sum

                async with self.coordinator.store_lock:
                    self.coordinator.stored_data[self._storage_key]["cumulative_sum"] = (
                        cumulative_sum
                    )
                    self.coordinator.stored_data[self._storage_key]["last_synced_date"] = (
                        profile_data["newest_dt"].isoformat()
                    )
                    # Also update sync status ok
                    sync_key = f"{self._ean}_sync_status"
                    self.coordinator.stored_data[sync_key]["status"] = "ok"
                    self.coordinator.stored_data[sync_key]["last_update"] = datetime.now(
                        UTC
                    ).isoformat()

                    await self.coordinator.store.async_save(self.coordinator.stored_data)

                _LOGGER.info("Imported %d records for %s", len(statistics), self._profile)

        self.async_write_ha_state()


class EgdSyncStatusSensor(CoordinatorEntity, SensorEntity):
    """EG.D Sync Status Sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "sync_status"
    _attr_icon = "mdi:sync"

    def __init__(self, coordinator: EgdDataUpdateCoordinator, ean: str):
        """Initialize."""
        super().__init__(coordinator)
        self.coordinator: EgdDataUpdateCoordinator = coordinator
        self._ean = ean
        self._attr_unique_id = f"egd_{ean}_sync_status"
        self._storage_key = f"{self._ean}_sync_status"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        # Coordinator sets this in memory on error, but we want to also
        # read from stored_data if we updated it
        return self.coordinator.stored_data.get(self._storage_key, {}).get(
            "status", "waiting_for_data"
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "last_update": self.coordinator.stored_data.get(self._storage_key, {}).get(
                "last_update"
            )
        }

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self._ean)},
            "name": f"Delivery Point {self._ean}",
            "manufacturer": "EG.D",
        }
