# Noah 2000 → Home Assistant über die offizielle Growatt-API

Oct 11, 2026 · @Markus

## Ziel und Ausgangslage

Ziel: Den Noah 2000 mit einer eigenen, kleinen Python-Bridge in Home Assistant holen, die sich per API-Token statt mit Benutzername und Passwort anmeldet. Kein Captcha, keine Login-Schleife, keine Account-Sperre durch Neustarts.

Warum noah-mqtt ersetzt wird:

- Der Web-Login von noah-mqtt schickt nur Benutzername und Passwort. Seit Growatt auf der Webseite ein Captcha verlangt, schlägt er fehl, ohne dass das Add-on es merkt.
- `postForm()` loggt sich daraufhin ohne Pause und ohne Abbruch immer wieder neu ein. Am 11.10. lief das über eine Stunde, mit zehntausenden Requests, bis Growatt nicht mehr antwortete.
- Die App-API von noah-mqtt ist ebenfalls inoffiziell und kann jederzeit gesperrt werden.

Die offizielle Growatt OpenAPI arbeitet mit einem Token, das du einmal im Growatt-Konto erzeugst. Für den Noah ist sie seit API-Version 4 nutzbar.

## Architektur

Ein einziger Dienst, die Bridge, spricht mit Growatt. Home Assistant sieht nur MQTT-Entitäten und weiß nichts von der Cloud.

&#91;embedded content: Architektur · Noah → Growatt-Cloud → Bridge → Mosquitto → Home Assistant\]

Werte fließen oben von links nach rechts zur Bridge und unten über Mosquitto zu Home Assistant; Befehle laufen denselben Weg zurück bis zum Noah. Der Shelly ist eine optionale, rein lokale Ergänzung.

## Schritt 1: API-Token beschaffen und von Hand testen

Bevor eine Zeile Bridge-Code entsteht, muss feststehen, dass dein Token den Noah überhaupt sieht. Das ist der wichtigste Test im ganzen Plan.

**Token holen** (eine der beiden Varianten):

1. ShinePhone-App: „Ich“ → dein Benutzername → „API Token“ → kopieren oder neu anfordern. Das ist der bevorzugte Weg, weil die Webseite gerade ein Captcha verlangt.
2. Webseite openapi.growatt.com: anmelden → Benutzername oben rechts → „Account Management“ → „API Token“.

**Von Hand testen** auf deinem Rechner, nicht im Home Assistant:

```bash
python -m venv venv && source venv/bin/activate
pip install growatt-public-api
```

```python
from growatt_public_api import GrowattApi

api = GrowattApi(token="DEIN_TOKEN")
plants = api.plant.list()
print(plants)
plant_id = plants.data.plants[0].plant_id
devices = api.plant.list_devices(plant_id=plant_id)
print(devices)
sn = devices.data.devices[0].device_sn
print(api.device.get_device_type(device_sn=sn))
print(api.noah.details_v4(device_sn=sn))
print(api.noah.power_realtime(device_sn=sn))
```

**Abbruchkriterium:** Taucht der Noah in der Geräteliste nicht auf oder liefert `details_v4()` nichts Brauchbares, lohnt der Rest des Plans nicht. In einer noah-mqtt-Diskussion berichtet ein Nutzer, dass sein Endkunden-Token keine Geräte lieferte, ein anderer sah Neo 800 und Noah 2000 problemlos.

- [ ] Token erzeugt und sicher abgelegt (Passwort-Manager)
- [ ] Plant-ID und Seriennummer des Noah ermittelt
- [x] `details_v4()` und `energy_v4()` liefern Werte (Test am 11.10.2026 bestanden); `power_realtime()` liefert `data: null`, `plant.list_devices()` ist leer, die Seriennummer muss also von Hand gesetzt werden
- [ ] Ausgabe als JSON gespeichert: daraus baut Claude Code später die Entitäten

## Schritt 2: Was die Bridge können muss

Die Bridge ist ein einzelner Python-Dienst: alle paar Minuten Werte holen, per MQTT veröffentlichen, Befehle aus Home Assistant entgegennehmen. Die wichtigste Regel steht ganz oben: Sie darf Growatt niemals so beschießen wie noah-mqtt.

**Robustheit (Pflicht, nicht optional):**

- Kein Login, keine Sitzung: jeder Request trägt nur das Token.
- Fehler und Rate-Limit-Antworten führen zu exponentiellem Backoff, zum Beispiel 1 → 2 → 4 … bis maximal 30 Minuten. Niemals sofortiger Retry, niemals Rekursion.
- Ein globaler Zähler begrenzt Requests pro Stunde hart, auch wenn der Code einen Fehler hat.
- Bei Fehlern wird `availability` auf `offline` gesetzt, statt den Prozess abstürzen zu lassen.

