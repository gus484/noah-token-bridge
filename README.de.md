# Noah Token Bridge

*English: [README.md](README.md)*

Home-Assistant-Add-on, das einen **Growatt Noah 2000** über die **offizielle Growatt-OpenAPI** (API-Token, kein Web-Login) ausliest und per **MQTT Discovery** bereitstellt. Es liest nur.

> Inoffizielles Projekt, steht in keiner Verbindung zu Growatt. Nutzung auf eigenes Risiko.

## Warum

Add-ons, die sich über die Growatt-Weboberfläche anmelden, können in endlosen Login-Versuchen enden (z. B. nach Einführung eines Captchas) und belasten Growatt. Diese Bridge nutzt nur die Token-API und ist darauf ausgelegt, Growatt nicht zu fluten: hartes Stundenlimit, Mindestabstand zwischen Requests, exponentieller Backoff je Abfrage, keine Wiederholschleifen.

## Installation

1. Home Assistant → Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories → `https://github.com/gus484/noah-token-bridge` hinzufügen.
2. **Noah Token Bridge** installieren. Voraussetzung: Mosquitto-Add-on (oder ein anderer beim Supervisor registrierter Broker) und die MQTT-Integration.
3. Im Reiter *Konfiguration* **API-Token** und **Seriennummer** des Noah eintragen, dann das Add-on starten.

### Token und Seriennummer finden

- Token: ShinePhone-App → *Ich* → Benutzername → *API Token*.
- Seriennummer: Typenschild des Noah oder App. Die Geräteliste der API ist beim Noah oft leer, daher wird die Seriennummer von Hand eingetragen.
- Server: Standard `https://openapi.growatt.com`. Konten in anderen Regionen brauchen den Server ihrer Region (z. B. `https://openapi-us.growatt.com`).

Andere Growatt-Integrationen mit demselben Konto (z. B. `noah-mqtt`) vorher stoppen.

## Was geliefert wird

Gerät "Growatt Noah 2000" mit Ladestand, PV-, Ausgangs- und Akkuleistung, Temperaturen, Werten je Akkupack, Einstellungen, WLAN/Firmware sowie bridge-eigene Energiezähler (PV, Akku geladen/entladen; heute und gesamt) für das Energie-Dashboard und abgeleitete Werte (gespeicherte Energie, Restlaufzeit, Zyklen, Wirkungsgrad). Im Energie-Dashboard die *gesamt*-Entitäten verwenden.

## Grenzen

- Getestet mit einem Noah 2000 an einem Konto. Andere Geräte (Nexa, mehrere Noah) und Installateur-/Händler-Tokens sind ungetestet.
- Noch keine Steuerung (Ausgangsleistung, SOC-Grenzen).
- Entitätsnamen sind derzeit deutsch.

Die Optionen stehen in [noah_token_bridge/DOCS.md](noah_token_bridge/DOCS.md). Entwicklungsnotizen: `CLAUDE.md`, `PLAN.md`.

Lizenz: MIT
