"""MQTT-Anbindung (paho-mqtt 2.x): Zustandsthemen, Verfuegbarkeit, Discovery."""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

import paho.mqtt.client as mqtt

from .config import Config

log = logging.getLogger(__name__)


class MqttPublisher:
    def __init__(self, cfg: Config, client_id: str) -> None:
        self.prefix = cfg.mqtt_prefix
        self.availability_topic = f"{cfg.mqtt_prefix}/availability"
        self._ha_status_topic = f"{cfg.discovery_prefix}/status"
        self._discovery: dict[str, str] = {}
        self._lock = threading.Lock()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if cfg.mqtt_tls:
            self._client.tls_set()
        if cfg.mqtt_user:
            self._client.username_pw_set(cfg.mqtt_user, cfg.mqtt_password)
        self._client.will_set(self.availability_topic, "offline", qos=1, retain=True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=120)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._host, self._port = cfg.mqtt_host, cfg.mqtt_port

    def start(self) -> None:
        self._client.connect_async(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        self.set_available(False)
        self._client.disconnect()
        self._client.loop_stop()

    # -- Callbacks ---------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            log.error("MQTT-Verbindung abgelehnt: %s", reason_code)
            return
        log.info("MQTT verbunden mit %s:%s", self._host, self._port)
        client.subscribe(self._ha_status_topic)
        self._republish_discovery()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        log.warning("MQTT getrennt (%s), paho verbindet automatisch neu", reason_code)

    def _on_message(self, client, userdata, msg) -> None:
        if msg.topic == self._ha_status_topic and msg.payload == b"online":
            log.info("Home Assistant gestartet, sende Discovery erneut")
            self._republish_discovery()

    # -- Veroeffentlichen --------------------------------------------------
    def _republish_discovery(self) -> None:
        with self._lock:
            items = list(self._discovery.items())
        for topic, payload in items:
            self._client.publish(topic, payload, qos=1, retain=True)

    def announce(self, topic: str, payload: str) -> None:
        with self._lock:
            if self._discovery.get(topic) == payload:
                return
            self._discovery[topic] = payload
        self._client.publish(topic, payload, qos=1, retain=True)

    def publish_state(self, suffix: str, state: dict[str, Any]) -> None:
        self._client.publish(f"{self.prefix}/{suffix}", json.dumps(state), qos=1, retain=True)

    def set_available(self, online: bool) -> None:
        self._client.publish(self.availability_topic, "online" if online else "offline",
                             qos=1, retain=True)
