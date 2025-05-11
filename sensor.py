"""Support for Nightscout sensors."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MILLIGRAMS_DECILITER,
    EntityCategory,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ALARM_VALUE,
    BASAL_VALUE,
    COB_VALUE,
    CONF_SENSOR_ALARM,
    CONF_SENSOR_BASAL,
    CONF_SENSOR_COB,
    CONF_SENSOR_GL,
    CONF_SENSOR_IOB,
    DOMAIN,
    GLUCOSE_VALUE,
    IOB_VALUE,
    TIME_VALUE,
    TREND_VALUE,
)
from .coordinator import NightscoutDataUpdateCoordinator

TREND_ICONS = {
    "DoubleUp": "mdi:arrow-up-thick",
    "SingleUp": "mdi:arrow-up",
    "FortyFiveUp": "mdi:arrow-top-right",
    "Flat": "mdi:arrow-right",
    "FortyFiveDown": "mdi:arrow-bottom-right",
    "SingleDown": "mdi:arrow-down",
    "DoubleDown": "mdi:arrow-down-thick",
    "None": "mdi:help-rhombus",
    "NOT COMPUTABLE": "mdi:alert",
    "RATE OUT OF RANGE": "mdi:alert-circle",
}


SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    GLUCOSE_VALUE: SensorEntityDescription(
        key=GLUCOSE_VALUE,
        name="Glucose Level",
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_DECILITER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    IOB_VALUE: SensorEntityDescription(
        key=IOB_VALUE,
        name="Insulin on Board",
        native_unit_of_measurement="U",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:medication-outline",
    ),
    COB_VALUE: SensorEntityDescription(
        key=COB_VALUE,
        name="Carbs on Board",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:food-apple",
    ),
    BASAL_VALUE: SensorEntityDescription(
        key=BASAL_VALUE,
        name="Basal Rate",
        native_unit_of_measurement="U/hr",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:doctor",
    ),
    ALARM_VALUE: SensorEntityDescription(
        key=ALARM_VALUE,
        name="Alarm",
        icon="mdi:alarm",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nightscout sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    
    # Add glucose sensor if enabled
    if entry.data.get(CONF_SENSOR_GL, True):
        entities.append(NightscoutGlucoseSensor(coordinator, SENSOR_TYPES[GLUCOSE_VALUE]))
    
    # Add IOB sensor if enabled
    if entry.data.get(CONF_SENSOR_IOB, True):
        entities.append(NightscoutSensor(coordinator, SENSOR_TYPES[IOB_VALUE]))
    
    # Add COB sensor if enabled
    if entry.data.get(CONF_SENSOR_COB, True):
        entities.append(NightscoutSensor(coordinator, SENSOR_TYPES[COB_VALUE]))
    
    # Add basal sensor if enabled
    if entry.data.get(CONF_SENSOR_BASAL, True):
        entities.append(NightscoutSensor(coordinator, SENSOR_TYPES[BASAL_VALUE]))
    
    # Add alarm sensor if enabled
    if entry.data.get(CONF_SENSOR_ALARM, True):
        entities.append(NightscoutBinarySensor(coordinator, SENSOR_TYPES[ALARM_VALUE]))
    
    async_add_entities(entities)


class NightscoutSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Nightscout sensor."""

    coordinator: NightscoutDataUpdateCoordinator
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: NightscoutDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.server_url}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.server_url)},
            name="Nightscout CGM",
            manufacturer="Nightscout",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.coordinator.data and self.entity_description.key in self.coordinator.data:
            return self.coordinator.data[self.entity_description.key]
        return None


class NightscoutGlucoseSensor(NightscoutSensor):
    """Implementation of a Nightscout glucose sensor with trend information."""

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        trend = None
        if self.coordinator.data:
            trend = self.coordinator.data.get(TREND_VALUE)
        
        if trend and trend in TREND_ICONS:
            return TREND_ICONS[trend]
        return self.entity_description.icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        if self.coordinator.data:
            if TREND_VALUE in self.coordinator.data:
                attrs["trend"] = self.coordinator.data[TREND_VALUE]
            if TIME_VALUE in self.coordinator.data:
                attrs["time"] = self.coordinator.data[TIME_VALUE]
        return attrs


class NightscoutBinarySensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Nightscout alarm binary sensor."""

    coordinator: NightscoutDataUpdateCoordinator
    entity_description: SensorEntityDescription
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["active", "inactive"]

    def __init__(
        self,
        coordinator: NightscoutDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.server_url}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.server_url)},
            name="Nightscout CGM",
            manufacturer="Nightscout",
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the binary sensor."""
        if self.coordinator.data and ALARM_VALUE in self.coordinator.data:
            return "active" if self.coordinator.data[ALARM_VALUE] else "inactive"
        return None