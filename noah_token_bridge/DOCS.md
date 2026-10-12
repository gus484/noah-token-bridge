# Noah Token Bridge

Liest einen Growatt Noah 2000 über die offizielle Growatt-OpenAPI (API-Token, kein Login) aus und
legt die Werte per MQTT Discovery als Gerät "Growatt Noah 2000" in Home Assistant an.

## Voraussetzungen

- Das Mosquitto-Add-on (oder ein anderer MQTT-Broker mit Supervisor-Dienst) läuft.
- Ein API-Token (ShinePhone-App: Ich → Benutzername → API Token).
- Die Seriennummer des Noah (Typenschild oder App).
- **noah-mqtt ist gestoppt**, mit deaktiviertem Autostart und Watchdog.

## Optionen

| Option | Bedeutung | Standard |
| --- | --- | --- |
| `token` | Growatt-API-Token | – |
| `device_sn` | Seriennummer des Noah | – |
| `server_url` | Growatt-Server deines Kontos (Region) | `https://openapi.growatt.com` |
| `entity_prefix` | Präfix der `entity_id`s, z. B. `sensor.noah_2000_soc` | `noah_2000` |
| `capacity_per_pack_kwh` | Nutzbare Kapazität je Akkupack (für gespeicherte Energie und Restlaufzeit) | 2.048 |
| `energy_interval` | Sekunden zwischen Live-Abrufen (mindestens 300) | 300 |
| `details_interval` | Sekunden zwischen Einstellungs-Abrufen (mindestens 300) | 900 |
| `slow_interval` | Sekunden für WLAN-Signal und Firmware (mindestens 60) | 3600 |
| `max_requests_per_hour` | Harte Obergrenze für Requests an Growatt | 60 |
| `log_level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_password` | Nur setzen, wenn nicht der Supervisor-Broker genutzt wird | leer |

## Energiezähler

Die Bridge integriert PV-Leistung und Akkuleistung selbst zu kWh-Zählern (PV, Akku geladen, Akku
entladen; heute und gesamt) und legt sie als Sensoren an. Sie eignen sich direkt für das
Energie-Dashboard (Solarproduktion, Batterie). Die Zählerstände liegen in `/data/noah_state.json`
und bleiben über Neustarts erhalten. Über Lücken (Netzausfall, Rechner im Ruhezustand) wird nicht
integriert; die Werte sind Näherungen aus 5-Minuten-Messungen.

## Verhalten bei Fehlern

Jeder Fehler führt zu exponentiell wachsender Wartezeit (1, 2, 4 … bis 30 Minuten), nie zu einem
sofortigen Neuversuch. Währenddessen steht die Verfügbarkeit der Entitäten auf "nicht verfügbar".
Das Stundenlimit gilt für alle Requests und ist unabhängig von den Intervallen.

---

# English

Reads a Growatt Noah 2000 through the official Growatt OpenAPI (API token, no login) and creates it as device "Growatt Noah 2000" in Home Assistant via MQTT Discovery. Read-only.

**Requirements:** Mosquitto add-on (or another broker with a Supervisor service), an API token (ShinePhone app: Me, user name, API Token), the Noah's serial number, and any other Growatt integration on the same account (e.g. noah-mqtt) stopped.

**Options:** `token`, `device_sn`, `server_url` (Growatt server of your region, default `https://openapi.growatt.com`), `entity_prefix` (e.g. `noah_2000` gives `sensor.noah_2000_soc`), `capacity_per_pack_kwh` (default 2.048), `energy_interval` (min. 300 s), `details_interval` (min. 300 s), `slow_interval` (min. 60 s), `max_requests_per_hour` (hard cap, default 60), `log_level`. `mqtt_*` only if you do not use the Supervisor broker. Labels and help texts appear in the configuration form.

**Energy counters:** PV power and battery power are integrated into kWh counters (PV, battery charged/discharged; today and total) usable in the Energy dashboard; use the *total* entities. Values are approximations from 5-minute samples and are not integrated across gaps.

**Errors:** every failure leads to exponentially growing waits (1, 2, 4 ... 30 minutes), never an immediate retry; entities show "unavailable" meanwhile.
