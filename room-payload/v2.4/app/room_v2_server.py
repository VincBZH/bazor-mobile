from __future__ import annotations
import json
import os
import threading
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
STATE_FILE = ROOT.parent / "state.json"
PROJECTS_FILE = ROOT.parent / "projects.json"

def _read_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _health_url(url: str, timeout: float = 1.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return {"available": 200 <= getattr(r, "status", 500) < 500, "status": getattr(r, "status", None)}
    except Exception as e:
        return {"available": False, "error": str(e)}

def engine_status():
    ollama = _health_url(os.getenv("BAZOR_OLLAMA_HEALTH_URL", "http://127.0.0.1:11434/api/tags"))
    mammouth_url = os.getenv("BAZOR_MAMMOUTH_HEALTH_URL", "")
    mammouth = _health_url(mammouth_url) if mammouth_url else {"available": None, "reason": "health_url_not_configured"}
    gpt_mode = os.getenv("BAZOR_GPT_MODE", "relay")
    gpt = {"available": None, "mode": gpt_mode, "reason": "relay_status_not_configured"}
    return {"gpt": gpt, "mammouth": mammouth, "ollama": ollama}

def choose_route(task_class: str, manual: str | None = None):
    engines = engine_status()
    if manual in {"gpt","mammouth","ollama"}:
        return {"mode":"manual","selected":manual,"engines":engines}

    if task_class in {"simple","local"} and engines["ollama"].get("available") is True:
        selected = "ollama"
    elif task_class in {"architecture","synthesis","arbitration"} and engines["gpt"].get("available") is not False:
        selected = "gpt"
    elif task_class in {"complex","second_opinion"} and engines["mammouth"].get("available") is not False:
        selected = "mammouth"
    elif engines["gpt"].get("available") is True:
        selected = "gpt"
    elif engines["mammouth"].get("available") is True:
        selected = "mammouth"
    elif engines["ollama"].get("available") is True:
        selected = "ollama"
    else:
        selected = None
    return {"mode":"auto","selected":selected,"engines":engines}

class Handler(BaseHTTPRequestHandler):
    server_version = "BAZORRoomV2/2.4"

    def _json(self, data: Any, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?",1)[0]
        if path == "/":
            return self._file(STATIC / "index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self._file(STATIC / "app.js", "application/javascript; charset=utf-8")
        if path == "/style.css":
            return self._file(STATIC / "style.css", "text/css; charset=utf-8")
        if path == "/api/status":
            state = _read_json(STATE_FILE, {})
            return self._json({
                "ok": True,
                "version": "2.4-lite",
                "state": state,
                "engines": engine_status()
            })
        if path == "/api/projects":
            return self._json(_read_json(PROJECTS_FILE, {"projects":[]}))
        return self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length","0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return self._json({"ok":False,"error":"invalid_json"},400)

        if self.path == "/api/route":
            task_class = str(data.get("task_class","simple"))
            manual = data.get("manual")
            return self._json({"ok":True, **choose_route(task_class, manual)})
        return self._json({"ok":False,"error":"not_found"},404)

    def log_message(self, fmt, *args):
        print("[ROOM]", self.address_string(), fmt % args)

def main():
    host = os.getenv("BAZOR_ROOM_HOST", "127.0.0.1")
    port = int(os.getenv("BAZOR_ROOM_PORT", "8765"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"BAZOR AI ROOM V2.4 listening on http://{host}:{port}/")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
