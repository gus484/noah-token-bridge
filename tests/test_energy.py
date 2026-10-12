from datetime import datetime, timedelta

import pytest

from noah_bridge.energy import EnergyCounters, derive

T0 = datetime(2026, 10, 12, 10, 0, 0)
GAP = 750  # 2,5 x 300 s


def counters(path=None):
    return EnergyCounters(path, GAP)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def test_first_sample_integrates_nothing():
    c = counters()
    c.update(T0, 500, 0)
    assert c.total.pv == 0


def test_trapezoid_pv_and_battery_split():
    c = counters()
    c.update(at(0), 0, 0)
    c.update(at(5), 600, 600)       # Laden: Mittel 300 W ueber 5 min
    c.update(at(10), 600, -600)     # Uebergang +600 -> -600: Laden Mittel 300, Entladen Mittel 300
    h = 5 / 60
    assert c.total.pv == pytest.approx((300 + 600) / 1000 * h)
    assert c.total.charged == pytest.approx((300 + 300) / 1000 * h)
    assert c.total.discharged == pytest.approx(300 / 1000 * h)
    assert c.today.pv == c.total.pv


def test_gap_is_not_integrated():
    c = counters()
    c.update(at(0), 1000, 0)
    c.update(at(300), 1000, 0)  # 5 Stunden spaeter, z. B. Ruhezustand
    assert c.total.pv == 0
    c.update(at(305), 1000, 0)  # danach laeuft die Integration wieder
    assert c.total.pv == pytest.approx(1.0 * 5 / 60)


def test_missing_values_reset_the_previous_sample():
    c = counters()
    c.update(at(0), 1000, 0)
    c.update(at(5), None, None)
    c.update(at(10), 1000, 0)
    assert c.total.pv == 0


def test_negative_pv_is_clamped():
    c = counters()
    c.update(at(0), -50, 0)
    c.update(at(5), -50, 0)
    assert c.total.pv == 0


def test_day_change_resets_today_but_not_total():
    c = counters()
    c.update(datetime(2026, 10, 12, 23, 55), 1000, 0)
    c.update(datetime(2026, 10, 13, 0, 0), 1000, 0)
    assert c.today.pv == pytest.approx(1.0 * 5 / 60)  # Intervall zaehlt zum neuen Tag
    c.update(datetime(2026, 10, 13, 0, 5), 1000, 0)
    assert c.total.pv == pytest.approx(2 * 1.0 * 5 / 60)
    c.update(datetime(2026, 10, 14, 0, 5), 0, 0)
    assert c.today.pv == 0 and c.total.pv > 0


def test_state_survives_restart(tmp_path):
    p = tmp_path / "state.json"
    a = counters(p)
    a.update(at(0), 1000, 0)
    a.update(at(5), 1000, 0)
    a.save()
    b = counters(p)
    b.load()
    assert b.total.pv == pytest.approx(a.total.pv)
    b.update(at(10), 1000, 0)  # kurze Pause ueber den Neustart: Integration geht weiter
    assert b.total.pv == pytest.approx(2 * 1.0 * 5 / 60)


def test_corrupt_file_starts_fresh(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{kaputt", encoding="utf-8")
    c = counters(p)
    c.load()
    assert c.total.pv == 0


def test_unwritable_path_does_not_raise(tmp_path):
    c = counters(tmp_path / "gibt-es-nicht" / "state.json")
    c.update(at(0), 1, 1)
    c.save()  # darf nicht werfen


def args(**kw):
    base = dict(counters=counters(), soc=50.0, battery_w=0.0, pack_count=2,
                capacity_per_pack_kwh=2.048, soc_lower=10.0, soc_upper=100.0, output_today_kwh=None)
    base.update(kw)
    return base


def test_stored_energy_and_runtime():
    d = derive(**args(soc=50.0, battery_w=-400.0))
    assert d["stored_energy"] == pytest.approx(2.048)            # 50 % von 4,096 kWh
    assert d["time_to_empty"] == pytest.approx(0.4 * 4.096 * 1000 / 400, abs=0.01)  # nutzbar ab 10 %
    assert d["time_to_full"] is None


def test_time_to_full_when_charging():
    d = derive(**args(soc=50.0, battery_w=500.0))
    assert d["time_to_full"] == pytest.approx(0.5 * 4.096 * 1000 / 500, abs=0.01)
    assert d["time_to_empty"] is None


def test_idle_battery_has_no_runtime():
    d = derive(**args(battery_w=5.0))
    assert d["time_to_empty"] is None and d["time_to_full"] is None


def test_no_packs_gives_no_capacity_values():
    d = derive(**args(pack_count=0, battery_w=-300.0))
    assert d["stored_energy"] is None and d["time_to_empty"] is None and d["cycles_today"] is None


def test_efficiency_and_direct_use():
    c = counters()
    c.today.pv, c.today.charged, c.today.discharged = 1.0, 0.6, 0.5
    d = derive(**args(counters=c, output_today_kwh=0.85))
    assert d["system_efficiency_today"] == pytest.approx(0.85 / 0.9 * 100, abs=0.1)
    assert d["pv_direct_today"] == pytest.approx(0.4)
    assert d["cycles_today"] == pytest.approx(0.5 / 4.096, abs=0.01)


def test_efficiency_needs_enough_energy():
    c = counters()
    c.today.pv = 0.1
    assert derive(**args(counters=c, output_today_kwh=0.09))["system_efficiency_today"] is None
