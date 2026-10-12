"""Verdrahtung: Client -> Parser -> MQTT. Ohne eigene Zeit- oder Netzlogik, daher gut testbar."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from . import entities as ent
from .config import Config
from .energy import EnergyCounters, derive
from .models import (
    DetailsSnapshot,
    EnergySnapshot,
    parse_firmware,
    parse_wifi,
)

log = logging.getLogger(__name__)


class Publisher(Protocol):
    def announce(self, topic: str, payload: str) -> None: ...
    def publish_state(self, suffix: str, state: dict[str, Any]) -> None: ...
    def set_available(self, online: bool) -> None: ...


class Bridge:
    def __init__(
        self, cfg: Config, client: Any, publisher: Publisher,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        counters: EnergyCounters | None = None,
    ) -> None:
        self.cfg = cfg
        self._now = now
        self.client = client
        self.pub = publisher
        self.dev_id = ent.device_id(cfg.device_sn)
        self._model: str | None = None
        self._pack_count = 0
        self.counters = counters or EnergyCounters(None, cfg.energy_interval * 2.5)
        self._soc_lower, self._soc_upper = 10.0, 100.0  # werden aus details_v4 ueberschrieben
        self.announce(ent.STATIC)

    def announce(self, entities) -> None:
        for e in entities:
            topic, payload = ent.discovery(
                e, dev_id=self.dev_id, prefix=self.cfg.mqtt_prefix,
                discovery_prefix=self.cfg.discovery_prefix,
                entity_prefix=self.cfg.entity_prefix, model=self._model,
            )
            self.pub.announce(topic, payload)

    def poll_energy(self) -> None:
        snap = EnergySnapshot.from_response(self.client.energy())
        if len(snap.packs) != self._pack_count:
            self._pack_count = len(snap.packs)
            self.announce(ent.pack_entities(self._pack_count))
        state = ent.energy_state(snap)
        self.counters.update(self._now().astimezone(), snap.pv_power, snap.battery_power)
        state.update(derive(
            counters=self.counters, soc=snap.soc, battery_w=snap.battery_power,
            pack_count=len(snap.packs), capacity_per_pack_kwh=self.cfg.capacity_per_pack_kwh,
            soc_lower=self._soc_lower, soc_upper=self._soc_upper,
            output_today_kwh=snap.energy_today,
        ))
        self.counters.save()
        state["last_update"] = self._now().isoformat(timespec="seconds")  # nur nach erfolgreichem Abruf
        self.pub.publish_state(ent.ENERGY, state)

    def poll_details(self) -> None:
        snap = DetailsSnapshot.from_response(self.client.details())
        if snap.soc_lower_limit is not None:
            self._soc_lower = snap.soc_lower_limit
        if snap.soc_upper_limit is not None:
            self._soc_upper = snap.soc_upper_limit
        if snap.model and snap.model != self._model:
            self._model = snap.model  # fuer das Geraet in HA; Discovery mit neuem Modell
            self.announce(ent.STATIC + ent.pack_entities(self._pack_count))
        self.pub.publish_state(ent.DETAILS, ent.details_state(snap))

    def poll_wifi(self) -> None:
        value = parse_wifi(self.client.wifi())
        self.pub.publish_state(ent.WIFI, {"wifi_signal": value})

    def poll_firmware(self) -> None:
        version, update = parse_firmware(self.client.firmware())
        self.pub.publish_state(ent.FIRMWARE, {"firmware_version": version, "update_available": update})