**Daten lesen** (Bibliotheksaufrufe aus Schritt 1):

| Zweck | Aufruf | Vorschlag Intervall |
| --- | --- | --- |
| Live-Werte: SOC, PV, Ausgang, Akkuleistung, Packs, Energie heute/Monat/gesamt | `noah.energy_v4()` | 5 min (Start, später anpassen) |
| Einstellungen: SOC-Grenzen, Zeitfenster, Firmware-Stände | `noah.details_v4()` | 15 min |
| WLAN-Signal, Firmware-Update | `noah.wifi_strength()`, `noah.firmware_info()`, `noah.device_info()` | 1 h |
| Optional | `noah.power_realtime()` | aus; lieferte im Test `data: null` |

Die Seriennummer des Noah steht als Konfigurationsoption (`device_sn`) in der Bridge, denn `plant.list_devices()` liefert für dieses Token keine Geräte.

Die Intervalle sind Startwerte. Die echten Limits der API kennst du erst, wenn die erste Rate-Limit-Meldung kommt; die Bibliothek cached Antworten selbst, um genau diese Meldung zu vermeiden.

**Entitäten in Home Assistant** (per MQTT Discovery):

- Sensoren (aus `energy_v4`): Gesamt-SOC in % (`total_battery_pack_soc`), PV-Leistung (`ppv`), Ausgangsleistung (`pac`), Akku-Lade-/Entladeleistung (`total_battery_pack_charging_power`), Energie heute/Monat/Jahr/gesamt in kWh (`eac_*`), Zyklen, Gesundheitszustand, Systemtemperatur, Status, WLAN-Signal.
- Pro Akkupack (der Noah hat bis zu vier, `battery_package_quantity` gibt die Anzahl an): SOC und Temperatur. Entitäten nur für vorhandene Packs anlegen; Seriennummer weglassen, sie ist privat.
- Energiesensoren mit `device_class: energy` und `state_class: total_increasing`, damit sie im Energie-Dashboard auftauchen.
- Ein gemeinsames Gerät „Growatt Noah 2000“, damit alles zusammen angezeigt wird.

**Steuern** (zweite Ausbaustufe, erst nach stabilem Lesebetrieb):

- `noah.setting_write_active_power()` als `number`-Entität für die Ausgangsleistung.
- Es gibt kein `setting_write_on_off()`. Stattdessen als `switch`: `noah.setting_write_grid_charging()` (Netzladen) und `noah.setting_write_off_grid()` (Off-Grid); als `number`: `setting_write_soc_upper_limit()` und `setting_write_soc_lower_limit()`. Alle Schreibaufrufe sind auf einmal pro 5 Sekunden begrenzt.
- Zeitfenster und Modus (Load First, Battery First) über `noah.setting_write_vpp_param()`.
- Laut Bibliotheksautor melden Schreibbefehle teils `SYSTEM_ERROR`, wirken aber trotzdem. Deshalb nach jedem Schreiben den Wert zurücklesen statt der Fehlermeldung zu trauen.

## Schritt 3: Betrieb in Home Assistant

Empfehlung: Die Bridge als lokales Add-on betreiben. Du nutzt schon Mosquitto als Add-on, also passt das ohne zusätzliche Infrastruktur.

**Variante A – lokales Add-on (empfohlen)**

1. `python scripts/package_addon.py` ausführen. Es baut `dist/noah_token_bridge/` aus `addon/` und dem Python-Code.
2. Diesen Ordner nach `/addons/noah_token_bridge/` kopieren, zum Beispiel über das Samba- oder SSH-Add-on. Darin liegen `config.yaml`, `Dockerfile`, `DOCS.md`, `requirements.txt` und `noah_bridge/`. Eine `run.sh` gibt es nicht: Das Image basiert auf `python:3.13-alpine` und startet `python -m noah_bridge` direkt (`init: false`).
3. In `config.yaml` sind die Optionen `token` (Passwortfeld), `device_sn`, die Intervalle, `max_requests_per_hour`, `entity_prefix` und `log_level` definiert.
4. Die MQTT-Zugangsdaten holt die Bridge selbst vom Supervisor-Dienst `mqtt` (`services: mqtt:need`). Nur wenn `mqtt_host` gesetzt ist, gelten stattdessen die eigenen Werte.
5. In Home Assistant: Einstellungen → Add-ons → Add-on Store → ⋮ → „Nach Updates suchen“. Das Add-on erscheint unter „Lokale Add-ons“.
6. Installieren, Token eintragen, starten, Log prüfen.

