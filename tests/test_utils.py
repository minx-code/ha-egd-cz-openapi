from datetime import UTC, datetime

import pytest

from custom_components.egd_cz_energy.utils import parse_15min_data


def test_parse_15min_data_basic():
    """Test basic parsing of 15-minute intervals."""
    data_points = [
        {"timestamp": "2026-09-15T10:00:00Z", "value": "0.01"},
        {"timestamp": "2026-09-15T10:15:00Z", "value": "0.02"},
        {"timestamp": "2026-09-15T10:30:00Z", "value": "0.03"},
        {"timestamp": "2026-09-15T10:45:00Z", "value": "0.01"},
    ]

    parsed_data, newest_dt = parse_15min_data(data_points)

    assert len(parsed_data) == 4
    assert datetime(2026, 9, 15, 10, 0, tzinfo=UTC) in parsed_data
    assert parsed_data[datetime(2026, 9, 15, 10, 15, tzinfo=UTC)] == pytest.approx(0.02)
    assert newest_dt == datetime(2026, 9, 15, 10, 45, tzinfo=UTC)


def test_parse_15min_data_midnight_boundary():
    """Test parsing across midnight boundaries."""
    data_points = [
        {"timestamp": "2026-09-15T23:45:00Z", "value": "0.10"},
        {"timestamp": "2026-09-16T00:00:00Z", "value": "0.05"},
        {"timestamp": "2026-09-16T00:15:00Z", "value": "0.05"},
    ]

    parsed_data, newest_dt = parse_15min_data(data_points)

    assert len(parsed_data) == 3
    assert parsed_data[datetime(2026, 9, 15, 23, 45, tzinfo=UTC)] == pytest.approx(0.10)
    assert parsed_data[datetime(2026, 9, 16, 0, 0, tzinfo=UTC)] == pytest.approx(0.05)
    assert parsed_data[datetime(2026, 9, 16, 0, 15, tzinfo=UTC)] == pytest.approx(0.05)
