# Smart Homelab Monitoring System

Das Monitoring liest jetzt echte Messwerte von einem JoyPi mit Raspberry Pi OS und einem DHT22 an **BCM GPIO 4**. Der Stack läuft auf dem Windows-PC; die Sensor-API verbindet sich per SSH mit dem JoyPi und führt dort den Sensor-Agenten aus. Es gibt keine simulierten Temperatur- oder Feuchtigkeitswerte.

## Komponenten

- JoyPi-Sensor-Agent liest Temperatur und relative Luftfeuchtigkeit vom DHT22.
- Sensor-API fragt den Agenten per SSH mit geprüftem SSH-Host-Key ab und stellt JSON sowie Prometheus-Metriken bereit.
- Prometheus speichert Messwerte und wertet Alarmregeln für Temperatur, Luftfeuchtigkeit und Sensorverbindung aus.
- Grafana enthält ein automatisch eingerichtetes Dashboard für die tatsächlichen DHT22-Messwerte.
- Loki und Promtail sammeln Container- und Systemlogs.
- Die Webübersicht zeigt Live-Messwerte und einen aus Temperatur und Feuchtigkeit berechneten Umgebungs-Score.

Andere Sensoren des ursprünglichen Projektentwurfs (z. B. Helligkeit, Bewegung, Türkontakt oder ein echtes LCD) werden nicht angezeigt, solange sie nicht angeschlossen und implementiert sind.

## 1. DHT22 am JoyPi anschließen

Bei einem DHT22-Sensormodul:

- VCC an 3,3 V
- GND an GND
- DATA an BCM GPIO 4 (physischer Pin 7)
- Bei einem nackten DHT22 einen 4,7–10 kΩ Pull-up-Widerstand zwischen DATA und 3,3 V verwenden. Viele Module haben den Widerstand bereits eingebaut.

Vor dem Verdrahten den JoyPi ausschalten. Raspberry-Pi-GPIOs sind nicht 5-V-tolerant.

## 2. Sensor-Agent auf dem JoyPi installieren

Auf dem JoyPi ein Benutzerkonto mit SSH-Zugang verwenden. In PowerShell im Projektordner den Agenten kopieren (Benutzer und IP ersetzen):

```powershell
ssh <BENUTZER>@<JOYPI-IP> "mkdir -p ~/homelab-monitoring"
scp .\joypi\sensor_agent.py <BENUTZER>@<JOYPI-IP>:homelab-monitoring/sensor_agent.py
```

Auf dem JoyPi:

```bash
sudo apt update
sudo apt install -y python3-venv libgpiod2
python3 -m venv --system-site-packages ~/homelab-monitoring/.venv
~/homelab-monitoring/.venv/bin/pip install adafruit-circuitpython-dht==4.0.7
~/homelab-monitoring/.venv/bin/python ~/homelab-monitoring/sensor_agent.py --json
```

Der letzte Befehl sollte genau eine JSON-Zeile mit `temperature_celsius` und `humidity_percent` ausgeben. Falls der Zugriff auf GPIO verweigert wird, prüfen, ob der JoyPi-Benutzer Mitglied der GPIO-Gruppe ist, und danach neu anmelden.

## 3. SSH sicher einrichten

Im Projektordner eine SSH-Schlüsseldatei erzeugen:

```powershell
ssh-keygen -t ed25519 -N "" -f .\secrets\joypi_ed25519
```

Den öffentlichen Schlüssel zum JoyPi hinzufügen:

```powershell
Get-Content .\secrets\joypi_ed25519.pub | ssh <BENUTZER>@<JOYPI-IP> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

Den SSH-Host-Key des JoyPi in `secrets/known_hosts` eintragen. Mit OpenSSH verfügbarer `ssh-keyscan`-Befehl:

```powershell
ssh-keyscan -H <JOYPI-IP> | Out-File -Encoding ascii .\secrets\known_hosts
```

Den Fingerabdruck anschließend mit dem auf dem JoyPi angezeigten SSH-Host-Key-Fingerabdruck vergleichen. Die API weist unbekannte oder geänderte Host-Keys zurück. Private Schlüssel und `known_hosts` liegen im ignorierten Ordner `secrets/` und dürfen nicht ins Repository eingecheckt werden.

## 4. Windows-Stack konfigurieren und starten

```powershell
Copy-Item .env.example .env
notepad .env
```

In `.env` `JOYPI_SSH_HOST`, `JOYPI_SSH_USER`, `JOYPI_PYTHON` und `JOYPI_AGENT_PATH` anpassen. Die beiden Pfade müssen zum JoyPi-Benutzer passen. Standardmäßig sind sie für den Benutzer `pi` eingetragen. Keine Zugangsdaten ins Repository schreiben.

Dann den Stack starten:

```powershell
docker compose up --build -d
```

Oberflächen:

- Dashboard: http://localhost:8081/
- Grafana: http://localhost:3000/ (Standard: `admin` / `admin`)
- Prometheus: http://localhost:9090/
- Sensor-API: http://localhost:8000/api/status

Prüfen, ob Prometheus die Sensor-API abfragt:

```powershell
docker compose logs sensor-api
Invoke-RestMethod http://localhost:8000/api/status
```

Bei fehlender SSH-Konfiguration oder nicht erreichbarem JoyPi liefert die API HTTP 503, die Dashboard-Seite zeigt einen Verbindungsfehler, und Prometheus meldet den Sensor als getrennt. Es werden keine Ersatzmesswerte ausgegeben.

## Messwerte und Grenzwerte

- Der Agent liest den DHT22 an BCM GPIO 4 aus; Sensorauslesefehler werden dreimal mit Pause wiederholt.
- Das API-Ergebnis wird maximal 10 Sekunden zwischengespeichert (`SENSOR_CACHE_SECONDS`).
- Temperaturwarnung: über 30 °C für 2 Minuten.
- Luftfeuchtigkeitswarnung: unter 20 % oder über 70 % für 5 Minuten.
- Der Umgebungs-Score ist eine einfache Bewertung aus Temperatur und Luftfeuchtigkeit, kein allgemeiner Server-Health-Score.

`node-exporter` im Windows-Docker-Stack misst die Linux-Docker-Umgebung, nicht den Windows-PC. Für echte Windows-Systemmetriken muss zusätzlich `windows_exporter` auf dem Windows-PC installiert und als weiteres Prometheus-Ziel konfiguriert werden.
