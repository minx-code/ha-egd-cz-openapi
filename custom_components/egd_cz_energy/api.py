import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.util import dt as dt_util

from .const import MAX_DAYS_PER_REQUEST, URL_OM, URL_SPOTREBY, URL_TOKEN

_LOGGER = logging.getLogger(__name__)


class EgdApiError(Exception):
    """Exception to indicate a general API error."""


class EgdApiAuthError(EgdApiError):
    """Exception to indicate an authentication error."""


class EgdApiPermissionError(EgdApiError):
    """Exception to indicate a permission error for a specific date range."""


class EgdApiRateLimitError(EgdApiError):
    """Exception to indicate rate limiting (HTTP 429)."""


class EgdApi:
    """Interface to the EG.D OpenApi."""

    def __init__(self, client_id: str, client_secret: str, session: aiohttp.ClientSession):
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = session
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None

    async def async_get_access_token(self) -> str:
        """Fetch a new access token."""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "namerena_data_openapi",
        }
        try:
            async with self._session.post(URL_TOKEN, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("Failed to get token: %s", text)
                    raise EgdApiAuthError(f"HTTP Error {resp.status}")
                data = await resp.json()
                token = data.get("access_token")
                if not token:
                    raise EgdApiAuthError("No access token in response")
                self._access_token = str(token)
                expires_in = data.get("expires_in", 3600)
                self._token_expiry = datetime.now(UTC) + timedelta(seconds=expires_in - 60)
                return self._access_token
        except aiohttp.ClientError as err:
            raise EgdApiError(f"Connection error: {err}") from err

    async def async_get_om_list(self) -> list:
        """Fetch list of supply points (EANs) and their measurement types."""
        if (
            not self._access_token
            or not self._token_expiry
            or datetime.now(UTC) >= self._token_expiry
        ):
            await self.async_get_access_token()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        url = URL_OM

        try:
            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    await self.async_get_access_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with self._session.get(url, headers=headers) as resp2:
                        if resp2.status != 200:
                            raise EgdApiError(f"HTTP Error {resp2.status}")
                        return await resp2.json()
                elif resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("Failed to get OM list: %s", text)
                    raise EgdApiError(f"HTTP Error {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise EgdApiError(f"Connection error: {err}") from err

    async def async_get_profile_data(  # noqa: C901
        self, ean: str, profile: str, date_from: datetime, date_to: datetime
    ) -> list:
        """
        Fetch profile data.
        date_from and date_to should be timezone aware (UTC).
        """
        if (
            not self._access_token
            or not self._token_expiry
            or datetime.now(UTC) >= self._token_expiry
        ):
            await self.async_get_access_token()

        headers = {"Authorization": f"Bearer {self._access_token}"}

        # If we request a large data range (e.g. > 60 days on the first sync),
        # we perform a binary search for the first valid day to prevent 429 Too Many Requests
        # by querying days without data (before the contract start).
        if (date_to - date_from).days > 60:
            _LOGGER.info(
                "Large date range requested (%s days). Finding exact contract start date...",
                (date_to - date_from).days,
            )
            valid_start = await self._find_first_valid_date(
                ean, profile, date_from, date_to, headers
            )
            _LOGGER.info("Determined real start date: %s", valid_start)
            date_from = valid_start

        all_results: list[dict[str, Any]] = []

        # Create time chunks of max 30 days
        chunks = []
        current_from = date_from
        while current_from < date_to:
            current_to = min(current_from + timedelta(days=MAX_DAYS_PER_REQUEST), date_to)
            chunks.append((current_from, current_to))
            current_from = current_to

        semaphore = asyncio.Semaphore(3)

        async def fetch_chunk_with_fallback(start_dt: datetime, end_dt: datetime):
            async with semaphore:
                retries = 3
                delay = 2
                for attempt in range(retries):
                    try:
                        local_headers = headers.copy()
                        data = await self._fetch_chunk(
                            ean, profile, start_dt, end_dt, local_headers
                        )
                        return data
                    except EgdApiPermissionError:
                        _LOGGER.info(
                            "Permission error for chunk %s to %s, falling back to 1-day chunks",
                            start_dt,
                            end_dt,
                        )
                        local_headers = headers.copy()
                        return await self._fetch_days_fallback(
                            ean, profile, start_dt, end_dt, local_headers
                        )
                    except EgdApiRateLimitError as e:
                        _LOGGER.error("Rate limit exceeded. Aborting fetch chunk: %s", e)
                        raise
                    except EgdApiError as e:
                        if attempt < retries - 1:
                            _LOGGER.warning("API error %s, retrying in %d seconds...", e, delay)
                            await asyncio.sleep(delay)
                            delay *= 2
                        else:
                            _LOGGER.error(
                                "Failed to fetch chunk %s to %s after %d attempts: %s",
                                start_dt,
                                end_dt,
                                retries,
                                e,
                            )
                            return []
                return []

        tasks = [fetch_chunk_with_fallback(c_from, c_to) for c_from, c_to in chunks]
        results = await asyncio.gather(*tasks)

        for res in results:
            self._parse_and_append(res, all_results)

        return all_results

    async def _check_day_access(
        self, ean: str, profile: str, check_dt: datetime, headers: dict
    ) -> bool:
        """Check if the user has permissions for data on a given day (even if empty)."""
        temp_to = check_dt + timedelta(days=1)
        try:
            await self._fetch_chunk(ean, profile, check_dt, temp_to, headers)
            return True
        except EgdApiPermissionError:
            return False
        except EgdApiRateLimitError:
            raise
        except Exception as e:
            # Ignore network issues, 500 and treat as error / no permission,
            # or let it bubble up
            _LOGGER.debug("Day check failed for %s: %s", check_dt, e)
            return False

    async def _find_first_valid_date(
        self, ean: str, profile: str, date_from: datetime, date_to: datetime, headers: dict
    ) -> datetime:
        """Binary search to find the day from which the API stops returning 400 (no permission)."""
        local_tz = dt_util.get_default_time_zone()
        # Normalize to midnight local time for clean day counts
        from_local = date_from.astimezone(local_tz).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        to_local = date_to.astimezone(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

        low = 0
        high = (to_local - from_local).days
        if high <= 0:
            return date_from

        first_valid = high

        while low <= high:
            mid = (low + high) // 2
            check_dt_local = from_local + timedelta(days=mid)
            check_dt_utc = check_dt_local.astimezone(UTC)

            has_access = await self._check_day_access(ean, profile, check_dt_utc, headers)

            if has_access:
                first_valid = mid
                high = mid - 1
            else:
                low = mid + 1

            await asyncio.sleep(0.5)

        # Convert the first valid day back to UTC exactly at midnight (if we are on the edge)
        valid_local = from_local + timedelta(days=first_valid)
        valid_utc = valid_local.astimezone(UTC)
        return max(valid_utc, date_from)

    async def _fetch_days_fallback(
        self, ean: str, profile: str, date_from: datetime, date_to: datetime, headers: dict
    ) -> list:
        local_tz = dt_util.get_default_time_zone()
        current_from_local = date_from.astimezone(local_tz)
        temp_from_local = current_from_local.replace(hour=0, minute=0, second=0, microsecond=0)
        temp_from = temp_from_local.astimezone(UTC)

        results = []
        while temp_from < date_to:
            temp_to = min(temp_from + timedelta(days=1), date_to)
            try:
                data = await self._fetch_chunk(ean, profile, temp_from, temp_to, headers)
                if data:
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        results.append(data)
            except EgdApiPermissionError:
                pass
            except Exception as e:
                _LOGGER.error("Error fetching day %s: %s", temp_from, e)
            temp_from = temp_from + timedelta(days=1)
            await asyncio.sleep(0.5)
        return results

    async def _fetch_chunk(
        self, ean: str, profile: str, date_from: datetime, date_to: datetime, headers: dict
    ) -> list:
        str_from = date_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        str_to = date_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        params = {"ean": ean, "profile": profile, "from": str_from, "to": str_to}

        try:
            async with self._session.get(URL_SPOTREBY, headers=headers, params=params) as resp:
                if resp.status == 401:
                    await self.async_get_access_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with self._session.get(
                        URL_SPOTREBY, headers=headers, params=params
                    ) as resp2:
                        if resp2.status != 200:
                            raise EgdApiError(f"HTTP Error {resp2.status} after token refresh")
                        return await resp2.json()
                elif resp.status == 400:
                    data = await resp.json()
                    if "nemáte oprávnění" in data.get("message", ""):
                        raise EgdApiPermissionError(data.get("message"))
                    else:
                        raise EgdApiError(f"HTTP Error 400: {data.get('message')}")
                elif resp.status == 429:
                    raise EgdApiRateLimitError(
                        "HTTP Error 429: Too many requests, please try again later."
                    )
                elif resp.status != 200:
                    text = await resp.text()
                    raise EgdApiError(f"HTTP Error {resp.status}: {text}")
                else:
                    return await resp.json()
        except aiohttp.ClientError as err:
            raise EgdApiError(f"Connection error during data fetch: {err}") from err

    def _parse_and_append(self, data, all_results: list):
        if data:
            # API documentation says it returns a list, but sometimes returns a dict directly
            if not isinstance(data, list):
                data = [data]

            for entry in data:
                if isinstance(entry, dict) and "data" in entry:
                    for point in entry["data"]:
                        if point.get("status") == "W":
                            all_results.append(
                                {"timestamp": point.get("timestamp"), "value": point.get("value")}
                            )
