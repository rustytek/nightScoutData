"""DataUpdateCoordinator for the Nightscout integration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from py_nightscout import Api as NightscoutAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

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
        sensor_age = None
        cannula_age = None

        if self.config_entry.data.get("show_sgv", True):
            # Fetch raw JSON instead of api.get_sgvs(): py_nightscout's SGV model
            # divides the optional 'delta' field unguarded (None / 18) and crashes
            # on servers that omit it.
            try:
                entries = await self._fetch_json(
                    "/api/v1/entries/sgv.json", {"count": "2"}
                )
                if entries:
                    latest_entry = entries[0]
                    raw_sgv = latest_entry.get("sgv")
                    if raw_sgv is not None:
                        sgv_mgdl_val = float(raw_sgv)
                        sgv_mmol_val = round(float(raw_sgv) / 18.0, 1)
                    raw_delta = latest_entry.get("delta")
                    if (
                        raw_delta is None
                        and raw_sgv is not None
                        and len(entries) > 1
                        and entries[1].get("sgv") is not None
                    ):
                        raw_delta = float(raw_sgv) - float(entries[1]["sgv"])
                    if raw_delta is not None:
                        delta_mgdl = float(raw_delta)
                        delta_mmol = round(delta_mgdl / 18.0, 2)
                    direction = latest_entry.get("direction")
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.error("Error retrieving Nightscout SGV: %s", error)

        # Raw devicestatus JSON: py_nightscout's model only knows the
        # AndroidAPS/Medtronic layout (pump.iob.bolusiob). Loop puts IOB/COB
        # under "loop", Trio/OpenAPS under "openaps".
        loop_status: dict[str, Any] = {}
        try:
            statuses = await self._fetch_json(
                "/api/v1/devicestatus.json", {"count": "1"}
            )
            if statuses:
                loop_status = parse_loop_status(statuses[0])
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Error retrieving Nightscout device status: %s", error)

        treatments_summary: dict[str, Any] = {}
        try:
            since = (dt_util.utcnow() - timedelta(hours=24)).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            )
            treatments = await self._fetch_json(
                "/api/v1/treatments.json",
                {"find[created_at][$gte]": since, "count": "500"},
            )
            if treatments is not None:
                treatments_summary = summarize_treatments(
                    treatments, dt_util.start_of_local_day()
                )
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Error summarizing Nightscout treatments: %s", error)

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
            "server": server_status,
            "sensor_age": sensor_age,
            "cannula_age": cannula_age,
            "loop": loop_status,
            "treatments": treatments_summary,
        }

    async def _fetch_json(self, path: str, params: dict[str, str]) -> Any:
        """Fetch raw JSON from the Nightscout API, bypassing py_nightscout models."""
        session = self.api._session
        if session is None:
            return None
        url = f"{self.api.server_url}{path}"
        async with session.get(url, params=params, **self.api._api_kwargs) as resp:
            if resp.status != 200:
                return None
            return await resp.json()

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


def _parse_ts(value: Any) -> datetime | None:
    """Parse a Nightscout ISO timestamp (or epoch ms) into an aware datetime."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _num(value: Any) -> float | None:
    """Return value as float, or None."""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def parse_loop_status(status: dict[str, Any]) -> dict[str, Any]:
    """Pull IOB/COB/loop/pump data out of one devicestatus record.

    Handles Loop ("loop"), Trio/OpenAPS ("openaps") and the older
    AndroidAPS/Medtronic layout ("pump.iob").
    """
    loop = status.get("loop") or {}
    openaps = status.get("openaps") or {}
    pump = status.get("pump") or {}

    loop_iob = loop.get("iob") or {}
    iob = _num(loop_iob.get("iob"))
    iob_time = _parse_ts(loop_iob.get("timestamp"))
    if iob is None:
        oa_iob = openaps.get("iob") or {}
        if isinstance(oa_iob, list):
            oa_iob = oa_iob[0] if oa_iob else {}
        iob = _num(oa_iob.get("iob"))
        iob_time = _parse_ts(oa_iob.get("time") or oa_iob.get("timestamp"))
    if iob is None:
        p_iob = pump.get("iob") or {}
        iob = _num(p_iob.get("bolusiob", p_iob.get("iob")))
        iob_time = _parse_ts(p_iob.get("timestamp"))

    cob = _num((loop.get("cob") or {}).get("cob"))
    if cob is None:
        cob = _num((openaps.get("suggested") or {}).get("COB"))

    enacted = loop.get("enacted") or openaps.get("enacted") or {}
    battery = pump.get("battery")
    if isinstance(battery, dict):
        battery = battery.get("percent")
    extended = pump.get("extended") or {}

    return {
        "iob": iob,
        "iob_time": iob_time,
        "cob": cob,
        "last_run": _parse_ts(loop.get("timestamp"))
        or _parse_ts((openaps.get("suggested") or {}).get("timestamp"))
        or _parse_ts(status.get("created_at")),
        "failure_reason": loop.get("failureReason"),
        "temp_basal_rate": _num(enacted.get("rate"))
        if enacted.get("rate") is not None
        else _num(extended.get("TempBasalAbsoluteRate")),
        "suspended": pump.get("suspended"),
        "bolusing": pump.get("bolusing"),
        # Omnipod reports no reservoir level above 50 U, so None is normal.
        "reservoir": _num(pump.get("reservoir")),
        "pump_battery": _num(battery),
        "uploader": status.get("device"),
    }


