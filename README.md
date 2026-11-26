# nightScoutData

Custom Home Assistant integration (`custom_components/nightscout`) for pulling CGM and Omnipod data from Nightscout into HA sensors, plus the `nightscout_sensors.yaml` REST sensor configuration deployed alongside it.

## Contents

- `custom_components/nightscout/` — HA custom integration (domain: `nightscout`). Polls the Nightscout API every minute for SGV, insulin/carbs on board (Loop, Trio or AndroidAPS uploads), loop last-run, pump status, sensor/cannula age, and a 24 h treatment summary: last bolus, bolus insulin today, carbs today, last carbs and the last meal's pre-bolus time. Configured via the HA UI config flow (URL + optional API key), one entry per Nightscout site; installed through HACS.
- `nightscout_sensors.yaml` — REST sensor config tracked here and deployed to the HA `/config/` directory. Fetches recent treatments from the Nightscout treatments API and derives pod/sensor "last change" and "change due" sensors for each tracked child.

## Status

Two local Nightscout add-ons run on the HA host as a future replacement for the current cloud (nightscoutpro.com) uploads; migration to local is not yet complete. See `CLAUDE.md` for the full migration checklist, add-on details, and operational gotchas (e.g. re-enabling REST sensors after they're disabled in the UI).

## Development Notes

See `CLAUDE.md` (or `AGENTS.md`) for architecture details, the local Nightscout add-on table, and the cloud-to-local migration checklist.
