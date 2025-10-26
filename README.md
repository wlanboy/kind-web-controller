# Kurzbeschreibung
Dieses Projekt startet einen FastAPI-Server (`main:app`) und nutzt Uvicorn als ASGI-Server. Siehe [`main:app`](main.py) für die App-Instanz und [pyproject.toml](pyproject.toml) für die deklarierte Abhängigkeiten.

# Voraussetzungen
- Python 3.12 (siehe [.python-version](.python-version))
- Git
- Optional: Docker / kind / kubectl (für Cluster-Operationen)

# Virtuelle Umgebung
Empfohlen: lokale venv im Projekt:
```bash
# einmalig
python3 -m venv .venv

# aktivieren (bash / zsh)
source .venv/bin/activate
```

# Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

# Uvicorn (uv) — Entwicklung vs. Produktion ("uv sync")
- Entwicklung: Verwenden Sie `--reload`, damit der Server bei Codeänderungen neu startet.
- Produktion: Entfernen Sie `--reload`. Für mehrere Prozesse/CPU-Kerne nutzen Sie `--workers` oder einen Prozessmanager (z. B. systemd oder Gunicorn mit Uvicorn-Worker).
Beispiele:
```bash
# Entwicklung (Hot reload)
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Produktion (einfach)
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```
Der Parameter `--workers` startet mehrere Prozesse (sinnvoll für CPU-bound Arbeit). Uvicorn selbst ist asynchron; synchroner Modus wird durch Einsatz multipler Worker bzw. durch Kombination mit Gunicorn erreicht.
