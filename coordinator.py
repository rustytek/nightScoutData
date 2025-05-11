"""DataUpdateCoordinator for the Nightscout integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, cast

from py_nightscout import Api as NightscoutAPI
# Remove the specific models import that's causing the error
# from py_nightscout.models import SGV, DeviceStatus, NightscoutStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NightscoutDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The Nightscout Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: NightscoutAPI, entry: ConfigEntry
    ) -> None:
        """Initialize the Nightscout coordinator."""
        self.api = api
        self.config_entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Nightscout."""
        sgv_mgdl_val = None
        sgv_mmol_val = None
        delta_mgdl = None
        delta_mmol = None
        direction = None
        device_status = {}
        sensor_age = None
        cannula_age = None

        # Only attempt to retrieve SGV values if enabled
        if self.config_entry.data.get("show_sgv", True):
            try:
                sgv_response = await self.api.get_sgvs(count=1)
                if sgv_response:
                    sgv_mgdl_val = cast(float, sgv_response[0].sgv)
                    sgv_mmol_val = cast(float, sgv_response[0].mmol)
                    delta_mgdl = cast(float, sgv_response[0].bgdelta)
                    delta_mmol = delta_mgdl / 18.0
                    direction = sgv_response[0].direction
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error("Error retrieving Nightscout SGV: %s", error)

        # Retrieve the device status which contains pump info
        try:
            device_status_response = await self.api.get_device_status()
            if device_status_response:
                # Extract existing pump info (for iob, basal, etc.)
                if hasattr(device_status_response[0], "pump"):
                    device_status = device_status_response[0].pump

                # Extract SAGE and CAGE if available
                # These are typically stored in the pump status or device status
                # The exact location depends on Nightscout setup and pump type
                for status in device_status_response:
                    # For OpenAPS and Loop integration
                    if hasattr(status, "pump") and status.pump:
                        pump_status = status.pump
                        if hasattr(pump_status, "reservoir"):
                            # Check for Loop/OpenAPS format
                            if hasattr(pump_status, "clock"):
                                # Try to find sage/cage in different possible locations
                                if hasattr(pump_status, "status") and pump_status.status:
                                    if "cage" in pump_status.status:
                                        cannula_age = float(pump_status.status["cage"]) / 3600  # Convert to hours
                                    if "sage" in pump_status.status:
                                        sensor_age = float(pump_status.status["sage"]) / 3600  # Convert to hours
                    
                    # For xDrip and other systems that report directly in devicestatus
                    if hasattr(status, "cage") and status.cage is not None:
                        cannula_age = float(status.cage) / 3600  # Convert to hours
                    if hasattr(status, "sage") and status.sage is not None:
                        sensor_age = float(status.sage) / 3600  # Convert to hours
                    
                    # Check in a common nested location
                    if hasattr(status, "device") and status.device:
                        if hasattr(status.device, "cage") and status.device.cage is not None:
                            cannula_age = float(status.device.cage) / 3600
                        if hasattr(status.device, "sage") and status.device.sage is not None:
                            sensor_age = float(status.device.sage) / 3600

        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Error retrieving Nightscout device status: %s", error)

        # Get the server status
        server_status = {}
        try:
            server_status_response = await self.api.get_server_status()
            if server_status_response:
                server_status = server_status_response
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Error retrieving Nightscout status: %s", error)

        return {
            "sgv": sgv_mgdl_val,
            "sgv_mmol": sgv_mmol_val,
            "delta": delta_mgdl,
            "delta_mmol": delta_mmol,
            "direction": direction,
            "device": device_status,
            "server": server_status,
            "sensor_age": sensor_age,
            "cannula_age": cannula_age,
        }