# Loop uploads every bolus as "Correction Bolus"; automatic (auto-bolus
# dosing strategy) ones carry automatic=true.
_BOLUS_TYPES = ("Correction Bolus", "Meal Bolus", "Bolus", "Snack Bolus", "SMB")
_CARB_TYPES = ("Carb Correction", "Meal Bolus", "Snack Bolus")
# Pair the latest carb entry with the nearest manual bolus inside this window.
PREBOLUS_WINDOW = timedelta(minutes=90)


def summarize_treatments(
    treatments: list[dict[str, Any]], day_start: datetime
) -> dict[str, Any]:
    """Summarize recent treatments into bolus and carb figures."""
    boluses: list[tuple[datetime, float, bool]] = []
    carbs: list[tuple[datetime, float]] = []
    for item in treatments:
        when = _parse_ts(item.get("created_at") or item.get("timestamp"))
        if when is None:
            continue
        event = item.get("eventType")
        insulin = _num(item.get("insulin"))
        if insulin and insulin > 0 and (event in _BOLUS_TYPES or event is None):
            automatic = bool(item.get("automatic")) or event == "SMB"
            boluses.append((when, insulin, automatic))
        grams = _num(item.get("carbs"))
        if grams and grams > 0 and (event in _CARB_TYPES or event is None):
            carbs.append((when, grams))
    boluses.sort(key=lambda b: b[0], reverse=True)
    carbs.sort(key=lambda c: c[0], reverse=True)
    manual = [b for b in boluses if not b[2]]
    today_manual = [b for b in manual if b[0] >= day_start]

    summary: dict[str, Any] = {
        "last_bolus_time": manual[0][0] if manual else None,
        "last_bolus_units": manual[0][1] if manual else None,
        "bolus_today": round(sum(b[1] for b in today_manual), 2),
        "bolus_count_today": len(today_manual),
        "auto_bolus_today": round(
            sum(b[1] for b in boluses if b[2] and b[0] >= day_start), 2
        ),
        "carbs_today": round(sum(c[1] for c in carbs if c[0] >= day_start), 1),
        "last_carbs_time": carbs[0][0] if carbs else None,
        "last_carbs_grams": carbs[0][1] if carbs else None,
        "prebolus_minutes": None,
        "prebolus_bolus_units": None,
    }
    if carbs:
        carb_time = carbs[0][0]
        near = [b for b in manual if abs(b[0] - carb_time) <= PREBOLUS_WINDOW]
        if near:
            best = min(near, key=lambda b: abs(b[0] - carb_time))
            # Positive = bolus given before the carbs (pre-bolus);
            # negative = bolus given after eating.
            summary["prebolus_minutes"] = round(
                (carb_time - best[0]).total_seconds() / 60
            )
            summary["prebolus_bolus_units"] = best[1]
    return summary
