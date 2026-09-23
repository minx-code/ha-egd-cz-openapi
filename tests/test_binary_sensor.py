import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant

from custom_components.egd_cz_energy.binary_sensor import EgdConnectionSensor


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def test_binary_sensor(hass: HomeAssistant):
    """Test the EG.D Connection Sensor."""
    from unittest.mock import MagicMock

    coordinator_mock = MagicMock()
    coordinator_mock.last_update_success = True

    sensor = EgdConnectionSensor(coordinator_mock, "123456789")
    sensor.hass = hass

    assert sensor.device_class == BinarySensorDeviceClass.CONNECTIVITY
    assert sensor.is_on is True

    # Test setting state
    coordinator_mock.last_update_success = False
    assert sensor.is_on is False
