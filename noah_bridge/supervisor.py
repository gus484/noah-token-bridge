"""MQTT-Zugangsdaten vom Home-Assistant-Supervisor (Add-on-Betrieb)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Any, Callable, Mapping

from .config import Config, ConfigError

SERVICE_URL = "http://supervisor/services/mqtt"


def fetch_mqtt_service(
    env: Mapping[str, str] | None = None,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> dict | None:
    """Liefert das MQTT-Service-Objekt oder None, wenn kein Supervisor-Token vorhanden ist."""
    env = os.environ if env is None else env
    token = env.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(SERVICE_URL, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=10) as resp:
            body = json.load(resp)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise ConfigError(
            f"MQTT-Dienst des Supervisors nicht erreichbar ({type(exc).__name__}); "
            "ist das Mosquitto-Add-on installiert und gestartet?"
        ) from exc
    data = body.get("data")
    if not isinstance(data, dict) or not data.get("host"):
        raise ConfigError("Supervisor liefert keinen MQTT-Dienst")
    return data


def resolve_mqtt(
    cfg: Config,
    fetch: Callable[[], dict | None] = fetch_mqtt_service,
) -> Config:
    """Explizit gesetzter mqtt_host gewinnt; sonst Supervisor; sonst localhost."""
    if cfg.mqtt_host:
        return cfg
    svc = fetch()
    if not svc:
        return replace(cfg, mqtt_host="localhost")
    return replace(
        cfg,
        mqtt_host=str(svc["host"]),
        mqtt_port=int(svc.get("port") or cfg.mqtt_port),
        mqtt_user=str(svc.get("username") or ""),
        mqtt_password=str(svc.get("password") or ""),
        mqtt_tls=1 if svc.get("ssl") else 0,
    )
