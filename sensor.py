"""Support for Nightscout sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_API_KEY,
    CONF_URL,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NightscoutData
from .const import DOMAIN

SENSOR_TYPES = {
    "bloodSugar": ["Blood Sugar", "mdi:diabetes", "mg/dl"],
    "trend": ["Trend", "mdi:trending-up", "mg/dl/min"],
    "iob": ["IOB", "mdi:medication", "U"],
    "cob": ["COB", "mdi:food", "g"],
    "sage": ["Sensor Age", "mdi:clock", TIME_MINUTES],
    "cage": ["Cannula Age", "mdi:clock", TIME_MINUTES],
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Nightscout platform."""
    if discovery_info is None:
        return

    api: NightscoutData = hass.data[DOMAIN]

    sensors = [
        NightscoutSensor(api, "bloodSugar", "mg/dl"),
        NightscoutSensor(api, "trend", "mg/dl/min"),
        NightscoutSensor(api, "iob", "U"),
        NightscoutSensor(api, "cob", "g"),
        NightscoutSensor(api, "sage", TIME_MINUTES),
        NightscoutSensor(api, "cage", TIME_MINUTES),
    ]

    async_add_entities(sensors, True)


class NightscoutSensor(SensorEntity):
    """Implementation of a Nightscout sensor."""

    def __init__(self, api: NightscoutData, sensor_type: str, unit: str) -> None:
        """Initialize the Nightscout sensor."""
        self._api = api
        self._type = sensor_type
        self._attr_name = f"Nightscout {SENSOR_TYPES[self._type][0]}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = SENSOR_TYPES[self._type][1]
        self._attr_unique_id = f"nightscout_{self._type}"
        self._state = None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self) -> None:
        """Fetch latest state from Nightscout API."""
        try:
            if self._type in ["sage", "cage"]:
                # Fetch device status for sensor and cannula age
                status = await self._api.get_device_status()
                if status and len(status) > 0:
                    device_status = status[0]
                    if "mills" in device_status:
                        mills = device_status["mills"]
                        if self._type == "sage" and "sensorAge" in mills:
                            self._state = mills["sensorAge"]
                        elif self._type == "cage" and "cannulaAge" in mills:
                            self._state = mills["cannulaAge"]
            else:
                # Handle standard sensor types
                if self._type == "bloodSugar":
                    self._state = await self._api.get_sgvs()
                elif self._type == "trend":
                    self._state = await self._api.get_trend()
                elif self._type == "iob":
                    self._state = await self._api.get_iob()
                elif self._type == "cob":
                    self._state = await self._api.get_cob()
        except Exception as err:
            self._state = None
            raise RuntimeError(f"Error updating Nightscout sensor: {err}") from err