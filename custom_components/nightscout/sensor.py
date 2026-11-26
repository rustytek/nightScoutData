"""Support for Nightscout sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SENSOR_TYPES
from .coordinator import NightscoutDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class NightscoutDataSensorDescription(SensorEntityDescription):
    """A sensor read from one section ("loop" or "treatments") of the data."""

    section: str
    value_key: str
    attrs: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


# Pump/loop sensors. Keys iob/basal_rate/battery/reservoir keep their
# original unique IDs, so existing entity IDs do not change.
LOOP_SENSORS: tuple[NightscoutDataSensorDescription, ...] = (
    NightscoutDataSensorDescription(
        key="iob",
        name="Insulin on Board",
        icon="mdi:insulin",
        native_unit_of_measurement="U",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        section="loop",
        value_key="iob",
        attrs=lambda d: {"calculated_at": _iso(d.get("iob_time"))},
    ),
    NightscoutDataSensorDescription(
        key="cob",
        name="Carbs on Board",
        icon="mdi:food-apple",
        native_unit_of_measurement="g",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        section="loop",
        value_key="cob",
    ),
    NightscoutDataSensorDescription(
        key="basal_rate",
        name="Basal Rate",
        icon="mdi:insulin",
        native_unit_of_measurement="U/hr",
        state_class=SensorStateClass.MEASUREMENT,
        section="loop",
        value_key="temp_basal_rate",
    ),
    NightscoutDataSensorDescription(
        key="battery",
        name="Pump Battery",
        icon="mdi:battery",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        section="loop",
        value_key="pump_battery",
    ),
    NightscoutDataSensorDescription(
        key="reservoir",
        name="Insulin Remaining",
        icon="mdi:insulin",
        native_unit_of_measurement="U",
        state_class=SensorStateClass.MEASUREMENT,
        section="loop",
        value_key="reservoir",
    ),
    NightscoutDataSensorDescription(
        key="loop_last_run",
        name="Loop Last Run",
        icon="mdi:sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        section="loop",
        value_key="last_run",
        attrs=lambda d: {
            "failure_reason": d.get("failure_reason"),
            "suspended": d.get("suspended"),
            "bolusing": d.get("bolusing"),
            "uploader": d.get("uploader"),
        },
    ),
)

TREATMENT_SENSORS: tuple[NightscoutDataSensorDescription, ...] = (
    NightscoutDataSensorDescription(
        key="last_bolus",
        name="Last Bolus",
        icon="mdi:needle",
        device_class=SensorDeviceClass.TIMESTAMP,
        section="treatments",
        value_key="last_bolus_time",
        attrs=lambda d: {"units": d.get("last_bolus_units")},
    ),
    NightscoutDataSensorDescription(
        key="last_bolus_units",
        name="Last Bolus Amount",
        icon="mdi:needle",
        native_unit_of_measurement="U",
        suggested_display_precision=2,
        section="treatments",
        value_key="last_bolus_units",
    ),
    NightscoutDataSensorDescription(
        key="bolus_today",
        name="Bolus Insulin Today",
        icon="mdi:needle",
        native_unit_of_measurement="U",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        section="treatments",
        value_key="bolus_today",
        attrs=lambda d: {
            "bolus_count": d.get("bolus_count_today"),
            "automatic_bolus_units": d.get("auto_bolus_today"),
            "records_24h": d.get("records_24h"),
            "event_types_24h": d.get("event_types_24h"),
        },
    ),
    NightscoutDataSensorDescription(
        key="carbs_today",
        name="Carbs Today",
        icon="mdi:food-apple",
        native_unit_of_measurement="g",
        state_class=SensorStateClass.TOTAL,
        section="treatments",
        value_key="carbs_today",
    ),
    NightscoutDataSensorDescription(
        key="last_carbs",
        name="Last Carbs",
        icon="mdi:food-apple",
        device_class=SensorDeviceClass.TIMESTAMP,
        section="treatments",
        value_key="last_carbs_time",
        attrs=lambda d: {"grams": d.get("last_carbs_grams")},
    ),
    NightscoutDataSensorDescription(
        key="prebolus_minutes",
        name="Last Meal Pre-bolus",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        section="treatments",
        value_key="prebolus_minutes",
        attrs=lambda d: {
            "bolus_units": d.get("prebolus_bolus_units"),
            "carbs_grams": d.get("last_carbs_grams"),
            "carbs_time": _iso(d.get("last_carbs_time")),
            "note": "positive = bolus before carbs; negative = after; "
            "unknown = no bolus within 90 min of the last carb entry",
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nightscout sensors."""
    coordinator: NightscoutDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[SensorEntity] = []

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

    if entry.data.get("show_pump", True):
        for description in LOOP_SENSORS:
            sensors.append(
                NightscoutDataSensor(
                    coordinator, site_name, entry.entry_id, description
                )
            )

    for description in TREATMENT_SENSORS:
        sensors.append(
            NightscoutDataSensor(coordinator, site_name, entry.entry_id, description)
        )

    # Sensor/cannula age sensors are added regardless of pump status
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


def _device_info(entry_id: str, site_name: str) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, entry_id)},
        "name": f"Nightscout ({site_name})",
        "manufacturer": MANUFACTURER,
    }


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
        self._attr_device_info = _device_info(entry_id, site_name)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and self.entity_description.key in (
            "sgv",
            "sgv_mmol",
            "delta",
            "delta_mmol",
            "direction",
        ):
            return self.coordinator.data[self.entity_description.key]
        return None


class NightscoutDataSensor(CoordinatorEntity, SensorEntity):
    """A sensor read from the parsed loop status or treatment summary."""

    entity_description: NightscoutDataSensorDescription

    def __init__(
        self,
        coordinator: NightscoutDataUpdateCoordinator,
        site_name: str,
        entry_id: str,
        description: NightscoutDataSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry_id, site_name)
        self.entity_description = description

    def _section(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return data.get(self.entity_description.section) or {}

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self._section().get(self.entity_description.value_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs is None:
            return None
        return self.entity_description.attrs(self._section())


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
        self._attr_device_info = _device_info(entry_id, site_name)
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
