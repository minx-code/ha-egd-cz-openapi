from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant


async def test_sync_status_sensor(hass: HomeAssistant):
    coordinator_mock = MagicMock()
    coordinator_mock.stored_data = {
        "123456_sync_status": {
            "status": "waiting_for_data",
            "last_update": "2023-01-01T12:00:00+00:00",
        },
    }

    from custom_components.egd_cz_energy.sensor import EgdSyncStatusSensor

    sensor = EgdSyncStatusSensor(
        coordinator=coordinator_mock,
        ean="123456",
    )
    sensor.hass = hass

    assert sensor.native_value == "waiting_for_data"
    assert sensor.extra_state_attributes["last_update"] == "2023-01-01T12:00:00+00:00"

    coordinator_mock.stored_data["123456_sync_status"]["status"] = "ok"
    assert sensor.native_value == "ok"
