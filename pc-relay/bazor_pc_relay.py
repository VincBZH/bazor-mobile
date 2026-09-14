import base64
import datetime
import hashlib
import ipaddress
import json
import os
import platform
import re
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UDP_PORT = 8766
API_PORT = 8765
MAGIC = b"BAZOR_DISCOVER_V1"
OLLAMA_URL = "http://127.0.0.1:11434"
hostname = platform.node() or "BAZOR-PC"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "BAZOR_DATA"
FILES_DIR = DATA_DIR / "ROOM_FILES"
JOURNAL_FILE = DATA_DIR / "journal.jsonl"
MAX_FILE_BYTES = 8 * 1024 * 1024
FILES_DIR.mkdir(parents=True, exist_ok=True)


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")

def safe_name(name):
    name = os.path.basename(str(name or "fichier.bin")).strip() or "fichier.bin"
    name = re.sub(r"[^A-Za-z0-9._() -]+", "_", name)
    return name[:180]


def journal(event, details):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    row = {"time": now_iso(), "event": event, **details}
    with JOURNAL_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def store_file(name, room, mime, b64data):
    try:
        raw = base64.b64decode(b64data, validate=True)
    except Exception:
        return {"ok": False, "error": "invalid_base64"}
    if len(raw) > MAX_FILE_BYTES:
        return {"ok": False, "error": "file_too_large", "max_bytes": MAX_FILE_BYTES}

    digest = hashlib.sha256(raw).hexdigest()
    clean = safe_name(name)
    room_clean = safe_name(room or "ROOM PRINCIPALE").replace(" ", "_")
    room_dir = FILES_DIR / room_clean
    room_dir.mkdir(parents=True, exist_ok=True)
    stored = room_dir / f"{digest[:12]}_{clean}"

    duplicate = stored.exists()
    if not duplicate:
        stored.write_bytes(raw)

    meta = {
        "id": digest,
        "name": clean,
        "stored_name": stored.name,
        "room": room or "ROOM PRINCIPALE",
        "mime": mime or "application/octet-stream",
        "size": len(raw),
        "sha256": digest,
        "duplicate": duplicate,
        "path": str(stored)
    }
    journal("FILE_UPLOAD", {k: v for k, v in meta.items() if k != "path"})
    return {"ok": True, "file": meta}


def list_files(room=None):
    items = []
    roots = [FILES_DIR]
    for path in FILES_DIR.rglob("*"):
        if not path.is_file():
            continue
        if room and path.parent.name != safe_name(room).replace(" ", "_"):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        items.append({
            "stored_name": path.name,
            "room": path.parent.name,
            "size": size
        })
    items.sort(key=lambda x: x["stored_name"].lower())
    return items


def is_local_client(host):
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False


