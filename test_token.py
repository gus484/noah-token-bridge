#!/usr/bin/env python3
r"""Schritt 1 aus PLAN.md: Token von Hand testen und Beispielantworten speichern.

Nutzung (PowerShell):
    python -m venv venv; .\venv\Scripts\Activate.ps1
    pip install growatt-public-api
    $env:GROWATT_TOKEN = "DEIN_TOKEN"
    python test_token.py

Optional: $env:GROWATT_SN, um eine bestimmte Seriennummer zu testen.

Das Skript fragt nur wenige Endpunkte genau einmal ab (kein Retry) und
schreibt die Antworten nach samples/. Token und Seriennummern werden
vor dem Speichern unkenntlich gemacht.
"""
import datetime
import enum
import json
import os
import re
import sys
from pathlib import Path

from growatt_public_api import GrowattApi

SAMPLES = Path(__file__).parent / "samples"
TOKEN = os.environ.get("GROWATT_TOKEN", "").strip()
SECRETS: set[str] = set()


def to_plain(obj):
    """Wandelt Antwortobjekte der Bibliothek in JSON-taugliche Strukturen."""
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    for attr in ("model_dump", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return to_plain(fn())
            except Exception:
                pass
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if hasattr(obj, "__dict__"):
        return to_plain(vars(obj))
    return repr(obj)


def redact(text: str) -> str:
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "REDACTED")
    return text


PRIVATE_KEYS = re.compile(
    r"serial|_sn$|^sn$|^name$|^alias$|city|latitude|longitude|user_id|plant_id|port_name|address",
    re.I,
)


def scrub(data):
    """Schwaerzt Schluessel mit Seriennummern, Namen und Ortsangaben."""
    if isinstance(data, dict):
        return {
            k: ("REDACTED" if PRIVATE_KEYS.search(k) and v not in (None, "") else scrub(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [scrub(v) for v in data]
    return data


def save(name: str, data) -> None:
    SAMPLES.mkdir(exist_ok=True)
    data = scrub(to_plain(data))
    text = redact(json.dumps(to_plain(data), indent=2, ensure_ascii=False, default=str))
    (SAMPLES / f"{name}.json").write_text(text, encoding="utf-8")


def step(name: str, fn, *args, **kwargs):
    """Ruft genau einmal auf; Fehler werden gemeldet, brechen aber nichts ab."""
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:
        print(f"  [FEHLER] {name}: {type(exc).__name__}: {redact(str(exc))}")
        return None
    plain = to_plain(result)
    save(name, plain)
    print(f"  [OK]     {name} -> samples/{name}.json")
    return plain


def find_first(data, key_pattern: str):
    """Sucht rekursiv den ersten Wert, dessen Schluessel zum Muster passt."""
    rx = re.compile(key_pattern, re.I)
    if isinstance(data, dict):
        for k, v in data.items():
            if rx.fullmatch(k) and v not in (None, ""):
                return v
        for v in data.values():
            hit = find_first(v, key_pattern)
            if hit is not None:
                return hit
    elif isinstance(data, list):
        for v in data:
            hit = find_first(v, key_pattern)
            if hit is not None:
                return hit
    return None


def main() -> int:
    if not TOKEN:
        print("GROWATT_TOKEN ist nicht gesetzt.")
        return 1
    SECRETS.add(TOKEN)
    api = GrowattApi(token=TOKEN)

    print("1. Anlagen")
    plants = step("plant_list", api.plant.list)
    if plants is None:
        print("\nABBRUCH: Anlagenliste nicht abrufbar (Token falsch oder Rate-Limit).")
        return 2
    plant_id = find_first(plants, r"plant_?id|id")
    if plant_id is None:
        print("\nABBRUCH: Keine Anlage gefunden. Siehe samples/plant_list.json.")
        return 2
    print(f"  Plant-ID: {plant_id}")

    print("2. Geraete")
    devices = step("plant_devices", api.plant.list_devices, plant_id=plant_id)
    sn = os.environ.get("GROWATT_SN") or (
        find_first(devices, r"device_?sn|sn") if devices else None
    )
    if not sn:
        print("  Geraeteliste der Anlage leer, versuche alternative Listen ...")
        alt = step("device_list", api.device.list)
        step("plant_list_by_user", api.plant.list_by_user)
        sn = find_first(alt, r"device_?sn|sn") if alt else None
    if not sn:
        print("\nABBRUCH: Kein Geraet gefunden. Der Noah taucht nicht auf.")
        print("Tipp: Seriennummer aus der ShinePhone-App holen und direkt testen:")
        print('  $env:GROWATT_SN = "DEINE_SN"; python test_token.py')
        return 3
    SECRETS.add(str(sn))
    # Datei neu schreiben, jetzt mit bekannter Seriennummer geschwaerzt
    save("plant_devices", devices)
    print(f"  Seriennummer: {str(sn)[:2]}***{str(sn)[-2:]}")

    print("3. Noah-Abfragen")
    step("device_type", api.device.get_device_type, device_sn=sn)
    details = step("noah_details_v4", api.noah.details_v4, device_sn=sn)
    realtime = step("noah_power_realtime", api.noah.power_realtime, device_sn=sn)

    # Optionale Abfragen aus Schritt 2 des Plans (je einmal)
    for name in ("energy_v4", "wifi_strength", "device_info", "firmware_info"):
        fn = getattr(api.noah, name, None)
        if fn is None:
            print(f"  [SKIP]   noah.{name} existiert nicht in dieser Version")
            continue
        step(f"noah_{name}", fn, device_sn=sn)

    print()
    if details and realtime:
        print("ERGEBNIS: details_v4() und power_realtime() liefern Daten. Weiter mit Etappe 1.")
        print("Pruefe samples/ noch einmal auf Reste von Token, SN, Adresse oder Namen.")
        return 0
    print("ERGEBNIS: Noah-Abfragen unvollstaendig - Abbruchkriterium aus PLAN.md pruefen.")
    return 4


if __name__ == "__main__":
    sys.exit(main())
