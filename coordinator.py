"""DataUpdateCoordinator for the Nightscout Data integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, cast

import aiohttp

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    ALARM_VALUE,
    BASAL_VALUE,
    COB_VALUE,
    DOMAIN,
    GLUCOSE_VALUE,
    IOB_VALUE,
    TIME_VALUE,
    TREND_VALUE,
    UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class NightscoutDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Nightscout Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        server_url: str,
        api_key: str | None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        if not server_url.endswith("/"):
            server_url += "/"
        self.server_url = server_url
        self.api_key = api_key

    def _get_url(self, path: str) -> str:
        """Get full URL with API key if needed."""
        url = f"{self.server_url}{path}"
        
        # Check if URL already has query parameters
        if "?" in url:
            # If URL already has parameters, append with &
            if self.api_key:
                url += f"&token={self.api_key}"
        else:
            # If no parameters yet, use ? to start query string
            if self.api_key:
                url += f"?token={self.api_key}"
                
        _LOGGER.debug("Generated URL: %s", url.replace(self.api_key or "", "[REDACTED]"))
        return url

    def _process_entries(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Process entries and return the latest data."""
        if not entries:
            return {}
        
        latest_entry = entries[0]
        
        data = {
            GLUCOSE_VALUE: latest_entry.get("sgv"),
            TIME_VALUE: latest_entry.get("dateString"),
            TREND_VALUE: latest_entry.get("direction"),
        }
        
        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Nightscout API."""
        session_timeout = aiohttp.ClientTimeout(total=10)
        result: dict[str, Any] = {}
        
        try:
            async with aiohttp.ClientSession(timeout=session_timeout) as session:
                # Fetch glucose data
                glucose_url = self._get_url("api/v1/entries/sgv?count=1")
                async with session.get(glucose_url) as resp:
                    if resp.status == 401 or resp.status == 403:
                        _LOGGER.error("Authentication failed for Nightscout. Check your API key.")
                        raise ConfigEntryAuthFailed(f"Authentication failed with status code: {resp.status}. Verify your API key.")
                    
                    if resp.status != 200:
                        error_text = await resp.text()
                        error_message = f"Error fetching glucose data: Status {resp.status}. Response: {error_text[:200]}"
                        _LOGGER.error(error_message)
                        raise UpdateFailed(error_message)
                    
                    try:
                        entries = await resp.json()
                        glucose_data = self._process_entries(entries)
                        result.update(glucose_data)
                    except Exception as e:
                        _LOGGER.error("Error parsing glucose data: %s", str(e))
                        raise UpdateFailed(f"Failed to parse glucose data: {str(e)}")
                
                # Fetch treatment data for IOB, COB and basal
                treatments_url = self._get_url("api/v1/treatments?count=1")
                async with session.get(treatments_url) as resp:
                    if resp.status != 200:
                        _LOGGER.warning(
                            "Error fetching treatment data: %s", resp.status
                        )
                    else:
                        treatments = await resp.json()
                        if treatments:
                            latest = treatments[0]
                            result[IOB_VALUE] = latest.get("insulin")
                            result[COB_VALUE] = latest.get("carbs")
                            result[BASAL_VALUE] = latest.get("rate")
                
                # Fetch status for alarms
                status_url = self._get_url("api/v1/status")
                async with session.get(status_url) as resp:
                    if resp.status != 200:
                        _LOGGER.warning(
                            "Error fetching status data: %s", resp.status
                        )
                    else:
                        status = await resp.json()
                        result[ALARM_VALUE] = status.get("status") == "warn"
                
                return result
        
        except aiohttp.ClientError as error:
            raise UpdateFailed(f"Error communicating with API: {error}")