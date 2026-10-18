"""BAZOR startup inventory and Studio journal. Standard library; no paid calls or service changes.

Installed per user under LocalAppData/BAZOR/Veille. The full report stays in Documents.
The Windows Run entry starts this at user sign-in, not before Windows antivirus starts.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path


APP = "BAZOR Veille"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LOCAL = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
ROOT = LOCAL / "BAZOR" / "Veille"
STUDIO = Path(r"C:\AI\SimpleStudioV2")
COMFY = Path(r"C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI")
KNOWN_PORTS = {"Ollama": 11434, "Core": 8775, "Room": 8765, "Studio": 8191, "ComfyUI": 8188}
PORT_PATHS = {
    "Ollama": "/api/tags", "Core": "/api/v1/health", "Room": "/api/status",
    "Studio": "/api/config", "ComfyUI": "/system_stats",
}
INTERESTING = re.compile(r"bazor|ollama|notrack|mammouth|mamouth|studio|comfy|mcafee|trellix", re.I)
ERROR = re.compile(r"error|exception|failed|fatal|traceback|erreur|echec|échec|invalid|rejected|rejet", re.I)
SECRET = re.compile(r"(?i)(bearer\s+|(?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;\"']+|\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})\b")
SHOW_FLAG = ROOT / "show.flag"
STOP_FLAG = ROOT / "stop.flag"
UTILITY = (
    (re.compile(r"ollama", re.I), "serveur de modèles locaux"),
    (re.compile(r"mcafee|trellix|defender|msmpeng", re.I), "protection antivirus"),
    (re.compile(r"chatgpt|openai", re.I), "application ChatGPT ; intégration BAZOR à prouver"),
    (re.compile(r"comfy", re.I), "moteur de génération image/vidéo"),
    (re.compile(r"studio", re.I), "interface de création vidéo"),
    (re.compile(r"bazor", re.I), "composant BAZOR ; rôle à confirmer par sa commande ou son port"),
    (re.compile(r"notrack", re.I), "outil NoTrack ; connexion BAZOR à vérifier"),
    (re.compile(r"python", re.I), "interpréteur Python ; rôle à confirmer par la commande ou le port"),
    (re.compile(r"onedrive", re.I), "synchronisation des fichiers"),
    (re.compile(r"explorer\.exe", re.I), "bureau et fenêtres Windows"),
)


def utility(name: str) -> str:
    return next((description for pattern, description in UTILITY if pattern.search(name)),
                "rôle à identifier ; le nom seul ne prouve pas son utilité")


def documents() -> Path:
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
                value, _ = winreg.QueryValueEx(key, "Personal")
                return Path(os.path.expandvars(value)) / "BAZOR"
        except Exception:
            pass
    return Path.home() / "Documents" / "BAZOR"


REPORTS = documents()
STUDIO_LOGS = REPORTS / "Studio"


def clean(value: object, limit: int = 600) -> str:
    s = str(value or "")
    s = SECRET.sub(lambda m: (m.group(1) or "") + "[MASQUÉ]", s)
    return s[:limit]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run(args: list[str], timeout: int = 7) -> tuple[int, str]:
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, creationflags=CREATE_NO_WINDOW, check=False)
        return p.returncode, p.stdout[:1_000_000].decode("utf-8-sig", "replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, type(exc).__name__ + ": " + clean(exc)


def local_json(port: int, route: str, timeout: float = 2.5, payload: dict | None = None) -> object:
    url = f"http://127.0.0.1:{port}{route}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        raw = response.read(512_001)
        if len(raw) > 512_000:
            raise ValueError("Réponse trop volumineuse")
        return json.loads(raw.decode("utf-8-sig"))


def probe_service(name: str) -> dict:
    port = KNOWN_PORTS[name]
    try:
        data = local_json(port, PORT_PATHS[name])
        if not isinstance(data, dict):
            return {"état": "HTTP répondu, identité inconnue", "port": port}
        if name == "Ollama":
            models = [str(m.get("name", "")) for m in data.get("models", []) if isinstance(m, dict)]
            return {"état": "répond", "port": port, "modèles": models,
                    "identité_BAZOR": "modèle dédié à examiner" if any("bazor" in m.lower() for m in models) else "non démontrée par les noms de modèles"}
        expected = {"Core": ("ok", "version", "status", "service"),
                    "Room": ("ok", "version", "status"),
                    "Studio": ("version", "token"),
                    "ComfyUI": ("system", "devices")}[name]
        identity = any(k in data for k in expected)
        return {"état": "répond" if identity else "HTTP répondu, identité non vérifiée",
                "port": port, "champs": list(data)[:12]}
    except Exception as exc:
        return {"état": "indisponible ou identité non vérifiée", "port": port,
                "détail": type(exc).__name__ + ": " + clean(exc, 120)}


def stage(report: dict, name: str, fn) -> None:
    try:
        report[name] = fn()
    except Exception as exc:
        report[name] = {"état": "contrôle impossible", "raison": type(exc).__name__ + ": " + clean(exc, 200)}


def paths() -> dict:
    home = Path.home()
    known = {
        "Dépôt BAZOR": home / "bazor-mobile",
        "Core installé": LOCAL / "BAZOR" / "Core" / "bazor_pc_relay_v3.py",
        "Room installée": LOCAL / "BazorAIROOM" / "app.py",
        "Lanceur Room": LOCAL / "BazorAIROOM" / "DEMARRER_BAZOR_AI_ROOM.cmd",
        "Studio": STUDIO / "app" / "studio.py",
        "Workflow Studio": STUDIO / "app" / "workflows.py",
        "ComfyUI": COMFY / "main.py",
        "NoTrack Coder": home / "NoTrackCoder",
        "Pont Mammouth BAZOR": home / "bazor-mobile" / "pc-relay" / "mammouth_transport.py",
        "Pont Mamouth isolé (non intégré)": home / "mamouth_bridge.py",
    }
    return {name: {"présent": path.exists(), "chemin": str(path)} for name, path in known.items()}


def startup() -> dict:
    out: dict = {"registre": [], "dossiers": [], "tâches": []}
    if os.name != "nt":
        return {"état": "Windows requis"}
    import winreg
    for hive, label in ((winreg.HKEY_CURRENT_USER, "utilisateur"), (winreg.HKEY_LOCAL_MACHINE, "machine")):
        try:
            with winreg.OpenKey(hive, RUN_KEY) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        out["registre"].append({"portée": label, "nom": name, "commande": clean(value, 300),
                                                 "utilité": utility(str(name) + " " + str(value))})
                        i += 1
                    except OSError:
                        break
        except OSError:
            pass
    folders = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup",
               Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"]
    for folder in folders:
        if folder.is_dir():
            out["dossiers"].extend({"chemin": str(p), "utilité": utility(p.name)}
                                    for p in folder.iterdir() if p.is_file())
    rc, txt = run(["schtasks", "/Query", "/FO", "CSV", "/V"], timeout=12)
    if rc == 0:
        out["tâches"] = [clean(" | ".join(row[:4]), 300) for row in list(csv.reader(io.StringIO(txt)))[1:] if INTERESTING.search(" ".join(row))][:50]
    else:
        out["tâches"] = ["inventaire indisponible : " + clean(txt, 100)]
    return out


def installed_programs() -> list[dict]:
    if os.name != "nt":
        return []
    import winreg
    found = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for base in (r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                     r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
            try:
                with winreg.OpenKey(hive, base) as parent:
                    i = 0
                    while True:
                        try:
                            sub = winreg.EnumKey(parent, i)
                            i += 1
                        except OSError:
                            break
                        try:
                            with winreg.OpenKey(parent, sub) as key:
                                name = winreg.QueryValueEx(key, "DisplayName")[0]
                                if INTERESTING.search(str(name)) or re.search(r"chatgpt|openai", str(name), re.I):
                                    try:
                                        location = winreg.QueryValueEx(key, "InstallLocation")[0]
                                    except OSError:
                                        location = "non indiqué"
                                    found.append({"nom": clean(name, 150), "emplacement": clean(location, 300)})
                        except OSError:
                            pass
            except OSError:
                pass
    return found[:80]


def processes() -> dict:
    rc, txt = run(["tasklist", "/FO", "CSV", "/NH"], timeout=10)
    if rc != 0:
        return {"état": "inventaire indisponible", "raison": clean(txt, 150)}
    rows = list(csv.reader(io.StringIO(txt)))
    snapshot = [{"nom": r[0], "PID": r[1], "utilité": utility(r[0])} for r in rows if len(r) > 1]
    interesting = [row for row in snapshot if INTERESTING.search(row["nom"])]
    rc2, net = run(["netstat", "-ano", "-p", "TCP"], timeout=8)
    listeners = []
    if rc2 == 0:
        for line in net.splitlines():
            fields = line.split()
            if len(fields) >= 5 and (fields[3].upper() in ("LISTENING", "ÉCOUTE", "ECOUTE")):
                for name, port in KNOWN_PORTS.items():
                    if fields[1].endswith(":" + str(port)):
                        listeners.append({"service_attendu": name, "adresse": fields[1], "PID": fields[4]})
    return {"processus_cibles": interesting[:150], "instantané_processus": snapshot[:600], "ports": listeners,
            "limite": "Instantané après ouverture de session, pas historique complet des créations de processus. Comparer PID, port et réponse HTTP."}


def antivirus() -> dict:
    result = {"produits": "non vérifiés", "événements": [], "limite": "Le journal Windows peut omettre les blocages internes à McAfee/Trellix."}
    rc, txt = run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                   "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct -ErrorAction Stop | Select-Object displayName,productState | ConvertTo-Json -Compress"], timeout=7)
    if rc == 0:
        try:
            result["produits"] = json.loads(txt)
        except ValueError:
            result["produits"] = "réponse non interprétable"
    else:
        result["produits"] = "sonde bloquée ou indisponible : " + clean(txt, 110)
    for channel in ("Microsoft-Windows-Windows Defender/Operational", "Application"):
        rc, xml = run(["wevtutil", "qe", channel, "/rd:true", "/c:120", "/f:xml"], timeout=8)
        if rc:
            continue
        import xml.etree.ElementTree as ET
        try:
            xml = re.sub(r"<\?xml[^>]*\?>", "", xml)
            root = ET.fromstring("<Events>" + xml + "</Events>")
            for event in root:
                provider = event.find(".//{*}Provider")
                name = provider.get("Name", "") if provider is not None else ""
                event_id = event.findtext(".//{*}EventID") or ""
                if channel == "Application" and not re.search(r"mcafee|trellix", name, re.I):
                    continue
                if channel != "Application" and event_id not in ("1116", "1117", "1121", "1122", "5007"):
                    continue
                created = event.find(".//{*}TimeCreated")
                values = [clean(e.text, 220) for e in event.findall(".//{*}Data") if e.text]
                result["événements"].append({"source": name, "id": event_id,
                                             "date": created.get("SystemTime") if created is not None else "",
                                             "détails": values[:5]})
        except ET.ParseError:
            result["événements"].append({"source": channel, "état": "journal non interprétable"})
    result["événements"] = result["événements"][:40]
    return result


def ai_inventory(report: dict) -> dict:
    p = report.get("Fichiers existants", {})
    services = report.get("Services locaux", {})
    key_presence = {key: bool(os.environ.get(key)) for key in ("NOTRACK_API_KEY", "MAMMOUTH_API_KEY", "OPENAI_API_KEY")}
    return {
        "Ollama": services.get("Ollama", {"état": "non contrôlé"}),
        "NoTrackAI": {"Coder installé ou dossier trouvé": bool(p.get("NoTrack Coder", {}).get("présent")),
                      "clé dans ce processus": key_presence["NOTRACK_API_KEY"],
                      "état API": "non interrogée (aucun appel externe ; 401 historique à confirmer)"},
        "Mammouth": {"pont dans dépôt": bool(p.get("Pont Mammouth BAZOR", {}).get("présent")),
                     "clé dans ce processus": key_presence["MAMMOUTH_API_KEY"],
                     "état API": "non interrogée pour éviter un appel payant"},
        "GPT / Astra": {"clé OpenAI dans ce processus": key_presence["OPENAI_API_KEY"],
                        "état": "aucun canal PC ou appel réel vérifié par cette veille"},
    }


def expected_services(report: dict) -> dict:
    p = report.get("Fichiers existants", {})
    s = report.get("Services locaux", {})
    expectations = {
        "Core": "Core installé", "Room": "Room installée", "Studio": "Studio",
        "ComfyUI": "ComfyUI", "Ollama": None,
    }
    out = {}
    for name, path_key in expectations.items():
        installed = bool(p.get(path_key, {}).get("présent")) if path_key else None
        current = s.get(name, {}).get("état", "non vérifié")
        on_demand = name in ("Studio", "ComfyUI")
        out[name] = {"fichier_trouvé": installed, "observé": current,
                     "conclusion": "service à la demande" if on_demand else
                         "répond" if current == "répond" else
                         "présent mais non opérationnel" if installed else "état d'installation à vérifier"}
    return out


def report_text(report: dict) -> str:
    lines = ["BAZOR — RAPPORT DE DÉMARRAGE", f"Date : {report['date']}",
             "Lecture seule : aucun Core, Room, Ollama, Studio ou ComfyUI redémarré.",
             "Aucun appel IA payant. Aucun secret publié. Ce rapport est local à votre PC.", ""]
    services = report.get("Services locaux", {})
    for name in KNOWN_PORTS:
        status = services.get(name, {})
        lines.append(f"{name} : {status.get('état', 'non vérifié')} (port {KNOWN_PORTS[name]})")
    lines += ["", "IDENTITÉ OLLAMA : les modèles et les consignes de BAZOR sont distincts.",
              "Le serveur Ollama ne sait pas automatiquement qu'il est BAZOR ; vérifier le prompt système du relais.",
              "Une future auto-configuration doit attendre la preuve du trajet Room → Core → Ollama.",
              "JOURNAL STUDIO : les erreurs remontées par les API et les fichiers log existants sont capturées.",
              "Une erreur visible seulement dans la console du navigateur exige un branchement dans l'interface Studio ; elle ne peut être capturée rétroactivement.",
              "Une console noire déjà lancée ne peut être masquée sans relancer son processus ; ne la fermez pas avant d'identifier son service.", ""]
    for key, value in report.items():
        if key in ("date", "Services locaux"):
            continue
        lines += [key.upper(), json.dumps(value, ensure_ascii=False, indent=2), ""]
    lines += ["PLAN COURT",
              "1. Rétablir Core + Room si le rapport les montre absents ; ne pas lancer de doublon.",
              "2. Certifier un trajet local Room → Core → Ollama avec les services réellement actifs.",
              "3. Résoudre l'authentification NoTrack, puis prouver son trajet dans BAZOR sans clé publiée.",
              "4. Corriger Studio à partir d'un job et d'une erreur observés ; ne pas changer le workflow à l'aveugle.",
              "5. Décider ensuite de l'auto-configuration et du déploiement avec sauvegarde et retour arrière.", ""]
    return "\n".join(lines)


def audit() -> dict:
    report: dict = {"date": now()}
    stage(report, "Fichiers existants", paths)
    stage(report, "Programmes déclarés installés", installed_programs)
    stage(report, "Démarrage automatique", startup)
    stage(report, "Processus et ports", processes)
    stage(report, "Antivirus et blocages récents", antivirus)
    stage(report, "Services locaux", lambda: {n: probe_service(n) for n in KNOWN_PORTS})
    stage(report, "Attendus et manquants", lambda: expected_services(report))
    stage(report, "Inventaire IA", lambda: ai_inventory(report))
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (REPORTS / f"rapport_demarrage_{stamp}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    text = report_text(report)
    (REPORTS / f"rapport_demarrage_{stamp}.txt").write_text(text, encoding="utf-8")
    (REPORTS / "rapport_demarrage_dernier.txt").write_text(text, encoding="utf-8")
    return report


def append_studio(event: dict) -> None:
    STUDIO_LOGS.mkdir(parents=True, exist_ok=True)
    path = STUDIO_LOGS / "journal.jsonl"
    if path.exists() and path.stat().st_size > 8_000_000:
        old = STUDIO_LOGS / "journal_precedent.jsonl"
        old.unlink(missing_ok=True)
        path.replace(old)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"date": now(), **event}, ensure_ascii=False) + "\n")


def _latest_image(job_id: str) -> str | None:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", job_id)[:90]
    if not safe:
        return None
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8191/api/media/{safe}/0", timeout=3) as r:
            kind = r.headers.get("Content-Type", "").split(";")[0]
            if kind not in ("image/png", "image/jpeg", "image/webp"):
                return None
            payload = r.read(500_001)
            if len(payload) > 500_000:
                return None
            thumbnails = STUDIO_LOGS / "vignettes"
            thumbnails.mkdir(parents=True, exist_ok=True)
            suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[kind]
            file = thumbnails / (safe + suffix)
            file.write_bytes(payload)
            return str(file)
    except Exception:
        return None


def _video_thumbnail(prompt_id: str, job_id: str) -> str | None:
    """Extract one local still if an existing ffmpeg can read a completed ComfyUI output."""
    ffmpeg = shutil.which("ffmpeg") or str(STUDIO / "bin" / "ffmpeg.exe")
    if not Path(ffmpeg).is_file():
        return None
    try:
        history = local_json(8188, "/history/" + urllib.parse.quote(prompt_id, safe=""))
        entry = history.get(prompt_id, {}) if isinstance(history, dict) else {}
        output_root = (COMFY / "output").resolve()
        for output in entry.get("outputs", {}).values():
            if not isinstance(output, dict):
                continue
            for kind in ("videos", "gifs"):
                for item in output.get(kind, []):
                    if not isinstance(item, dict):
                        continue
                    candidate = (output_root / str(item.get("subfolder", "")) / str(item.get("filename", ""))).resolve()
                    if not candidate.is_relative_to(output_root) or candidate.suffix.lower() not in (".mp4", ".webm", ".mov") or not candidate.is_file():
                        continue
                    thumbs = STUDIO_LOGS / "vignettes"
                    thumbs.mkdir(parents=True, exist_ok=True)
                    target = thumbs / (re.sub(r"[^A-Za-z0-9_-]", "", job_id)[:90] + ".png")
                    rc, _ = run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-ss", "00:00:01",
                                 "-i", str(candidate), "-frames:v", "1", "-vf", "scale=320:-1", str(target)], timeout=12)
                    if rc == 0 and target.is_file() and target.stat().st_size > 0:
                        return str(target)
        return None
    except Exception:
        return None


def existing_studio_errors(seen: dict) -> list[dict]:
    found = []
    for root in (STUDIO / "logs", COMFY / "user"):
        try:
            files = sorted((p for p in root.glob("*.log") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
            if root == STUDIO / "logs":
                files += sorted((p for p in root.glob("*.txt") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:2]
            for file in files:
                with file.open("rb") as fh:
                    fh.seek(max(0, file.stat().st_size - 16_000))
                    lines = fh.read().decode("utf-8", "replace").splitlines()
                errors = [clean(line, 650) for line in lines if ERROR.search(line)]
                if errors and seen.get("file_" + str(file)) != errors[-1]:
                    found.append({"source": "Fichier console Studio/ComfyUI", "fichier": str(file), "erreur": errors[-1]})
                    seen["file_" + str(file)] = errors[-1]
        except OSError:
            continue
    return found


def poll_studio(seen: dict) -> list[dict]:
    events: list[dict] = []
    try:
        rows = local_json(8191, "/api/jobs")
        if isinstance(rows, dict):
            rows = next((rows[k] for k in ("jobs", "items", "results") if isinstance(rows.get(k), list)), [])
        if isinstance(rows, list):
            for job in rows[-20:]:
                if not isinstance(job, dict):
                    continue
                job_id = clean(job.get("id") or job.get("job_id"), 90)
                if not job_id:
                    continue
                state = clean(job.get("status") or job.get("state"), 100)
                detail = clean(job.get("error") or job.get("message"), 500)
                key = job_id + "|" + state + "|" + detail
                if seen.get(job_id) == key:
                    continue
                seen[job_id] = key
                params = job.get("params") if isinstance(job.get("params"), dict) else {}
                video_fields = ("mode", "model", "workflow", "width", "height", "frames", "fps",
                                "steps", "cfg", "seed", "duration", "negative_prompt")
                settings = {field: clean(params[field], 250) for field in video_fields if field in params}
                finished = bool(re.search(r"complete|success|done|finish", state, re.I))
                thumb = _latest_image(job_id) if finished else None
                prompt_id = str(job.get("prompt_id") or "")
                if not thumb and finished and prompt_id:
                    thumb = _video_thumbnail(prompt_id, job_id)
                events.append({"source": "Studio /api/jobs", "job": job_id, "état": state,
                               "prompt_id": clean(prompt_id, 100),
                               "prompt": clean(params.get("prompt") or job.get("prompt"), 1200),
                               "réglages_vidéo": settings,
                               "erreur": detail if ERROR.search(state + detail) else "",
                               "vignette": thumb or "indisponible pour ce média"})
    except Exception as exc:
        if seen.get("offline") != type(exc).__name__:
            events.append({"source": "Studio", "état": "API indisponible", "erreur": type(exc).__name__})
            seen["offline"] = type(exc).__name__
    else:
        seen.pop("offline", None)
    try:
        try:
            logs = local_json(8191, "/api/log")
        except ValueError:
            with urllib.request.urlopen("http://127.0.0.1:8191/api/log", timeout=2.5) as response:
                logs = response.read(128_000).decode("utf-8-sig", "replace")
        raw = json.dumps(logs, ensure_ascii=False) if not isinstance(logs, str) else logs
        for line in raw.splitlines()[-100:]:
            if ERROR.search(line):
                line = clean(line, 700)
                if seen.get("ui_log") != line:
                    events.append({"source": "Studio /api/log", "erreur": line})
                    seen["ui_log"] = line
    except Exception:
        pass
    events.extend(existing_studio_errors(seen))
    try:
        history = local_json(8188, "/history?max_items=5")
        if isinstance(history, dict):
            for prompt_id, item in history.items():
                status = item.get("status", {}) if isinstance(item, dict) else {}
                if not isinstance(status, dict):
                    continue
                errors = [x for x in status.get("messages", []) if isinstance(x, list) and x and x[0] == "execution_error"]
                if errors and seen.get("comfy_" + prompt_id) != len(errors):
                    event = {"source": "ComfyUI /history", "prompt_id": clean(prompt_id, 100),
                             "erreur": clean(errors[-1][1], 700)}
                    events.append(event)
                    seen["comfy_" + prompt_id] = len(errors)
    except Exception:
        pass
    if len(seen) > 1500:
        seen.clear()
    return events


def existing_observer_feed(seen: dict) -> list[dict] | None:
    """Reuse the dedicated Studio observer if another BAZOR supervisor already runs it."""
    file = STUDIO_LOGS / "latest.json"
    try:
        if time.time() - file.stat().st_mtime > 75:
            return None
        data = json.loads(file.read_text(encoding="utf-8"))
        jobs = data.get("jobs", [])
        events = []
        if isinstance(jobs, list) and jobs:
            job = jobs[-1]
            if isinstance(job, dict):
                key = str(job.get("id")) + "|" + str(job.get("state")) + "|" + str(job.get("error")) + "|" + str(data.get("latest_thumbnail"))
                if seen.get("observer_job") != key:
                    seen["observer_job"] = key
                    events.append({"source": "Observateur Studio", "job": clean(job.get("id"), 90),
                                   "état": clean(job.get("state"), 90),
                                   "prompt": clean(job.get("prompt_preview"), 180),
                                   "erreur": clean(job.get("error"), 500),
                                   "vignette": clean(data.get("latest_thumbnail"), 500),
                                   "réglages_vidéo": {k: job.get(k) for k in ("mode", "width", "height", "frames", "steps", "seed")}})
        errors = data.get("console_errors", [])
        if isinstance(errors, list) and errors:
            last = errors[-1]
            if isinstance(last, dict):
                message = clean(last.get("message"), 500)
                if message and seen.get("observer_error") != message:
                    seen["observer_error"] = message
                    events.append({"source": "Observateur Studio / logs", "erreur": message})
        return events
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def install() -> int:
    if os.name != "nt":
        print("Installation uniquement sous Windows.")
        return 2
    import winreg
    if run(["schtasks", "/Query", "/TN", r"BAZOR\BilanDemarrage", "/FO", "LIST"], timeout=5)[0] == 0:
        print("Un bilan BAZOR au démarrage est déjà programmé ; aucune deuxième veille ajoutée.")
        return 2
    if not ((LOCAL / "BAZOR" / "Core").exists() or (LOCAL / "BazorAIROOM").exists() or (Path.home() / "bazor-mobile").exists()):
        print("Installation BAZOR non trouvée aux emplacements connus. Aucune modification.")
        return 2
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        print("pythonw.exe introuvable. Aucune entrée de démarrage ajoutée.")
        return 2
    ROOT.mkdir(parents=True, exist_ok=True)
    dest = ROOT / "bazor_boot_watch.pyw"
    command = f'"{pythonw}" "{dest}" --watch'
    already_registered = False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            existing, _ = winreg.QueryValueEx(key, APP)
        if existing != command:
            print("Une autre entrée BAZOR Veille existe ; aucune entrée remplacée.")
            return 2
        already_registered = True
    except FileNotFoundError:
        pass
    except OSError as exc:
        print("Entrée de démarrage illisible : " + type(exc).__name__)
        return 2
    if dest.is_file() and already_registered:
        SHOW_FLAG.write_text(now(), encoding="utf-8")
        print(f"BAZOR Veille déjà installée. Rapport dans {REPORTS}.")
        return 0
    shutil.copy2(Path(__file__).resolve(), dest)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, APP, 0, winreg.REG_SZ, command)
    STOP_FLAG.unlink(missing_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([str(pythonw), str(dest), "--watch"], creationflags=CREATE_NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"BAZOR Veille installée au démarrage de session. Rapport dans {REPORTS}.")
    return 0


def uninstall() -> int:
    if os.name != "nt":
        print("Désinstallation uniquement sous Windows.")
        return 2
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            value, _ = winreg.QueryValueEx(key, APP)
            if str(ROOT / "bazor_boot_watch.pyw").lower() not in str(value).lower():
                print("Entrée différente détectée ; aucune suppression.")
                return 2
            winreg.DeleteValue(key, APP)
    except FileNotFoundError:
        pass
    STOP_FLAG.parent.mkdir(parents=True, exist_ok=True)
    STOP_FLAG.write_text(now(), encoding="utf-8")
    print("Démarrage retiré. La veille en cours s'arrête ; rapports conservés dans Documents.")
    return 0


def singleton():
    ROOT.mkdir(parents=True, exist_ok=True)
    fh = (ROOT / "veille.lock").open("a+b")
    fh.seek(0)
    fh.write(b"0")
    fh.flush()
    fh.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None


def watch(show_ui: bool = True) -> int:
    lock = singleton()
    if lock is None:
        SHOW_FLAG.write_text(now(), encoding="utf-8")
        return 0
    messages: queue.Queue = queue.Queue()
    latest: dict = {"date": now(), "Services locaux": {}}
    latest_job: dict = {}

    def worker():
        nonlocal latest, latest_job
        try:
            latest = audit()
            messages.put("Rapport de démarrage prêt dans Documents/BAZOR.")
        except Exception as exc:
            append_studio({"source": "Veille", "erreur": "Rapport impossible : " + clean(exc)})
            messages.put("Rapport impossible : " + type(exc).__name__)
        seen: dict = {}
        previous = None
        while True:
            if STOP_FLAG.exists():
                return
            try:
                observer_events = existing_observer_feed(seen)
                for event in (observer_events if observer_events is not None else poll_studio(seen)):
                    if observer_events is None:
                        append_studio(event)
                    if event.get("job"):
                        latest_job = event
                    messages.put(f"Studio : {event.get('état') or event.get('erreur') or 'nouvelle activité'}")
                status = {n: probe_service(n)["état"] for n in KNOWN_PORTS}
                if status != previous:
                    append_studio({"source": "Services", "états": status})
                    messages.put("Services : " + ", ".join(f"{k} {v}" for k, v in status.items()))
                    previous = status
            except Exception as exc:
                append_studio({"source": "Veille", "erreur": type(exc).__name__ + ": " + clean(exc)})
            time.sleep(30)

    threading.Thread(target=worker, daemon=True).start()
    if not show_ui:
        while not STOP_FLAG.exists():
            time.sleep(5)
        STOP_FLAG.unlink(missing_ok=True)
        return 0
    try:
        import tkinter as tk
        from tkinter import ttk
        window = tk.Tk()
        window.title("BAZOR — veille des projets")
        window.geometry("720x570")
        window.minsize(540, 410)
        main = ttk.Frame(window, padding=15)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="BAZOR · démarrage et Studio", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(main, text="Le rapport est local. Les erreurs d'un contrôle n'arrêtent pas les suivants.").pack(anchor="w", pady=(3, 10))
        services_view = ttk.Treeview(main, columns=("etat", "decision"), show="headings", height=5)
        services_view.heading("etat", text="Projet / service")
        services_view.heading("decision", text="Décision")
        services_view.column("etat", width=370, stretch=True)
        services_view.column("decision", width=220, stretch=True)
        services_view.pack(fill="x", pady=(0, 10))
        preview_row = ttk.Frame(main)
        preview_row.pack(fill="x", pady=(0, 8))
        preview_image = ttk.Label(preview_row)
        preview_image.pack(side="left", padx=(0, 10))
        preview_text = tk.StringVar(value="Studio : aucune nouvelle tâche observée depuis l'ouverture.")
        ttk.Label(preview_row, textvariable=preview_text, wraplength=490).pack(side="left", fill="x", expand=True)
        shown_job = ""
        box = tk.Text(main, height=10, wrap="word", state="disabled", font=("Consolas", 9))
        box.pack(fill="both", expand=True)
        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(11, 0))
        ttk.Button(buttons, text="Lire le rapport", command=lambda: os.startfile(REPORTS / "rapport_demarrage_dernier.txt") if (REPORTS / "rapport_demarrage_dernier.txt").exists() else None).pack(side="left", padx=(0, 7))
        ttk.Button(buttons, text="Journal Studio", command=lambda: os.startfile(STUDIO_LOGS) if STUDIO_LOGS.exists() else None).pack(side="left", padx=(0, 7))
        ttk.Button(buttons, text="Ouvrir Studio", command=lambda: webbrowser.open("http://127.0.0.1:8191/")).pack(side="left", padx=(0, 7))
        ttk.Button(buttons, text="Ouvrir Sabrina", command=lambda: webbrowser.open("https://reperes-sabrina.vgouriou.chatgpt.site/#simulation")).pack(side="right")

        def tick():
            nonlocal shown_job
            if STOP_FLAG.exists():
                STOP_FLAG.unlink(missing_ok=True)
                window.destroy()
                return
            if SHOW_FLAG.exists():
                SHOW_FLAG.unlink(missing_ok=True)
                window.deiconify()
                window.lift()
            while not messages.empty():
                msg = messages.get_nowait()
                box.configure(state="normal")
                box.insert("end", now()[11:19] + "  " + clean(msg, 300) + "\n")
                box.see("end")
                box.configure(state="disabled")
            services_view.delete(*services_view.get_children())
            for name, port in KNOWN_PORTS.items():
                entry = latest.get("Services locaux", {}).get(name, {})
                state = entry.get("état", "contrôle en cours")
                decision = "à garder pour BAZOR" if name in ("Core", "Room", "Ollama") else "à garder si création en cours"
                services_view.insert("", "end", values=(f"{name} · {port} : {state}", decision))
            job = latest_job
            identity = str(job.get("job", "")) + "|" + str(job.get("état", ""))
            if job and identity != shown_job:
                shown_job = identity
                preview_text.set(f"Studio · {job.get('état', 'état inconnu')} · {clean(job.get('prompt'), 180) or 'prompt non disponible'}")
                path = str(job.get("vignette") or "")
                if path.lower().endswith(".png") and Path(path).is_file():
                    try:
                        photo = tk.PhotoImage(file=path)
                        photo = photo.subsample(max(1, (photo.width() + 125) // 126))
                        preview_image.configure(image=photo)
                        preview_image.image = photo
                    except tk.TclError:
                        pass
                elif path.lower().endswith((".jpg", ".jpeg", ".webp")) and Path(path).is_file():
                    try:
                        from PIL import Image, ImageTk
                        with Image.open(path) as source:
                            source.thumbnail((126, 126))
                            photo = ImageTk.PhotoImage(source.copy())
                        preview_image.configure(image=photo)
                        preview_image.image = photo
                    except (ImportError, OSError, ValueError, tk.TclError):
                        pass
            window.after(1000, tick)
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        tick()
        window.mainloop()
    except Exception as exc:
        append_studio({"source": "Fenêtre", "erreur": type(exc).__name__ + ": " + clean(exc)})
        while not STOP_FLAG.exists():
            time.sleep(5)
        STOP_FLAG.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.install:
        raise SystemExit(install())
    if args.uninstall:
        raise SystemExit(uninstall())
    if args.show:
        SHOW_FLAG.parent.mkdir(parents=True, exist_ok=True)
        SHOW_FLAG.write_text(now(), encoding="utf-8")
        raise SystemExit(0)
    if args.once:
        print(report_text(audit()))
        raise SystemExit(0)
    raise SystemExit(watch())
