"""Sensor type definitions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTime,
)

DOMAIN: Final = "nightscout"
MANUFACTURER: Final = "Nightscout"

# Define missing constants directly
CONCENTRATION_MILLIGRAMS_PER_DECILITER = "mg/dL"

SENSOR_TYPES: Final[dict[str, SensorEntityDescription]] = {
    "sgv": SensorEntityDescription(
        key="sgv",
        name="Blood Sugar",
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_DECILITER,
        icon="mdi:diabetes",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "sgv_mmol": SensorEntityDescription(
        key="sgv_mmol",
        name="Blood Sugar mmol/L",
        native_unit_of_measurement="mmol/L",
        icon="mdi:diabetes",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "delta": SensorEntityDescription(
        key="delta",
        name="Blood Sugar Delta",
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_DECILITER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "delta_mmol": SensorEntityDescription(
        key="delta_mmol",
        name="Blood Sugar Delta mmol/L",
        native_unit_of_measurement="mmol/L",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "direction": SensorEntityDescription(
        key="direction",
        name="Blood Sugar Direction",
        icon="mdi:diabetes",
    ),
    "iob": SensorEntityDescription(
        key="iob",
        name="Insulin on Board",
        icon="mdi:insulin",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "basal_rate": SensorEntityDescription(
        key="basal_rate",
        name="Basal Rate",
        native_unit_of_measurement="U/hr",
        icon="mdi:insulin",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        name="Pump Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "reservoir": SensorEntityDescription(
        key="reservoir",
        name="Insulin Remaining",
        icon="mdi:insulin",
        native_unit_of_measurement="U",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "sensor_age": SensorEntityDescription(
        key="sensor_age",
        name="Sensor Age",
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "cannula_age": SensorEntityDescription(
        key="cannula_age",
        name="Cannula Age",
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}