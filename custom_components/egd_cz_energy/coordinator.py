import asyncio
import logging
from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EgdApi, EgdApiAuthError
from .const import DOMAIN
from .utils import parse_15min_data

_LOGGER = logging.getLogger(__name__)


class EgdDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching EG.D data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EgdApi,
        ean: str,
        profiles: list[str],
        store,
        stored_data: dict,
        history_start: datetime,
        entry_id: str,
    ):
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self.api = api
        self.ean = ean
        self.profiles = profiles
        self.store = store
        self.stored_data = stored_data
        self.history_start = history_start
        self.entry_id = entry_id
        self.custom_start_date = None
        self.store_lock = asyncio.Lock()

        # Initialize stored data
        for profile in self.profiles:
            key = f"{self.ean}_{profile}"
            if key not in self.stored_data:
                self.stored_data[key] = {
                    "last_synced_date": self.history_start.isoformat(),
                    "cumulative_sum": 0.0,
                }

        sync_key = f"{self.ean}_sync_status"
        if sync_key not in self.stored_data:
            self.stored_data[sync_key] = {
                "status": "waiting_for_data",
                "last_update": None,
            }

    async def _async_update_data(self):
        """Fetch data from API."""
        async_delete_issue(self.hass, DOMAIN, "auth_failed")

        now_local = dt_util.now()
        yesterday_end_local = (now_local - timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=999000
        )
        yesterday_end = yesterday_end_local.astimezone(UTC)

        fetched_data = {}

        try:
            for profile in self.profiles:
                key = f"{self.ean}_{profile}"
                last_synced_str = self.stored_data.get(key, {}).get("last_synced_date")
                if not last_synced_str:
                    continue

                last_synced = datetime.fromisoformat(last_synced_str)
                start_date = self.custom_start_date if self.custom_start_date else last_synced

                if start_date >= yesterday_end:
                    continue

                data_points = await self.api.async_get_profile_data(
                    self.ean, profile, start_date, yesterday_end
                )

                if data_points:
                    parsed_data, newest_dt = parse_15min_data(data_points)
                    fetched_data[profile] = {
                        "parsed_data": parsed_data,
                        "newest_dt": newest_dt,
                    }

            self.custom_start_date = None
            return fetched_data

        except EgdApiAuthError as err:
            async_create_issue(
                self.hass,
                DOMAIN,
                "auth_failed",
                is_fixable=False,
                severity=IssueSeverity.ERROR,
                translation_key="auth_failed",
                translation_placeholders={"ean": self.ean},
            )
            async with self.store_lock:
                sync_key = f"{self.ean}_sync_status"
                if sync_key in self.stored_data:
                    self.stored_data[sync_key]["status"] = "error"
                await self.store.async_save(self.stored_data)
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except Exception as err:
            async with self.store_lock:
                sync_key = f"{self.ean}_sync_status"
                if sync_key in self.stored_data:
                    self.stored_data[sync_key]["status"] = "error"
                await self.store.async_save(self.stored_data)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
