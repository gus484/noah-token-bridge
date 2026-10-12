"""Energiezaehler (PV, Akku laden/entladen) und abgeleitete Werte.

Die API liefert nur Momentanleistungen alle ~5 Minuten. Die Zaehler integrieren diese Werte
nach der Trapezregel. Ueber Luecken (Rechner im Ruhezustand, Netzausfall, Neustart) wird nicht
integriert: Lieber fehlt Energie, als dass der letzte Wert stundenlang fortgeschrieben wird.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Unterhalb dieser Leistung gelten Laden/Entladen als Stillstand (Messrauschen)
MIN_FLOW_W = 20.0
# Auswertungen mit zu wenig Basis liefern keinen Wert
MIN_EFFICIENCY_BASE_KWH = 0.3


@dataclass
class Totals:
    pv: float = 0.0
    charged: float = 0.0
    discharged: float = 0.0


class EnergyCounters:
    def __init__(self, path: Path | None, max_gap_s: float) -> None:
        self.path = path
        self.max_gap_s = max_gap_s
        self.today = Totals()
        self.total = Totals()
        self._day: date | None = None
        self._last: tuple[datetime, float, float] | None = None  # (Zeit, PV W, Akku W)

    # -- Speicherung -------------------------------------------------------
    def load(self) -> None:
        if not self.path or not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.today = Totals(**raw["today"])
            self.total = Totals(**raw["total"])
            self._day = date.fromisoformat(raw["day"]) if raw.get("day") else None
            last = raw.get("last")
            self._last = (datetime.fromisoformat(last["t"]), last["pv"], last["batt"]) if last else None
            log.info("Zaehlerstaende geladen (%s, PV gesamt %.1f kWh)", self.path, self.total.pv)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Zaehlerdatei %s unbrauchbar, starte bei 0: %s", self.path, exc)
            self.today, self.total, self._day, self._last = Totals(), Totals(), None, None

    def save(self) -> None:
        if not self.path:
            return
        payload: dict[str, Any] = {
            "day": self._day.isoformat() if self._day else None,
            "today": asdict(self.today),
            "total": asdict(self.total),
            "last": None if self._last is None else
            {"t": self._last[0].isoformat(), "pv": self._last[1], "batt": self._last[2]},
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("Zaehlerdatei %s nicht schreibbar: %s", self.path, exc)

    # -- Integration -------------------------------------------------------
    def update(self, t: datetime, pv_w: float | None, battery_w: float | None) -> None:
        """`t` muss die lokale Zeit sein (bestimmt den Tageswechsel)."""
        if self._day != t.date():
            self.today = Totals()
            self._day = t.date()
        if pv_w is None or battery_w is None:
            self._last = None  # unvollstaendige Messung: nichts fortschreiben
            return
        pv_w = max(pv_w, 0.0)
        if self._last is not None:
            prev_t, prev_pv, prev_batt = self._last
            dt = (t - prev_t).total_seconds()
            if 0 < dt <= self.max_gap_s:
                hours = dt / 3600.0
                self._add("pv", (prev_pv + pv_w) / 2 * hours / 1000)
                self._add("charged", (max(prev_batt, 0) + max(battery_w, 0)) / 2 * hours / 1000)
                self._add("discharged", (max(-prev_batt, 0) + max(-battery_w, 0)) / 2 * hours / 1000)
            elif dt > self.max_gap_s:
                log.info("Luecke von %.0f s, keine Integration ueber die Luecke", dt)
        self._last = (t, pv_w, battery_w)

    def _add(self, field: str, kwh: float) -> None:
        setattr(self.today, field, getattr(self.today, field) + kwh)
        setattr(self.total, field, getattr(self.total, field) + kwh)


def derive(
    *,
    counters: EnergyCounters,
    soc: float | None,
    battery_w: float | None,
    pack_count: int,
    capacity_per_pack_kwh: float,
    soc_lower: float,
    soc_upper: float,
    output_today_kwh: float | None,
) -> dict[str, float | None]:
    """Zustandswerte fuer Home Assistant (Schluessel = Entity-keys)."""
    today, total = counters.today, counters.total
    capacity = capacity_per_pack_kwh * pack_count if pack_count else None

    stored = soc / 100 * capacity if soc is not None and capacity else None
    to_empty = to_full = None
    if soc is not None and capacity and battery_w is not None:
        if battery_w < -MIN_FLOW_W:
            usable = max(soc - soc_lower, 0) / 100 * capacity
            to_empty = usable * 1000 / -battery_w
        elif battery_w > MIN_FLOW_W:
            missing = max(soc_upper - soc, 0) / 100 * capacity
            to_full = missing * 1000 / battery_w

    # Energie an der Wandlerstufe: PV direkt + Akku-Entladung = PV - Ladung + Entladung
    base = today.pv - today.charged + today.discharged
    efficiency = None
    if output_today_kwh is not None and base >= MIN_EFFICIENCY_BASE_KWH:
        efficiency = output_today_kwh / base * 100

    def r(v: float | None, n: int = 3) -> float | None:
        return None if v is None else round(v, n)

    return {
        "pv_energy_today": r(today.pv), "pv_energy_total": r(total.pv),
        "battery_charged_today": r(today.charged), "battery_charged_total": r(total.charged),
        "battery_discharged_today": r(today.discharged), "battery_discharged_total": r(total.discharged),
        "pv_direct_today": r(max(today.pv - today.charged, 0.0)),
        "cycles_today": r(today.discharged / capacity, 2) if capacity else None,
        "stored_energy": r(stored),
        "time_to_empty": r(to_empty, 2),
        "time_to_full": r(to_full, 2),
        "system_efficiency_today": r(efficiency, 1),
    }
