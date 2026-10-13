import dataclasses

import pytest

from noah_bridge import entities as ent
from test_models import load
from noah_bridge.models import EnergySnapshot


def snap(**kw):
    return dataclasses.replace(EnergySnapshot.from_response(load("noah_energy_v4")), **kw)


@pytest.mark.parametrize("raw,text", [(0, "Standby"), (1, "Laden"), (2, "Entladen")])
def test_charging_text_bits(raw, text):
    assert ent.energy_state(snap(charging_status=raw))["charging_status"] == text


def test_status_text():
    assert ent.energy_state(snap(status=1))["status"] == "Normal"
    assert ent.energy_state(snap(status=5))["status"] == "Heizen"
    assert ent.energy_state(snap(status=9))["status"] == "Unbekannt (9)"


def test_problem_flag():
    base = snap(status=1, fault_status=0, pd_warn_status=0, mppt_protect_status=0, packs=())
    assert ent.energy_state(base)["problem"] is False
    assert ent.energy_state(dataclasses.replace(base, status=4))["problem"] is True
    assert ent.energy_state(dataclasses.replace(base, pd_warn_status=1))["problem"] is True
    pack = dataclasses.replace(snap().packs[0], protect_status=4)
    assert ent.energy_state(dataclasses.replace(base, packs=(pack,)))["problem"] is True
