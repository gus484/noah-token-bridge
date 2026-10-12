# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`noah_bridge` polls a Growatt Noah 2000 through the official Growatt OpenAPI v4 (token auth, library `growatt-public-api`, import name `growatt_public_api`) and publishes it to Home Assistant via MQTT Discovery. It replaces `noah-mqtt`, whose web login looped endlessly against Growatt. `PLAN.md` (German) holds the rationale, staged roadmap and open risks; user-facing text, logs and docs are German.

Status: stages 1–3 done (config/models, polling + MQTT, add-on packaging). Stage 4 (control: `number` for output power 0–800 W and SOC limits, `switch` for grid charging and off-grid, always read back after writing because writes may report `SYSTEM_ERROR` yet succeed) is not built. The library has no `setting_write_on_off`.

## Commands

Windows, PowerShell; the venv lives in `venv/` (Python 3.13).

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q                      # all tests
python -m pytest tests/test_poller.py::test_failure_backs_off_exponentially_never_immediately
python test_token.py                     # one-shot API probe, writes redacted samples/*.json (needs GROWATT_TOKEN, optional GROWATT_SN)
python -m noah_bridge                    # run the bridge (needs GROWATT_TOKEN, GROWATT_DEVICE_SN, MQTT_HOST)
python scripts/package_addon.py          # builds dist/noah_token_bridge/ for /addons/
docker compose -f docker/compose.yaml up -d   # test Mosquitto :1883 + Home Assistant :8123 (localhost only)
```

In the compose network the broker host is `mosquitto`; from the host it is `localhost`. The HA MQTT integration must be set up once by hand in the UI. There is no linter configured.

## Architecture

Data flow: `Poller` → `Task.run` = `Bridge.poll_*` → `NoahClient` (library) → parse in `models.py` → `entities.py` builds state/discovery → `MqttPublisher`. `app.Bridge` depends only on a `Publisher` protocol and a client, so tests use fakes plus the real JSON in `samples/`.

Rules the code enforces; keep them intact when changing anything that talks to Growatt:

- **No request flood.** `client.build_api` replaces `requests.Session.request` with `GuardedRequests` (30 s timeout, shared `HourlyLimiter`), so the hourly cap also covers hidden extra calls inside the library. `Poller` makes at most one request per `step()`, keeps `min_gap` 5 s between requests, and a failing task backs off exponentially (`Backoff`, per task) instead of retrying. Only the `primary` task (`energy`) toggles MQTT `availability`.
- **Library cache is off** (`use_cache=False`). Its cache silently returns stale data on rate-limit errors, which would then be published as current.
- **Time is injected** (`clock`, `stop.wait`) in `Poller`, `HourlyLimiter`, `GuardedRequests`; tests drive a fake clock.
- `energy_v4` and `details_v4` allow one call per 5 minutes; `Config.validate` enforces this minimum. `power_realtime` returns `data: null` for this device and is not polled; `plant.list_devices` is empty for this token, so the serial comes from config (`device_sn`).
- **Privacy.** Logs pass `RedactFilter` (token, serial, MQTT password); `Config` hides secrets in `repr`; HA identifiers use `entities.device_id` (hash of the serial). The serial must never appear in topics, payloads or samples; `test_token.py` redacts samples.

Config precedence: env var > `/data/options.json` (add-on) > default. Env names are `GROWATT_<FIELD>` except `MQTT_*` and `DISCOVERY_*`. `supervisor.resolve_mqtt` fills the MQTT connection from the Supervisor `mqtt` service when `mqtt_host` is empty and `SUPERVISOR_TOKEN` is set, else `localhost`.

Energy counters: `energy.EnergyCounters` trapezoid-integrates PV power and battery power (split into charge/discharge) every energy poll, never across gaps longer than 2.5x `energy_interval`, resets "today" at the local date change, and persists to `state_file` (default `/data/noah_state.json` in the add-on, else `./noah_state.json`). `energy.derive` adds stored energy, time to empty/full, cycles, PV direct use and system efficiency; capacity = `capacity_per_pack_kwh` x pack count. These values are merged into the energy state dict, so their entity keys live on the `state/energy` topic.

Entities: `entities.STATIC` plus `pack_entities(n)` (announced once the pack count is known). Every entity's `key` must exist in the state dict published to its topic; `tests/test_app.py` checks this. Discovery is per entity and retained, and is re-sent when HA publishes `homeassistant/status online`. Battery power sign: positive = charging, negative = discharging (seen: -362 W discharging, +56 W charging at 59 W PV). Charging only starts at roughly 55-60 W PV; below that `battery_power` stays 0 although PV is non-zero. Single `pack2_soc` readings of 0.0 occur as API glitches.

Add-on: `addon/` (config.yaml, Dockerfile on `python:3.13-alpine`, no s6/bashio, `init: false`) is combined with `noah_bridge/` and `requirements.txt` by `scripts/package_addon.py`; `dist/` is gitignored. Only aarch64 and amd64 (no armv7 wheels for pydantic-core).

## Gotchas

- Retained discovery messages persist in the Docker broker. After testing with a dummy serial, clear the retained `homeassistant/+/<device_id>/+/config` topics (publish an empty retained payload), otherwise extra devices show up in HA.
- Dummy-serial test devices claim the same `object_id`s, so HA gives the real device suffixed entity_ids (`..._2`). Delete the test devices in HA as well, not only the retained topics.
- Running a second bridge or the old noah-mqtt against the same token causes load on Growatt; stop noah-mqtt (and disable its autostart/watchdog) before live runs.
- `samples/*.json` are redacted real responses used as test fixtures; live values change between refreshes, so tests compare against the raw sample fields rather than hardcoded numbers.
- The Bash tool here rejected a long multi-heredoc command; write files with the Write tool instead.
