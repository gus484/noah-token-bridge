"""Konfiguration aus Umgebungsvariablen und optional /data/options.json (HA-Add-on).

Reihenfolge: Umgebungsvariable > options.json > Standardwert.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping

OPTIONS_PATH = Path("/data/options.json")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    token: str = field(repr=False)
    device_sn: str = field(repr=False)
    server_url: str = ""  # leer = https://openapi.growatt.com (Region/Server des Kontos)
    mqtt_host: str = ""  # leer = Supervisor-Dienst (Add-on) oder localhost
    mqtt_port: int = 1883
    mqtt_user: str = ""
    mqtt_password: str = field(default="", repr=False)
    mqtt_tls: int = 0
    mqtt_prefix: str = "noah_bridge"
    discovery_prefix: str = "homeassistant"
    entity_prefix: str = "noah_2000"  # Praefix der entity_ids in Home Assistant
    capacity_per_pack_kwh: float = 2.048  # nutzbar fuer Restlaufzeit und gespeicherte Energie
    state_file: str = ""  # Zaehlerstaende; leer = /data/noah_state.json (Add-on) oder ./noah_state.json
    # Abfrageintervalle in Sekunden
    energy_interval: int = 300
    details_interval: int = 900
    slow_interval: int = 3600
    # Harte Obergrenze fuer Requests pro Stunde, unabhaengig von den Intervallen
    max_requests_per_hour: int = 60
    backoff_start: int = 60
    backoff_max: int = 1800
    log_level: str = "INFO"

    def validate(self) -> None:
        if not self.token:
            raise ConfigError("token fehlt (GROWATT_TOKEN)")
        if not self.device_sn:
            raise ConfigError("device_sn fehlt (GROWATT_DEVICE_SN)")
        if self.server_url and not self.server_url.startswith(("https://", "http://")):
            raise ConfigError("server_url muss mit https:// beginnen")
        # energy_v4 und details_v4 sind laut Growatt auf einen Abruf je 5 Minuten begrenzt
        for name, minimum in (("energy_interval", 300), ("details_interval", 300), ("slow_interval", 60)):
            if getattr(self, name) < minimum:
                raise ConfigError(f"{name} muss mindestens {minimum} Sekunden betragen")
        if self.capacity_per_pack_kwh <= 0:
            raise ConfigError("capacity_per_pack_kwh muss groesser als 0 sein")
        if self.max_requests_per_hour < 1:
            raise ConfigError("max_requests_per_hour muss mindestens 1 sein")
        if not 0 < self.backoff_start <= self.backoff_max:
            raise ConfigError("backoff_start muss > 0 und <= backoff_max sein")
        if self.log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ConfigError(f"unbekanntes log_level: {self.log_level}")


def _env_name(key: str) -> str:
    # mqtt_* und discovery_* bleiben MQTT_* / DISCOVERY_*, alles andere GROWATT_*
    return key.upper() if key.startswith(("mqtt_", "discovery_")) else f"GROWATT_{key.upper()}"


def load_config(
    env: Mapping[str, str] | None = None,
    options_path: Path | None = None,
) -> Config:
    env = os.environ if env is None else env
    path = OPTIONS_PATH if options_path is None else options_path
    options: dict[str, Any] = {}
    if path.is_file():
        try:
            options = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"{path} nicht lesbar: {exc}") from exc

    values: dict[str, Any] = {}
    for f in fields(Config):
        raw = env.get(_env_name(f.name), options.get(f.name))
        if raw is None or raw == "":
            continue
        try:
            if f.type in (int, "int"):
                values[f.name] = int(raw)
            elif f.type in (float, "float"):
                values[f.name] = float(raw)
            else:
                values[f.name] = str(raw)
        except ValueError as exc:
            raise ConfigError(f"{f.name}: ungueltiger Wert") from exc
    values.setdefault("token", "")
    values.setdefault("device_sn", "")
    cfg = Config(**values)
    cfg.validate()
    return cfg
