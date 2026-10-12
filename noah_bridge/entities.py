"""Home-Assistant-Entitaeten (MQTT Discovery) und Zustandsthemen."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .models import DetailsSnapshot, EnergySnapshot

# Zustandsthemen (Suffix hinter dem Praefix)
ENERGY, DETAILS, WIFI, FIRMWARE = "state/energy", "state/details", "state/wifi", "state/firmware"


@dataclass(frozen=True)
class Entity:
    key: str
    name: str
    topic: str
    platform: str = "sensor"
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    category: str | None = None  # "diagnostic"
    icon: str | None = None
    precision: int | None = None

    @property
    def template(self) -> str:
        return "{{ value_json.%s }}" % self.key


S = Entity
STATIC: tuple[Entity, ...] = (
    S("soc", "Ladestand", ENERGY, unit="%", device_class="battery", state_class="measurement"),
    S("pv_power", "PV-Leistung", ENERGY, unit="W", device_class="power", state_class="measurement"),
    S("output_power", "Ausgangsleistung", ENERGY, unit="W", device_class="power", state_class="measurement"),
    S("battery_power", "Akkuleistung", ENERGY, unit="W", device_class="power", state_class="measurement"),
    S("energy_today", "Energie heute", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=2),
    S("energy_month", "Energie Monat", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=1),
    S("energy_year", "Energie Jahr", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=1),
    S("energy_total", "Energie gesamt", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=1),
    S("cycles", "Ladezyklen", ENERGY, state_class="total_increasing", category="diagnostic", icon="mdi:battery-sync"),
    S("health", "Akkugesundheit", ENERGY, unit="%", state_class="measurement", category="diagnostic", icon="mdi:battery-heart-variant"),
    S("system_temperature", "Systemtemperatur", ENERGY, unit="°C", device_class="temperature", state_class="measurement", category="diagnostic"),
    S("status", "Status", ENERGY, category="diagnostic", icon="mdi:information-outline"),
    S("work_mode", "Betriebsmodus", ENERGY, category="diagnostic", icon="mdi:cog-outline"),
    S("charging_status", "Ladestatus (roh)", ENERGY, category="diagnostic", icon="mdi:battery-charging-outline"),
    S("pv1_voltage", "PV1 Spannung", ENERGY, unit="V", device_class="voltage", state_class="measurement", category="diagnostic"),
    S("pv1_current", "PV1 Strom", ENERGY, unit="A", device_class="current", state_class="measurement", category="diagnostic"),
    S("pv2_voltage", "PV2 Spannung", ENERGY, unit="V", device_class="voltage", state_class="measurement", category="diagnostic"),
    S("pv2_current", "PV2 Strom", ENERGY, unit="A", device_class="current", state_class="measurement", category="diagnostic"),
    S("pv_energy_today", "PV-Energie heute", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=2),
    S("pv_energy_total", "PV-Energie gesamt", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=1),
    S("battery_charged_today", "Akku geladen heute", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=2),
    S("battery_charged_total", "Akku geladen gesamt", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=1),
    S("battery_discharged_today", "Akku entladen heute", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=2),
    S("battery_discharged_total", "Akku entladen gesamt", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=1),
    S("pv_direct_today", "PV direkt genutzt heute", ENERGY, unit="kWh", device_class="energy", state_class="total_increasing", precision=2),
    S("cycles_today", "Vollzyklen heute", ENERGY, state_class="total_increasing", icon="mdi:battery-sync", precision=2),
    S("stored_energy", "Gespeicherte Energie", ENERGY, unit="kWh", device_class="energy_storage", state_class="measurement", precision=2),
    S("time_to_empty", "Restlaufzeit Akku", ENERGY, unit="h", device_class="duration", state_class="measurement", precision=1),
    S("time_to_full", "Zeit bis Akku voll", ENERGY, unit="h", device_class="duration", state_class="measurement", precision=1),
    S("system_efficiency_today", "Systemwirkungsgrad heute", ENERGY, unit="%", state_class="measurement", category="diagnostic", precision=1, icon="mdi:percent"),
    S("last_update", "Letzte Aktualisierung", ENERGY, device_class="timestamp", category="diagnostic"),
    S("soc_upper_limit", "SOC-Obergrenze", DETAILS, unit="%", category="diagnostic", icon="mdi:battery-arrow-up"),
    S("soc_lower_limit", "SOC-Untergrenze", DETAILS, unit="%", category="diagnostic", icon="mdi:battery-arrow-down"),
    S("allow_grid_charging", "Netzladen erlaubt", DETAILS, platform="binary_sensor", category="diagnostic"),
    S("bms_version", "BMS-Version", DETAILS, category="diagnostic"),
    S("mppt_version", "MPPT-Version", DETAILS, category="diagnostic"),
    S("pd_version", "PD-Version", DETAILS, category="diagnostic"),
    S("wifi_signal", "WLAN-Signal", WIFI, unit="dBm", device_class="signal_strength", state_class="measurement", category="diagnostic"),
    S("firmware_version", "Firmware", FIRMWARE, category="diagnostic", icon="mdi:chip"),
    S("update_available", "Firmware-Update", FIRMWARE, platform="binary_sensor", device_class="update", category="diagnostic"),
)


def pack_entities(count: int) -> tuple[Entity, ...]:
    out: list[Entity] = []
    for i in range(1, count + 1):
        out.append(S(f"pack{i}_soc", f"Pack {i} Ladestand", ENERGY, unit="%", device_class="battery", state_class="measurement"))
        out.append(S(f"pack{i}_temperature", f"Pack {i} Temperatur", ENERGY, unit="°C", device_class="temperature", state_class="measurement"))
    return tuple(out)


def device_id(device_sn: str) -> str:
    """Stabile, nicht rueckrechenbare Kennung; die Seriennummer selbst bleibt privat."""
    return "noah_" + hashlib.sha256(device_sn.encode()).hexdigest()[:8]


def discovery(entity: Entity, *, dev_id: str, prefix: str, discovery_prefix: str,
              entity_prefix: str, model: str | None = None) -> tuple[str, str]:
    """Liefert (Topic, JSON-Payload) fuer eine Entitaet."""
    payload: dict[str, Any] = {
        "name": entity.name,
        "unique_id": f"{dev_id}_{entity.key}",
        "object_id": f"{entity_prefix}_{entity.key}",
        "state_topic": f"{prefix}/{entity.topic}",
        "value_template": entity.template,
        "availability_topic": f"{prefix}/availability",
        "device": {
            "identifiers": [dev_id],
            "name": "Growatt Noah 2000",
            "manufacturer": "Growatt",
            "model": model or "Noah 2000",
        },
    }
    if entity.platform == "binary_sensor":
        payload["payload_on"], payload["payload_off"] = "True", "False"
    if entity.unit:
        payload["unit_of_measurement"] = entity.unit
    if entity.device_class:
        payload["device_class"] = entity.device_class
    if entity.state_class:
        payload["state_class"] = entity.state_class
    if entity.category:
        payload["entity_category"] = entity.category
    if entity.icon:
        payload["icon"] = entity.icon
    if entity.precision is not None:
        payload["suggested_display_precision"] = entity.precision
    topic = f"{discovery_prefix}/{entity.platform}/{dev_id}/{entity.key}/config"
    return topic, json.dumps(payload, ensure_ascii=False)


def energy_state(s: EnergySnapshot) -> dict[str, Any]:
    state: dict[str, Any] = {
        "soc": s.soc, "pv_power": s.pv_power, "output_power": s.output_power,
        "battery_power": s.battery_power, "energy_today": s.energy_today,
        "energy_month": s.energy_month, "energy_year": s.energy_year,
        "energy_total": s.energy_total, "cycles": s.cycles, "health": s.health,
        "system_temperature": s.system_temperature, "status": s.status,
        "work_mode": s.work_mode, "charging_status": s.charging_status,
        "pv1_voltage": s.pv1_voltage, "pv1_current": s.pv1_current,
        "pv2_voltage": s.pv2_voltage, "pv2_current": s.pv2_current,
    }
    for p in s.packs:
        state[f"pack{p.index}_soc"] = p.soc
        state[f"pack{p.index}_temperature"] = p.temperature
    return state


def details_state(s: DetailsSnapshot) -> dict[str, Any]:
    return {
        "soc_upper_limit": s.soc_upper_limit, "soc_lower_limit": s.soc_lower_limit,
        "allow_grid_charging": s.allow_grid_charging, "bms_version": s.bms_version,
        "mppt_version": s.mppt_version, "pd_version": s.pd_version,
    }
