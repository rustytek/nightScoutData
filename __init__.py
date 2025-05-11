"""The Nightscout integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientError
import async_timeout
from py_nightscout import Api as NightscoutAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nightscout from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    url = entry.data[CONF_URL]
    api_key = entry.data.get(CONF_API_KEY)

    api = NightscoutData(hass, url, api_key)
    coordinator = NightscoutCoordinator(hass, api)

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class NightscoutData:
    """Get data from Nightscout API."""

    def __init__(self, hass: HomeAssistant, url: str, api_key: str | None = None) -> None:
        """Initialize the Nightscout data object."""
        self.hass = hass
        self.api = NightscoutAPI(url, api_key=api_key)

    async def get_sgvs(self):
        """Get sensor glucose values."""
        return await self.api.get_sgvs()

    async def get_trend(self):
        """Get current trend."""
        entries = await self.api.get_sgvs()
        if entries and len(entries) > 0:
            return entries[0].get("trend")
        return None

    async def get_iob(self):
        """Get current IOB."""
        treatments = await self.api.get_treatments()
        if treatments and len(treatments) > 0:
            return treatments[0].get("iob")
        return None

    async def get_cob(self):
        """Get current COB."""
        treatments = await self.api.get_treatments()
        if treatments and len(treatments) > 0:
            return treatments[0].get("cob")
        return None

    async def get_device_status(self):
        """Get device status including sensor and cannula age."""
        try:
            return await self.api.get_devicestatus()
        except Exception as err:
            _LOGGER.error("Error fetching device status: %s", err)
            return None


class NightscoutCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Nightscout data."""

    def __init__(self, hass: HomeAssistant, api: NightscoutData) -> None:
        """Initialize global Nightscout data updater."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from Nightscout."""
        try:
            async with async_timeout.timeout(10):
                data = {
                    "sgvs": await self.api.get_sgvs(),
                    "trend": await self.api.get_trend(),
                    "iob": await self.api.get_iob(),
                    "cob": await self.api.get_cob(),
                    "devicestatus": await self.api.get_device_status(),
                }
                return data
        except ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err