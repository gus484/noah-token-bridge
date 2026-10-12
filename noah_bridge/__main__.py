"""Start: python -m noah_bridge"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import uuid
from pathlib import Path

from .app import Bridge
from .client import NoahClient, build_api
from .config import ConfigError, load_config
from .energy import EnergyCounters
from .logging_setup import setup_logging
from .mqtt import MqttPublisher
from .poller import Poller, Task
from .ratelimit import HourlyLimiter
from .supervisor import resolve_mqtt

log = logging.getLogger("noah_bridge")


def main() -> int:
    try:
        cfg = resolve_mqtt(load_config())
    except ConfigError as exc:
        print(f"Konfigurationsfehler: {exc}", file=sys.stderr)
        return 2
    setup_logging(cfg.log_level, [cfg.token, cfg.device_sn, cfg.mqtt_password])

    limiter = HourlyLimiter(cfg.max_requests_per_hour)
    client = NoahClient(build_api(cfg.token, limiter), cfg.device_sn)
    publisher = MqttPublisher(cfg, client_id=f"noah-bridge-{uuid.uuid4().hex[:6]}")
    state_file = cfg.state_file or ("/data/noah_state.json" if os.path.isdir("/data") else "noah_state.json")
    counters = EnergyCounters(Path(state_file), max_gap_s=cfg.energy_interval * 2.5)
    counters.load()
    bridge = Bridge(cfg, client, publisher, counters=counters)

    tasks = [
        Task("energy", cfg.energy_interval, bridge.poll_energy, primary=True),
        Task("details", cfg.details_interval, bridge.poll_details),
        Task("wifi", cfg.slow_interval, bridge.poll_wifi),
        Task("firmware", cfg.slow_interval, bridge.poll_firmware),
    ]
    poller = Poller(tasks, limiter, cfg.backoff_start, cfg.backoff_max, publisher.set_available)

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    log.info("Start: energy alle %d s, details alle %d s, Limit %d Requests/h",
             cfg.energy_interval, cfg.details_interval, cfg.max_requests_per_hour)
    publisher.start()
    try:
        poller.run_forever(stop)
    finally:
        publisher.stop()
        log.info("Beendet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
