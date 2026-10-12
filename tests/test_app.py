import json
from pathlib import Path

import pytest

from noah_bridge.app import Bridge
from noah_bridge.config import load_config
from noah_bridge.models import ParseError

SAMPLES = Path(__file__).parent.parent / "samples"


def load(name):
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


class FakeClient:
    def energy(self): return load("noah_energy_v4")
    def details(self): return load("noah_details_v4")
    def wifi(self): return load("noah_wifi_strength")
    def firmware(self): return load("noah_firmware_info")


class FakePub:
    def __init__(self):
        self.announced, self.states, self.available = {}, {}, None

    def announce(self, topic, payload): self.announced[topic] = json.loads(payload)
    def publish_state(self, suffix, state): self.states[suffix] = state
    def set_available(self, online): self.available = online


@pytest.fixture
def bridge(tmp_path):
    cfg = load_config({"GROWATT_TOKEN": "tok", "GROWATT_DEVICE_SN": "SN123"}, tmp_path / "x.json")
    pub = FakePub()
    return Bridge(cfg, FakeClient(), pub), pub


def test_static_entities_announced_without_serial(bridge):
    _, pub = bridge
    assert len(pub.announced) >= 20
    blob = json.dumps(pub.announced)
    assert "SN123" not in blob and "tok" not in blob


def test_energy_publishes_state_and_pack_entities(bridge):
    b, pub = bridge
    b.poll_energy()
    state = pub.states["state/energy"]
    assert {"soc", "pv_power", "output_power", "battery_power", "pack1_soc", "pack2_temperature"} <= set(state)
    packs = [t for t in pub.announced if "pack" in t]
    assert len(packs) == 4  # 2 Packs x (SOC, Temperatur)


def test_every_entity_key_is_published_by_its_topic(bridge):
    b, pub = bridge
    for poll in (b.poll_energy, b.poll_details, b.poll_wifi, b.poll_firmware):
        poll()
    for cfg in pub.announced.values():
        suffix = cfg["state_topic"].split("/", 1)[1]
        key = cfg["value_template"].split("value_json.")[1].split(" ")[0]
        assert key in pub.states[suffix], f"{key} fehlt in {suffix}"


def test_discovery_has_ha_required_fields(bridge):
    _, pub = bridge
    for cfg in pub.announced.values():
        assert cfg["unique_id"] and cfg["state_topic"] and cfg["availability_topic"]
        assert cfg["device"]["identifiers"]
    soc = next(c for c in pub.announced.values() if c["unique_id"].endswith("_energy_total"))
    assert (soc["device_class"], soc["state_class"]) == ("energy", "total_increasing")


def test_bad_response_raises_so_poller_backs_off(bridge):
    b, _ = bridge
    b.client.energy = lambda: {"error_code": 10012, "error_msg": "limit", "data": None}
    with pytest.raises(ParseError):
        b.poll_energy()


def test_last_update_timestamp_only_after_successful_poll(tmp_path):
    from datetime import datetime, timezone

    cfg = load_config({"GROWATT_TOKEN": "tok", "GROWATT_DEVICE_SN": "SN123"}, tmp_path / "x.json")
    pub = FakePub()
    b = Bridge(cfg, FakeClient(), pub, now=lambda: datetime(2026, 10, 12, 8, 34, 32, tzinfo=timezone.utc))
    assert "state/energy" not in pub.states
    b.poll_energy()
    assert pub.states["state/energy"]["last_update"] == "2026-10-12T08:34:32+00:00"
    entity = next(c for c in pub.announced.values() if c["unique_id"].endswith("_last_update"))
    assert entity["device_class"] == "timestamp"

    b.client.energy = lambda: {"error_code": 1, "data": None}
    with pytest.raises(ParseError):
        b.poll_energy()
    assert pub.states["state/energy"]["last_update"] == "2026-10-12T08:34:32+00:00"  # unveraendert


def test_counters_accumulate_and_are_published(tmp_path):
    from datetime import datetime, timedelta, timezone

    from noah_bridge.energy import EnergyCounters

    cfg = load_config({"GROWATT_TOKEN": "tok", "GROWATT_DEVICE_SN": "SN123"}, tmp_path / "x.json")
    pub = FakePub()
    clock = {"t": datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)}
    path = tmp_path / "state.json"
    b = Bridge(cfg, FakeClient(), pub, now=lambda: clock["t"], counters=EnergyCounters(path, 750))
    raw = load("noah_energy_v4")["data"]["devices"][0]
    raw["ppv"], raw["total_battery_pack_charging_power"] = 600.0, 500.0
    b.client.energy = lambda: {"error_code": 0, "data": {"devices": [raw]}}
    b.poll_energy()
    clock["t"] += timedelta(minutes=5)
    b.poll_energy()
    state = pub.states["state/energy"]
    assert state["pv_energy_total"] == pytest.approx(0.05, abs=0.001)         # 600 W x 5 min
    assert state["battery_charged_total"] == pytest.approx(0.0417, abs=0.001)  # 500 W x 5 min
    assert state["battery_discharged_total"] == 0
    assert state["stored_energy"] is not None
    assert path.is_file()
