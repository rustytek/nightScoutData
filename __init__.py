"""The Nightscout Data integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_SERVER, DOMAIN
from .coordinator import NightscoutDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nightscout Data from a config entry."""
    server_url = entry.data[CONF_SERVER]
    api_key = entry.data.get(CONF_API_KEY)

    _LOGGER.debug("Setting up Nightscout integration with server %s", server_url)
    
    # Create coordinator
    coordinator = NightscoutDataUpdateCoordinator(
        hass=hass,
        server_url=server_url,
        api_key=api_key,
    )

    # Initial data fetch
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed as auth_err:
        _LOGGER.error(
            "Failed to authenticate with Nightscout server %s: %s",
            server_url,
            auth_err
        )
        # Re-raise to let HA handle it
        raise
    except Exception as err:
        _LOGGER.exception(
            "Error during initial data refresh from %s: %s",
            server_url,
            err
        )
        return False

    # Store the coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok