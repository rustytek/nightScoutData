"""DataUpdateCoordinator for the Nightscout integration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from py_nightscout import Api as NightscoutAPI

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

        if self.config_entry.data.get("show_sgv", True):
            try:
                sgv_response = await self.api.get_sgvs()
                if sgv_response:
                    entry = sgv_response[0]
                    sgv_mgdl_val = float(entry.sgv)
                    sgv_mmol_val = float(entry.sgv_mmol)
                    raw_delta = getattr(entry, "delta", None)
                    if raw_delta is not None:
                        delta_mgdl = float(raw_delta)
                        delta_mmol = round(delta_mgdl / 18.0, 2)
                    direction = entry.direction
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error("Error retrieving Nightscout SGV: %s", error)

        try:
            device_status_response = await self.api.get_devices_status()
            if device_status_response:
                latest = device_status_response[0]
                if hasattr(latest, "pump") and latest.pump:
                    device_status = latest.pump
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Error retrieving Nightscout device status: %s", error)

        sensor_age = await self._get_treatment_age("Sensor Change")
        cannula_age = await self._get_treatment_age("Site Change")

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

    async def _get_treatment_age(self, event_type: str) -> float | None:
        """Return hours elapsed since the most recent treatment of the given event type."""
        try:
            session = self.api._session
            if session is None:
                return None
            url = f"{self.api.server_url}/api/v1/treatments.json"
            params = {"find[eventType]": event_type, "count": "1"}
            async with session.get(url, params=params, **self.api._api_kwargs) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not data:
                    return None
                created_at = data[0].get("created_at")
                if not created_at:
                    return None
                ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
                return round(age_hours, 1)
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Error calculating %s age: %s", event_type, error)
            return None