def ollama_tags():
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=1.2) as response:
            data = json.loads(response.read().decode("utf-8"))
        return True, [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return False, []

def pick_local_model(text, models):
    lower = (text or "").lower()
    code_words = ("code", "python", "javascript", "java", "bug", "github", "api", "script", "cmd", "powershell", "apk", "gradle", "html", "css", "fonction", "débog", "debug")
    light_words = ("résume", "resume", "reformule", "classe", "liste", "titre", "court", "simple", "rapide")
    preferred = []
    if any(w in lower for w in code_words):
        preferred = ["qwen2.5-coder:7b", "qwen2.5-coder", "mistral:latest", "mistral"]
        kind = "code"
    elif any(w in lower for w in light_words):
        preferred = ["gemma3:4b", "gemma3", "mistral:latest", "mistral"]
        kind = "light"
    else:
        preferred = ["mistral:latest", "mistral", "qwen2.5-coder:7b", "gemma3:4b"]
        kind = "general"

    for wanted in preferred:
        for installed in models:
            if installed == wanted or installed.startswith(wanted + ":"):
                return installed, kind
    return (models[0] if models else None), kind


def route_task(text):
    online, models = ollama_tags()
    model, kind = pick_local_model(text, models)
    # ECO CREDITS: never spend GPT automatically.
    return {
        "target": "ollama" if online and model else "gpt_manual",
        "model": model,
        "kind": kind,
        "reason": "local_first",
        "gpt_auto": False,
        "ollama_online": online,
        "models": models
    }


def ollama_chat(text, model=None):
    online, models = ollama_tags()
    if not online:
        return {"ok": False, "error": "ollama_offline", "message": "Ollama ne répond pas sur le PC."}
    selected = model if model in models else (models[0] if models else None)
    if not selected:
        return {"ok": False, "error": "no_model", "message": "Aucun modèle Ollama installé."}

    payload = json.dumps({
        "model": selected,
        "messages": [{"role": "user", "content": text}],
        "stream": False
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
        answer = ((data.get("message") or {}).get("content") or "").strip()
        return {"ok": True, "model": selected, "answer": answer}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "ollama_http", "message": f"Ollama HTTP {exc.code}"}
    except Exception as exc:
        return {"ok": False, "error": "ollama_error", "message": str(exc)[:240]}


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "BAZOR-API/1.0"

    def log_message(self, fmt, *args):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] API {self.client_address[0]} - " + (fmt % args))

    def _headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _json(self, data, status=200):
        self._headers(status)
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _allowed(self):
        if is_local_client(self.client_address[0]):
            return True
        self._json({"ok": False, "error": "local_network_only"}, 403)
        return False

    def do_OPTIONS(self):
        self._headers(204)

    def do_GET(self):
        if not self._allowed():
            return
        if self.path in ("/", "/api", "/api/v1", "/api/v1/health"):
            online, models = ollama_tags()
            self._json({
                "ok": True,
                "service": "BAZOR API",
                "version": "1.0",
                "pc": hostname,
                "time": now_iso(),
                "ollama": {"online": online, "models": models},
                "capabilities": ["health", "models", "ollama_chat", "routing", "eco_credits", "file_upload", "file_list"],
                "security": {
                    "scope": "local-network",
                    "ollama_exposed": False,
                    "shell_commands": False
                }
            })
            return
        if self.path == "/api/v1/route":
            self._json({"ok": True, "usage": "POST /api/v1/route with text"})
            return
        if self.path.startswith("/api/v1/files"):
            room = None
            if "?room=" in self.path:
                from urllib.parse import unquote
                room = unquote(self.path.split("?room=", 1)[1].split("&", 1)[0])
            self._json({"ok": True, "files": list_files(room)})
            return
        if self.path == "/api/v1/models":
            online, models = ollama_tags()
            self._json({"ok": True, "ollama_online": online, "models": models})
            return
        self._json({"ok": False, "error": "not_found"}, 404)

    def do_POST(self):
        if not self._allowed():
            return
        length = min(int(self.headers.get("Content-Length", "0") or "0"), 12 * 1024 * 1024)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except Exception:
            self._json({"ok": False, "error": "invalid_json"}, 400)
            return

        if self.path == "/api/v1/files/upload":
            name = body.get("name")
            room = body.get("room") or "ROOM PRINCIPALE"
            mime = body.get("mime")
            data = body.get("data")
            if not name or not data:
                self._json({"ok": False, "error": "missing_file_data"}, 400)
                return
            result = store_file(name, room, mime, data)
            self._json(result, 200 if result.get("ok") else 400)
            return

        if self.path == "/api/v1/route":
            text = str(body.get("text", "")).strip()
            if not text:
                self._json({"ok": False, "error": "empty_message"}, 400)
                return
            self._json({"ok": True, "route": route_task(text)})
            return

        if self.path == "/api/v1/chat":
            text = str(body.get("text", "")).strip()
            target = str(body.get("target", "auto")).lower()
            model = body.get("model")
            if not text:
                self._json({"ok": False, "error": "empty_message"}, 400)
                return

            route_info = None
            if target == "auto":
                route_info = route_task(text)
                if route_info["target"] == "ollama":
                    target = "ollama"
                    model = route_info["model"]
                else:
                    self._json({
                        "ok": False,
                        "error": "gpt_manual_required",
                        "message": "Aucun modèle local disponible. GPT n'est jamais dépensé automatiquement en mode ECO.",
                        "route": route_info
                    }, 503)
                    return

            result = {
                "ok": True,
                "target": target,
                "pc": hostname,
                "time": now_iso(),
                "gpt": None,
                "ollama": None,
                "route": route_info,
                "eco_credits": True
            }

            if target in ("ollama", "both"):
                result["ollama"] = ollama_chat(text, model)

            if target in ("gpt", "both"):
                result["gpt"] = {
                    "ok": False,
                    "error": "gpt_connector_not_configured",
                    "message": "Le connecteur GPT n'est pas encore configuré dans BAZOR API."
                }

            if target not in ("gpt", "ollama", "both"):
                self._json({"ok": False, "error": "invalid_target"}, 400)
                return

            self._json(result)
            return

        self._json({"ok": False, "error": "not_found"}, 404)


def run_api():
    server = ThreadingHTTPServer(("0.0.0.0", API_PORT), ApiHandler)
    print(f"API      : http://0.0.0.0:{API_PORT}/api/v1/health")
    server.serve_forever()


def run_udp_discovery():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", UDP_PORT))
    print(f"UDP      : {UDP_PORT}")
    while True:
        data, addr = sock.recvfrom(512)
        if data.strip() == MAGIC and is_local_client(addr[0]):
            reply = f"BAZOR_PC_OK|{hostname}|{API_PORT}".encode("utf-8")
            sock.sendto(reply, addr)
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] BAZOR Mobile détecté depuis {addr[0]}")


print("=" * 62)
print(" BAZOR PC RELAY + BAZOR API v1.0")
print("=" * 62)
print(f"PC       : {hostname}")
print("Etat     : EN LIGNE")
print("Ollama   : LOCAL UNIQUEMENT - jamais exposé directement")
print("Sécurité : réseau local uniquement, aucune commande shell")
print(f"Fichiers : {FILES_DIR} (max {MAX_FILE_BYTES // (1024*1024)} Mo/fichier)")
print("Fermer cette fenêtre pour arrêter BAZOR API.")
print("=" * 62)

threading.Thread(target=run_udp_discovery, daemon=True).start()
run_api()
