# Noah Token Bridge

*Deutsch: [README.de.md](README.de.md)*

Home Assistant add-on that reads a **Growatt Noah 2000** through the **official Growatt OpenAPI** (API token, no web login) and publishes it via **MQTT Discovery**. It is read-only.

> Unofficial project, not affiliated with or endorsed by Growatt. Use at your own risk.

## Why

Add-ons that log in through the Growatt web interface can end up in endless login retries (e.g. after a captcha was introduced) and put load on Growatt. This bridge uses only the token API and is built not to flood it: hard hourly request cap, minimum gap between requests, exponential backoff per task, no retry loops.

## Install

1. Home Assistant → Settings → Add-ons → Add-on Store → ⋮ → Repositories → add `https://github.com/gus484/noah-token-bridge`.
2. Install **Noah Token Bridge**. Requires the Mosquitto broker add-on (or another broker registered with the Supervisor) and the MQTT integration.
3. On the *Configuration* tab enter your **API token** and the **serial number** of the Noah, then start the add-on.

### Getting the token and serial number
- Token: ShinePhone app → *Me* → your user name → *API Token*.
- Serial number: name plate of the Noah or the app. The API's device list is often empty for the Noah, so the serial must be entered by hand.
- Server: default `https://openapi.growatt.com`. Accounts on another region need that region's server (e.g. `https://openapi-us.growatt.com`).

Stop other Growatt integrations that use the same account (e.g. `noah-mqtt`) first.

## Provides

Device "Growatt Noah 2000" with state of charge, PV/output/battery power, temperatures, per-pack values, settings, WiFi/firmware, plus bridge-internal energy counters (PV, battery charged/discharged; today and total) for the Energy dashboard and derived values (stored energy, time to empty/full, cycles, efficiency). For the Energy dashboard use the *total* entities.

## Limits

- Tested with one Noah 2000 on one account. Other devices (Nexa, multiple Noahs) and installer/distributor tokens are untested.
- No control (output power, SOC limits) yet.
- Entity names are currently German.

Options are documented in [noah_token_bridge/DOCS.md](noah_token_bridge/DOCS.md). Development notes: `CLAUDE.md`, `PLAN.md`.

## Development

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -q
```

License: MIT
