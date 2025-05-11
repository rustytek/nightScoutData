"""Constants for the Nightscout Data integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "nightscout"

CONF_SERVER: Final = "server"
CONF_API_KEY: Final = "api_key"
CONF_SENSOR_GL: Final = "sensor_glucose_level"
CONF_SENSOR_IOB: Final = "sensor_iob"
CONF_SENSOR_COB: Final = "sensor_cob"
CONF_SENSOR_BASAL: Final = "sensor_basal"
CONF_SENSOR_ALARM: Final = "sensor_alarm"

DEFAULT_SENSOR_GL: Final = True
DEFAULT_SENSOR_IOB: Final = True
DEFAULT_SENSOR_COB: Final = True
DEFAULT_SENSOR_BASAL: Final = True
DEFAULT_SENSOR_ALARM: Final = True

GLUCOSE_VALUE: Final = "glucose"
IOB_VALUE: Final = "iob"
COB_VALUE: Final = "cob"
BASAL_VALUE: Final = "basal"
TREND_VALUE: Final = "direction"
ALARM_VALUE: Final = "alarm"
TIME_VALUE: Final = "time"

UPDATE_INTERVAL_SECONDS: Final = 300