import json

import pytest

from noah_bridge.config import ConfigError, load_config


def test_env_values(tmp_path):
    env = {"GROWATT_TOKEN": "t", "GROWATT_DEVICE_SN": "s", "MQTT_PORT": "1884"}
    cfg = load_config(env, tmp_path / "x.json")
    assert (cfg.token, cfg.device_sn, cfg.mqtt_port) == ("t", "s", 1884)
    assert cfg.energy_interval == 300


def test_options_json_and_env_override(tmp_path):
    p = tmp_path / "options.json"
    p.write_text(json.dumps({"token": "a", "device_sn": "s", "energy_interval": 600}))
    cfg = load_config({"GROWATT_TOKEN": "b"}, p)
    assert cfg.token == "b"
    assert cfg.energy_interval == 600


def test_missing_token(tmp_path):
    with pytest.raises(ConfigError):
        load_config({"GROWATT_DEVICE_SN": "s"}, tmp_path / "x.json")


def test_interval_too_small(tmp_path):
    env = {"GROWATT_TOKEN": "t", "GROWATT_DEVICE_SN": "s", "GROWATT_ENERGY_INTERVAL": "5"}
    with pytest.raises(ConfigError):
        load_config(env, tmp_path / "x.json")


def test_bad_number(tmp_path):
    env = {"GROWATT_TOKEN": "t", "GROWATT_DEVICE_SN": "s", "MQTT_PORT": "abc"}
    with pytest.raises(ConfigError):
        load_config(env, tmp_path / "x.json")


def test_repr_hides_secrets(tmp_path):
    env = {"GROWATT_TOKEN": "geheim", "GROWATT_DEVICE_SN": "snsn", "MQTT_PASSWORD": "pw"}
    text = repr(load_config(env, tmp_path / "x.json"))
    assert "geheim" not in text and "snsn" not in text and "pw'" not in text