**Variante B – Docker-Container auf einem anderen Rechner im Heimnetz**

Sinnvoll zum Entwickeln und Testen, bevor du daraus ein Add-on machst. Die Bridge braucht dann nur Host, Port, Benutzer und Passwort deines Mosquitto.

**Umstellung von noah-mqtt**

- [ ] noah-mqtt stoppen und Autostart sowie Watchdog deaktivieren
- [ ] Neue Bridge starten, Entitäten unter Einstellungen → Geräte & Dienste → MQTT prüfen
- [ ] Werte einen Tag lang mit der ShinePhone-App vergleichen
- [ ] Automationen und Dashboards von den alten auf die neuen Entitäten umstellen
- [ ] Energiesensoren im Energie-Dashboard eintragen
- [ ] noah-mqtt deinstallieren; verwaiste MQTT-Geräte entfernen

**Tipp:** Wenn die neuen Entitäten dieselben `entity_id`s bekommen sollen wie die alten, gib der Bridge passende `object_id`s mit. Dann laufen bestehende Automationen ohne Änderung weiter.

## Schritt 4: Claude Code den Code bauen lassen

Claude Code arbeitet am besten in kleinen, überprüfbaren Etappen mit echten Beispieldaten. Deshalb zuerst die JSON-Ausgaben aus Schritt 1 ins Projekt legen, dann den Prompt unten verwenden.

**Vorbereitung:**

1. Leeres Git-Repository anlegen, zum Beispiel `noah-token-bridge`.
2. Ordner `samples/` mit den gespeicherten Antworten aus Schritt 1 (Token und Seriennummer vorher unkenntlich machen).
3. Claude Code im Ordner starten und mit dem Prompt beginnen.
4. Nach jeder Etappe selbst testen, erst dann „weiter“ sagen.

**Etappen:**

1. Projektgerüst, Konfiguration, Logging, Tests gegen `samples/`.
2. Lesebetrieb mit Backoff und Request-Limit, MQTT Discovery, lokal gegen deinen Mosquitto testen.
3. Verpackung als Home-Assistant-Add-on.
4. Steuerung (Ausgangsleistung 0–800 W, SOC-Grenzen, Netzladen, Off-Grid, Modus) mit Zurücklesen nach dem Schreiben.

**Prompt für den Start:**

```markdown
Baue einen Python-Dienst "noah-token-bridge", der einen Growatt Noah 2000 über die
offizielle Growatt OpenAPI (v4, Token-Auth) ausliest und per MQTT Discovery in
Home Assistant bereitstellt.

Rahmen:
- Python >= 3.10, Bibliothek growatt-public-api (Import: from growatt_public_api import GrowattApi)
- MQTT mit paho-mqtt, Home Assistant MQTT Discovery, ein Gerät "Growatt Noah 2000"
- Konfiguration über Umgebungsvariablen und optional /data/options.json (HA-Add-on)
- Beispielantworten der API liegen in samples/ – Modelle und Entitäten daraus ableiten

Harte Regeln (wichtig, das Vorgängertool hat Growatt mit Endlos-Retries geflutet):
- Keine Rekursion bei Retries, kein sofortiger Retry
- Exponentieller Backoff bei jedem Fehler, max. 30 Minuten
- Globales Limit: höchstens N Requests pro Stunde (konfigurierbar), danach warten
- Fehler setzen availability auf offline, der Prozess läuft weiter
- Token nie loggen

Abfragen und Intervalle (konfigurierbar):
- noah.energy_v4(): 5 min (liefert die Live-Werte)
- noah.details_v4(): 15 min
- noah.wifi_strength(), noah.firmware_info(), noah.device_info(): 1 h
- noah.power_realtime() nicht abfragen (liefert im Test null)
- Die Seriennummer kommt als Konfigurationsoption device_sn; plant.list_devices() ist leer

Entitäten: Gesamt-SOC (%), PV-Leistung, Ausgangsleistung, Akku-Leistung (W),
Energie heute/Monat/Jahr/gesamt (kWh, device_class energy, state_class total_increasing),
Zyklen, Gesundheitszustand, Temperatur, WLAN-Signal, Status.
Pro Akkupack SOC und Temperatur (Anzahl aus battery_package_quantity).
Feldnamen stehen in samples/noah_energy_v4.json.

Arbeite in Etappen und halte nach jeder an:
1. Gerüst + Konfiguration + Unit-Tests gegen samples/
2. Polling-Loop mit Backoff/Limit + MQTT Discovery
3. Home-Assistant-Add-on (config.yaml, Dockerfile, run.sh, MQTT über Supervisor-Dienst)
4. Steuerung: number für Ausgangsleistung (setting_write_active_power),
   switch für Netzladen (setting_write_grid_charging) und Off-Grid (setting_write_off_grid),
   number für SOC-Ober-/Untergrenze (setting_write_soc_upper_limit/_lower_limit); nach jedem Schreiben Wert zurücklesen

Starte mit Etappe 1 und zeig mir vorher kurz deinen Plan.
```

