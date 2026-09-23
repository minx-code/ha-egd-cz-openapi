"""Global fixtures for EG.D tests."""

from unittest.mock import patch

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def mock_recorder_setup():
    """Mock recorder setup to prevent DependencyError in tests."""
    with patch("homeassistant.components.recorder.async_setup", return_value=True):
        yield
