"""Typisierte Sicht auf die Growatt-Antworten (Felder laut samples/*.json)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

MAX_PACKS = 4


class ParseError(ValueError):
    pass


def _check(response: Mapping[str, Any]) -> None:
    if not isinstance(response, Mapping):
        raise ParseError("Antwort ist kein Objekt")
    if response.get("error_code") not in (0, None):
        raise ParseError(f"error_code={response.get('error_code')}: {response.get('error_msg')}")


def first_device(response: Mapping[str, Any]) -> Mapping[str, Any]:
    """Wirft ParseError bei Fehlercode oder wenn kein Geraet enthalten ist."""
    _check(response)
    data = response.get("data")
    devices = data.get("devices") if isinstance(data, Mapping) else None
    if not devices:
        raise ParseError("Antwort enthaelt kein Geraet")
    return devices[0]


def _num(d: Mapping[str, Any], key: str) -> float | None:
    v = d.get(key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _int(d: Mapping[str, Any], key: str) -> int | None:
    v = d.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


@dataclass(frozen=True)
class Pack:
    index: int
    soc: float | None
    temperature: float | None


@dataclass(frozen=True)
class EnergySnapshot:
    """Live-Werte aus noah.energy_v4()."""

    soc: float | None
    pv_power: float | None
    output_power: float | None
    battery_power: float | None  # positiv = Laden, negativ = Entladen; Laden erst ab ca. 55-60 W PV
    energy_today: float | None
    energy_month: float | None
    energy_year: float | None
    energy_total: float | None
    cycles: float | None
    health: float | None
    system_temperature: float | None
    status: int | None
    work_mode: int | None
    # Rohwerte zur Diagnose der Akkuleistung (Vorzeichen/Ladeerkennung noch ungeklaert)
    charging_status: int | None = None
    pv1_voltage: float | None = None
    pv1_current: float | None = None
    pv2_voltage: float | None = None
    pv2_current: float | None = None
    packs: tuple[Pack, ...] = field(default_factory=tuple)

    @classmethod
    def from_response(cls, response: Mapping[str, Any]) -> "EnergySnapshot":
        d = first_device(response)
        count = _int(d, "battery_package_quantity") or 0
        packs = tuple(
            Pack(i, _num(d, f"battery{i}_soc"), _num(d, f"battery{i}_temp"))
            for i in range(1, min(count, MAX_PACKS) + 1)
        )
        return cls(
            soc=_num(d, "total_battery_pack_soc"),
            pv_power=_num(d, "ppv"),
            output_power=_num(d, "pac"),
            battery_power=_num(d, "total_battery_pack_charging_power"),
            energy_today=_num(d, "eac_today"),
            energy_month=_num(d, "eac_month"),
            energy_year=_num(d, "eac_year"),
            energy_total=_num(d, "eac_total"),
            cycles=_num(d, "battery_cycles"),
            health=_num(d, "battery_soh"),
            system_temperature=_num(d, "system_temp"),
            status=_int(d, "status"),
            work_mode=_int(d, "work_mode"),
            charging_status=_int(d, "total_battery_pack_charging_status"),
            pv1_voltage=_num(d, "pv1_voltage"),
            pv1_current=_num(d, "pv1_current"),
            pv2_voltage=_num(d, "pv2_voltage"),
            pv2_current=_num(d, "pv2_current"),
            packs=packs,
        )


@dataclass(frozen=True)
class DetailsSnapshot:
    """Einstellungen und Versionen aus noah.details_v4()."""

    model: str | None
    soc_upper_limit: float | None
    soc_lower_limit: float | None
    allow_grid_charging: bool | None
    lost: bool | None
    bms_version: str | None
    mppt_version: str | None
    pd_version: str | None

    @classmethod
    def from_response(cls, response: Mapping[str, Any]) -> "DetailsSnapshot":
        d = first_device(response)
        grid = _int(d, "allow_grid_charging")
        lost = d.get("lost")
        return cls(
            model=d.get("model_name") or d.get("model"),
            soc_upper_limit=_num(d, "charging_soc_high_limit"),
            soc_lower_limit=_num(d, "charging_soc_low_limit"),
            allow_grid_charging=None if grid is None else bool(grid),
            lost=lost if isinstance(lost, bool) else None,
            bms_version=d.get("bms_version"),
            mppt_version=d.get("mppt_version"),
            pd_version=d.get("pd_version"),
        )


def parse_wifi(response: Mapping[str, Any]) -> float | None:
    _check(response)
    v = response.get("data")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def parse_firmware(response: Mapping[str, Any]) -> tuple[str | None, bool | None]:
    _check(response)
    d = response.get("data") or {}
    update = d.get("update_available")
    return d.get("current_version"), update if isinstance(update, bool) else None