## Risiken, offene Fragen und Fallbacks

Das größte Risiko ist, dass dein Endkunden-Token den Noah nicht liefert. Deshalb steht der Test in Schritt 1 vor allem anderen.

| Risiko | Folge | Fallback |
| --- | --- | --- |
| Token liefert keine Geräte | Plan nicht umsetzbar | Token über Händler/Installateur beantragen; sonst noah-mqtt mit langem Intervall |
| Unbekannte Rate-Limits der v4-API | Werte veralten, Sperre möglich | Konservativ starten (5 min), Limit-Meldungen loggen, Intervalle anpassen |
| Bibliothek ist Beta, ein Entwickler | Bricht bei API-Änderungen | Version in `requirements.txt` festpinnen, Updates bewusst testen |
| Schreibbefehle melden `SYSTEM_ERROR` | Unklar, ob Befehl wirkte | Nach jedem Schreiben zurücklesen |
| Growatt-Cloud fällt aus | Keine Daten, keine Steuerung | Leistung lokal mit Shelly am Wechselrichter-Ausgang messen |

**Offene Fragen:**

- Welcher Wechselrichter hängt am Noah? Bei einem Hoymiles ginge die Einspeiseregelung lokal per OpenDTU, unabhängig von Growatt.
- Wie oft brauchst du Werte wirklich? Für Statistik reichen 5 bis 15 Minuten; für Nulleinspeisung ist die Cloud grundsätzlich zu langsam.

## Zurückgestellt

- [ ] **Nullwerte der Akkupacks filtern.** Die API liefert vereinzelt `batteryN_soc = 0` für ein Pack, obwohl der Gesamt-SOC deutlich darüber liegt (gesehen am 12.10.2026 um 08:44: Pack 2 zeigte einmal 0 %, fünf Minuten später wieder 9 %). Home Assistant würde das als echten Einbruch aufzeichnen. Idee: Pack-SOC `0` nur übernehmen, wenn der Gesamt-SOC ebenfalls nahe 0 ist, sonst den vorherigen Wert beibehalten oder `None` veröffentlichen. Mit Test gegen ein präpariertes Sample.
- [ ] **Akku-Wirkungsgrad** (entladen ÷ geladen, gleitende Woche, um die SOC-Differenz korrigiert) und **Pack-Gleichlauf** (SOC- und Temperaturabstand der Packs), sobald genug Zählerhistorie vorliegt. Die Zähler selbst (PV, Akku laden/entladen, Restlaufzeit, Vollzyklen, Systemwirkungsgrad) sind fertig.
- [ ] **Steuerung (Etappe 4)** nach Bedarf, siehe Schritt 2.
- [ ] **`object_id` in der Discovery** prüfen: Neuere Home-Assistant-Versionen stufen das Feld meines Wissens als veraltet ein (Nachfolger `default_entity_id`). Auf dem echten Home Assistant kontrollieren, ob die `entity_id`s stimmen.
- [ ] **Ladestatus (roh)** als Text anzeigen, sobald die Werte 0, 1 und 2 beobachtet und zugeordnet sind (bisher: 0 = Laden, 2 = Entladen).

## Quellen

- [growatt-public-api auf PyPI](https://pypi.org/project/growatt-public-api/) (Version 2026.5.19, Noah-Funktionen, Token-Beschaffung)
- [noah-mqtt: client\_http.go](https://raw.githubusercontent.com/mtrossbach/noah-mqtt/main/internal/growatt_web/client_http.go) und [client.go](https://raw.githubusercontent.com/mtrossbach/noah-mqtt/main/internal/growatt_web/client.go) (Ursache der Login-Schleife)
- [noah-mqtt Diskussion #70: Growatt API Token](https://github.com/mtrossbach/noah-mqtt/discussions/70) (Erfahrungen mit Endkunden-Tokens)
