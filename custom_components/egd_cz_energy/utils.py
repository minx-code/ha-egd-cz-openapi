import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


def parse_15min_data(data_points: list) -> tuple[dict[datetime, float], datetime | None]:
    """
    Parses 15-minute data points and returns them without aggregating.
    Returns a tuple of (parsed_data_dict, newest_datetime).
    """
    parsed_data = {}
    newest_dt = None

    for point in data_points:
        try:
            ts_str = point["timestamp"]
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts_str)
            val = float(point["value"])

            parsed_data[dt] = val

            if newest_dt is None or dt > newest_dt:
                newest_dt = dt
        except (ValueError, KeyError) as e:
            _LOGGER.warning("Failed to parse data point: %s", e)

    return parsed_data, newest_dt
