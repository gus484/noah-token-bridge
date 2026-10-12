import io
import json

import pytest

from noah_bridge.config import ConfigError, load_config
from noah_bridge.supervisor import fetch_mqtt_service, resolve_mqtt


def cfg(tmp_path, **extra):
    env = {"GROWATT_TOKEN": "t", "GROWATT_DEVICE_SN": "s", **extra}
    return load_config(env, tmp_path / "x.json")


def test_explicit_host_wins_and_skips_supervisor(tmp_path):
    c = cfg(tmp_path, MQTT_HOST="broker")
    assert resolve_mqtt(c, fetch=lambda: pytest.fail("darf nicht aufgerufen werden")).mqtt_host == "broker"


def test_no_supervisor_falls_back_to_localhost(tmp_path):
    assert resolve_mqtt(cfg(tmp_path), fetch=lambda: None).mqtt_host == "localhost"


def test_supervisor_values_are_used(tmp_path):
    svc = {"host": "core-mosquitto", "port": 8883, "username": "u", "password": "p", "ssl": True}
    c = resolve_mqtt(cfg(tmp_path), fetch=lambda: svc)
    assert (c.mqtt_host, c.mqtt_port, c.mqtt_user, c.mqtt_password, c.mqtt_tls) == (
        "core-mosquitto", 8883, "u", "p", 1)


def test_fetch_without_token_returns_none():
    assert fetch_mqtt_service(env={}) is None


def test_fetch_sends_bearer_and_parses():
    seen = {}

    def fake_open(req, timeout):
        seen["auth"] = req.get_header("Authorization")
        return io.StringIO(json.dumps({"data": {"host": "h"}}))

    assert fetch_mqtt_service(env={"SUPERVISOR_TOKEN": "abc"}, urlopen=fake_open) == {"host": "h"}
    assert seen["auth"] == "Bearer abc"


def test_fetch_error_is_config_error():
    def broken(req, timeout):
        raise OSError("down")

    with pytest.raises(ConfigError):
        fetch_mqtt_service(env={"SUPERVISOR_TOKEN": "abc"}, urlopen=broken)
