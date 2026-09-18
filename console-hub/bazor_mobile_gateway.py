import json
import os
import sys
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = "http://127.0.0.1:8775"
PORT = 8776

FORWARD_HEADERS = {
    "content-type",
    "x-bazor-device",
    "x-bazor-nonce",
    "x-bazor-proof",
}

class Gateway(SimpleHTTPRequestHandler):
    server_version = "BAZOR-Mobile-Gateway/1.0"

    def log_message(self, fmt, *args):
        sys.stdout.write(f"[WEB] {self.client_address[0]} - " + (fmt % args) + "\n")
        sys.stdout.flush()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _proxy(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else None
        headers = {}
        for k, v in self.headers.items():
            if k.lower() in FORWARD_HEADERS:
                headers[k] = v
        req = urllib.request.Request(
            CORE + self.path,
            data=body,
            headers=headers,
            method=self.command,
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
                status = getattr(r, "status", 200)
                ctype = r.headers.get("Content-Type", "application/json; charset=utf-8")
        except urllib.error.HTTPError as e:
            data = e.read()
            status = e.code
            ctype = e.headers.get("Content-Type", "application/json; charset=utf-8")
        except Exception as e:
            payload = json.dumps({
                "ok": False,
                "error": "core_gateway_unreachable",
                "detail": type(e).__name__,
            }).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        self.send_error(405, "POST only allowed for /api/")

    def do_OPTIONS(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        self.send_response(204)
        self.end_headers()

if __name__ == "__main__":
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Gateway)
    print(f"BAZOR Mobile Gateway : http://0.0.0.0:{PORT}/ -> Core {CORE}", flush=True)
    server.serve_forever()
