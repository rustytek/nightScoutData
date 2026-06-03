# nightScoutData

## Project Overview
Custom Home Assistant integration (`custom_components/nightscout`) for pulling CGM and Omnipod data from Nightscout into HA sensors. Owned by @rustytek. Also includes the `nightscout_sensors.yaml` REST sensor configuration deployed to the HA config directory.

## Security Rules

**NEVER open `secrets.yaml`, `.env`, or any file containing credentials.** If secret values are needed (API keys, URLs, passwords), ask the user to provide the specific values. User had to rotate credentials after a file read — this is a hard rule.

## Integration Architecture

- `custom_components/nightscout/` — HA custom integration (domain: `nightscout`)
  - Polls Nightscout API every 1 min for SGV, pump status, sensor/cannula age
  - Config entry created via UI config flow (URL + optional API key)
  - No reconfigure flow currently — to change URL, delete entry and re-add

- `nightscout_sensors.yaml` — REST sensor config tracked in this repo and deployed to `/config/` on HA
  - Fetches last 5 treatments from Nightscout treatments API
  - Creates `sensor.amelia_omnipod_last_change`, `sensor.amelia_dexcom_last_change`, and Ethan equivalents
  - URLs stored as `!secret nightscout_amelia_url` and `!secret nightscout_ethan_url` in HA secrets.yaml
  - Template sensors in `configuration.yaml` derive pod/sensor due dates from these REST sensors
  - After editing, deploy to HA via Samba (`\\192.168.0.156\config\`) and run `rest.reload` service
  - **Gotcha:** if these entities are ever disabled via Settings → Entities in the HA UI, the pod/sensor change automations will silently stop firing (no traces). Re-enable via `ha_set_entity(enabled=True)` then call `rest.reload`.

## Local Nightscout Add-ons (HAOS)

Two Nightscout add-ons run locally on the HA host — both are installed and running but phones/devices still upload to nightscoutpro.com (cloud). Migration to local is pending.

| Port | Slug | Child | auth_default_roles |
|------|------|-------|--------------------|
| 5423 | `9a608f85_nightscout` | **Amelia** | `devicestatus-upload` |
| 5433 | `8ac0fd6f_nightscout` | **Ethan** | `readable` |

API key for both instances is the same (in HA secrets.yaml).

## Migration Checklist (cloud → local, not yet done)

When phones/devices are ready to migrate off nightscoutpro.com:

1. **Migrate devices first** — update Omnipod/Dexcom uploader on each kid's phone to point at the local Nightscout URL (`https://HA_IP:5423` for Amelia, `https://HA_IP:5433` for Ethan). Confirm data is flowing locally before touching HA.

2. **Update secrets.yaml** — change these four secrets:
   - `nightscout_amelia_url` → `https://192.168.0.156:5423/api/v1/treatments?count=5&...&token=LOCAL_TOKEN`
   - `nightscout_ethan_url` → `https://192.168.0.156:5433/api/v1/treatments?count=5&...` (port 5433 is `readable`, token may not be needed)
   - `nightscout_amelia_analysis_url` → `https://192.168.0.156:5423`
   - `nightscout_ethan_analysis_url` → `https://192.168.0.156:5433`

3. **Reload REST sensors** — HA UI → Developer Tools → YAML → Reload REST entities (or full restart).

4. **Re-create the custom integration config entry** — the integration has no reconfigure flow; delete the existing entry in Settings → Integrations → Nightscout, then re-add it with the local URL. Local tokens will differ from the cloud `drg-*` tokens — use the local API key or generate a new subject token on the local instance.

5. **Reload the custom component** — after deploying updated coordinator.py (NoneType SGV fix), reload via Settings → Integrations → Nightscout → Reload.

6. **Update automation descriptions** — several automation `description` fields still reference `amelia.nightscoutpro.com` / `ethanr.nightscoutpro.com`. Update for accuracy after migration.
