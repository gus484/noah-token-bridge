import json
from pathlib import Path

import pytest

from noah_bridge.models import (
    DetailsSnapshot,
    EnergySnapshot,
    ParseError,
    parse_firmware,
    parse_wifi,
)

SAMPLES = Path(__file__).parent.parent / "samples"


def load(name):
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def raw_device(name):
    return load(name)["data"]["devices"][0]


def test_energy_snapshot_matches_raw_fields():
    raw = raw_device("noah_energy_v4")
    s = EnergySnapshot.from_response(load("noah_energy_v4"))
    assert s.soc == raw["total_battery_pack_soc"]
    assert s.output_power == raw["pac"]
    assert s.pv_power == raw["ppv"]
    assert s.battery_power == raw["total_battery_pack_charging_power"]
    assert s.energy_today == raw["eac_today"]
    assert s.energy_total == raw["eac_total"]
    assert s.cycles == raw["battery_cycles"]
    assert s.status == raw["status"]
    assert s.charging_status == raw["total_battery_pack_charging_status"]
    assert s.pv2_voltage == raw["pv2_voltage"]


def test_energy_packs_follow_quantity():
    raw = raw_device("noah_energy_v4")
    s = EnergySnapshot.from_response(load("noah_energy_v4"))
    assert len(s.packs) == raw["battery_package_quantity"] == 2
    assert [(p.index, p.soc, p.temperature) for p in s.packs] == [
        (i, raw[f"battery{i}_soc"], raw[f"battery{i}_temp"]) for i in (1, 2)
    ]


def test_details_snapshot():
    s = DetailsSnapshot.from_response(load("noah_details_v4"))
    assert s.model == "NEO 2000M-X2"
    assert (s.soc_lower_limit, s.soc_upper_limit) == (10, 100)
    assert s.allow_grid_charging is False
    assert s.lost is False


def test_wifi_and_firmware():
    assert parse_wifi(load("noah_wifi_strength")) == -77
    assert parse_firmware(load("noah_firmware_info")) == ("19.20.14.4026", False)


def test_null_data_is_parse_error():
    with pytest.raises(ParseError):
        EnergySnapshot.from_response(load("noah_power_realtime"))


def test_error_code_is_parse_error():
    with pytest.raises(ParseError):
        EnergySnapshot.from_response({"error_code": 10012, "error_msg": "RATE_LIMIT", "data": None})


def test_energy_diagnostic_fields_match_raw():
    raw = raw_device("noah_energy_v4")
    s = EnergySnapshot.from_response(load("noah_energy_v4"))
    assert s.heating_status == raw["heating_status"]
    assert s.fault_status == raw["fault_status"]
    assert s.pd_warn_status == raw["pd_warn_status"]
    assert s.mppt_protect_status == raw["mppt_protect_status"]
    assert s.on_off_grid == raw["on_off_grid"]
    assert [(p.warn_status, p.protect_status) for p in s.packs] == [
        (raw[f"battery{i}_warn_status"], raw[f"battery{i}_protect_status"]) for i in (1, 2)
    ]


def test_details_default_power():
    raw = raw_device("noah_details_v4")
    assert DetailsSnapshot.from_response(load("noah_details_v4")).default_power == raw["default_power"]
