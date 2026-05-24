"""Support for Nightscout sensors."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SENSOR_TYPES
from .coordinator import NightscoutDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nightscout sensors."""
    coordinator: NightscoutDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    
    # Get site name, with fallback to the URL or a default value
    site_name = entry.data.get("site_name", entry.data.get("url", "Nightscout"))

    # Add 'regular' glucose sensors
    if entry.data.get("show_sgv", True):
        for sensor_type in (
            "sgv",
            "sgv_mmol",
            "delta",
            "delta_mmol",
            "direction",
        ):
            sensors.append(
                NightscoutSensor(
                    coordinator,
                    site_name,
                    coordinator.config_entry.entry_id,
                    SENSOR_TYPES[sensor_type],
                )
            )

    # If pump enabled, add pump sensors
    if entry.data.get("show_pump", True):
        # Add standard pump sensors like iob, basal, etc.
        for sensor_type in (
            "reservoir",
            "battery",
            "iob",
            "basal_rate",
        ):
            sensors.append(
                NightscoutPumpSensor(
                    coordinator,
                    site_name,
                    coordinator.config_entry.entry_id,
                    SENSOR_TYPES[sensor_type],
                )
            )

    # Add the new sensor age sensors regardless of pump status
    # These are separate entities that should be available even if pump data isn't shown
    sensors.append(
        NightscoutAgeSensor(
            coordinator,
            site_name,
            coordinator.config_entry.entry_id,
            SENSOR_TYPES["sensor_age"],
            "sensor_age",
        )
    )
    
    sensors.append(
        NightscoutAgeSensor(
            coordinator,
            site_name,
            coordinator.config_entry.entry_id,
            SENSOR_TYPES["cannula_age"],
            "cannula_age",
        )
    )

    async_add_entities(sensors)


class NightscoutSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Nightscout sensor."""

    def __init__(
        self,
        coordinator: NightscoutDataUpdateCoordinator,
        site_name: str,
        entry_id: str,
        description,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"Nightscout ({site_name})",
            "manufacturer": MANUFACTURER,
        }
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        # Make sure we handle None values for missing sgv values
        if self.entity_description.key == "sgv" and self.coordinator.data:
            return self.coordinator.data["sgv"]
        if self.entity_description.key == "sgv_mmol" and self.coordinator.data:
            return self.coordinator.data["sgv_mmol"]
        if self.entity_description.key == "delta" and self.coordinator.data:
            return self.coordinator.data["delta"]
        if self.entity_description.key == "delta_mmol" and self.coordinator.data:
            return self.coordinator.data["delta_mmol"]
        if self.entity_description.key == "direction" and self.coordinator.data:
            return self.coordinator.data["direction"]
        return None


class NightscoutPumpSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Nightscout pump sensor."""

    def __init__(
        self,
        coordinator: NightscoutDataUpdateCoordinator,
        site_name: str,
        entry_id: str,
        description,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"Nightscout ({site_name})",
            "manufacturer": MANUFACTURER,
        }
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if (
            not self.coordinator.data
            or "device" not in self.coordinator.data
            or not self.coordinator.data["device"]
        ):
            return None

        pump_status = self.coordinator.data["device"]

        if self.entity_description.key == "reservoir" and hasattr(
            pump_status, "reservoir"
        ):
            return cast(float, pump_status.reservoir)
        if self.entity_description.key == "battery" and hasattr(pump_status, "battery"):
            return cast(float, pump_status.battery)
        if self.entity_description.key == "iob" and hasattr(pump_status, "iob"):
            if hasattr(pump_status.iob, "bolusiob"):
                return cast(float, pump_status.iob.bolusiob)
        if self.entity_description.key == "basal_rate" and hasattr(
            pump_status, "extended"
        ):
            if hasattr(pump_status.extended, "TempBasalAbsoluteRate"):
                return cast(float, pump_status.extended.TempBasalAbsoluteRate)

        return None


class NightscoutAgeSensor(CoordinatorEntity, SensorEntity):
    """Implementation of an Nightscout age sensor."""

    def __init__(
        self,
        coordinator: NightscoutDataUpdateCoordinator,
        site_name: str,
        entry_id: str,
        description,
        data_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"Nightscout ({site_name})",
            "manufacturer": MANUFACTURER,
        }
        self.entity_description = description
        self._data_key = data_key

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and self._data_key in self.coordinator.data:
            return self.coordinator.data[self._data_key]
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Only mark as unavailable if the coordinator itself is unavailable
        # Sometimes the sensor/cannula age might be None which is expected
        return self.coordinator.last_update_success