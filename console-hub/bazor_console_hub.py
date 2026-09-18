import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "pc-relay" / "BAZOR_DATA"
LOG_DIR = DATA / "HUB_LOGS"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = DATA / "console_hub_state.json"
MOBILE_STATE = DATA / "mobile_state.json"
LOCK_PORT = 8790

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

SERVICES = [
    {
        "id": "core", "project": "BAZOR Mobile", "name": "Core 8775",
        "match": "bazor_pc_relay_v3.py", "port": 8775,
        "health": "http://127.0.0.1:8775/api/v1/security/status",
        "command": [sys.executable, str(ROOT / "pc-relay" / "bazor_pc_relay_v3.py")],
        "cwd": str(ROOT / "pc-relay"), "managed": True,
    },
    {
        "id": "web", "project": "BAZOR Mobile", "name": "Web 8776",
        "match": "http.server 8776", "port": 8776,
        "health": "http://127.0.0.1:8776/index.html",
        "command": [sys.executable, "-m", "http.server", "8776", "--bind", "0.0.0.0"],
        "cwd": str(ROOT), "managed": True,
    },
    {
        "id": "watcher", "project": "BAZOR Mobile", "name": "GitHub Watcher",
        "match": "bazor_github_watcher.py", "port": None, "health": None,
        "command": [sys.executable, str(ROOT / "pc-relay" / "bazor_github_watcher.py")],
        "cwd": str(ROOT), "managed": True,
    },
    {
        "id": "ai-room", "project": "BAZOR AI Room", "name": "AI Room 8765",
        "match": "BazorAIROOM", "port": 8765, "health": "http://127.0.0.1:8765/",
        "managed": False,
    },
    {
        "id": "comfy", "project": "AI Simple Studio", "name": "ComfyUI 8188",
        "match": "ComfyUI", "port": 8188, "health": "http://127.0.0.1:8188/",
        "managed": False,
    },
    {
        "id": "studio", "project": "AI Simple Studio", "name": "Studio 8191",
        "match": "SimpleStudio", "port": 8191, "health": "http://127.0.0.1:8191/",
        "managed": False,
    },
    {
        "id": "wii", "project": "Projet Wii AI Relay", "name": "Wii Bridge",
        "match": "Wii_AI_Bridge", "port": None, "health": None,
        "managed": False,
    },
]

STATUS_ORDER = {"ERROR": 0, "DUPLICATE": 1, "WORK": 2, "OK": 3, "CLOSED": 4, "EXTERNAL": 5}
STATUS_UI = {
    "OK": ("● OK", "ok"),
    "WORK": ("● EN COURS", "work"),
    "ERROR": ("● ERREUR", "error"),
    "DUPLICATE": ("● DOUBLON À FERMER", "error"),
    "CLOSED": ("✖ FERMÉ", "closed"),
    "EXTERNAL": ("● DÉTECTÉ", "external"),
}

def powershell_processes():
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
        "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8)
        if p.returncode != 0 or not p.stdout.strip():
            return []
        data = json.loads(p.stdout)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []

def port_open(port):
    if not port:
        return False
    s = socket.socket()
    s.settimeout(0.35)
    try:
        return s.connect_ex(("127.0.0.1", int(port))) == 0
    finally:
        s.close()

def http_ok(url):
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=0.75) as r:
            return 200 <= getattr(r, "status", 200) < 500
    except Exception:
        return False

def tail(path, lines=80):
    try:
        p = Path(path)
        if not p.exists():
            return ""
        return "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except Exception:
        return ""

def mobile_working():
    try:
        data = json.loads(MOBILE_STATE.read_text(encoding="utf-8"))
        client = data.get("client_state") or {}
        runs = client.get("runs") or {}
        return any(bool(v.get("active")) for v in runs.values() if isinstance(v, dict))
    except Exception:
        return False

class Hub:
    def __init__(self, centralize=False):
        self.centralize_requested = centralize
        self.root = tk.Tk()
        self.root.title("BAZOR Console Hub")
        self.root.geometry("1040x680")
        self.root.minsize(850, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.stop_evt = threading.Event()
        self.proc_cache = []
        self.rows = {}
        self.selected_id = None
        self.security_code = ""
        self.lock_socket = socket.socket()
        try:
            self.lock_socket.bind(("127.0.0.1", LOCK_PORT))
            self.lock_socket.listen(1)
        except OSError:
            messagebox.showinfo("BAZOR Console Hub", "BAZOR Console Hub est déjà ouvert.")
            self.root.destroy()
            raise SystemExit(0)
        self.build_ui()
        if centralize:
            self.root.after(700, self.centralize)
        self.root.after(1000, self.refresh)
        self.root.after(1400, self.refresh_logs)

    def build_ui(self):
        top = tk.Frame(self.root, bg="#11151b", padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="BAZOR CONSOLE HUB", fg="white", bg="#11151b", font=("Segoe UI", 18, "bold")).pack(side="left")
        self.summary = tk.Label(top, text="Analyse…", fg="#aeb8c5", bg="#11151b", font=("Segoe UI", 10))
        self.summary.pack(side="left", padx=16)
        self.code_label = tk.Label(top, text="", fg="black", bg="#f6d04d", font=("Consolas", 13, "bold"), padx=10, pady=5)
        self.code_label.pack(side="right")
        self.code_label.pack_forget()

        bar = tk.Frame(self.root, padx=10, pady=8)
        bar.pack(fill="x")
        for text, cmd in [
            ("CENTRALISER BAZOR", self.centralize),
            ("ACTUALISER", self.refresh),
            ("VOIR LOG", self.open_log),
            ("DÉMARRER", self.start_selected),
            ("REDÉMARRER", self.restart_selected),
            ("FERMER", self.stop_selected),
            ("FERMER DOUBLONS", self.close_duplicates),
        ]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=3)

        cols = ("status", "project", "service", "pid", "detail")
        self.tree = ttk.Treeview(self.root, columns=cols, show="headings", height=13)
        for c, title, width in [
            ("status","ÉTAT",155),("project","PROJET",180),("service","SERVICE",180),("pid","PID",85),("detail","DÉTAIL",360)
        ]:
            self.tree.heading(c, text=title)
            self.tree.column(c, width=width, anchor="w")
        self.tree.tag_configure("ok", foreground="#198754")
        self.tree.tag_configure("work", foreground="#b77900")
        self.tree.tag_configure("error", foreground="#d93845")
        self.tree.tag_configure("closed", foreground="#b22222")
        self.tree.tag_configure("external", foreground="#4377a8")
        self.tree.pack(fill="both", expand=False, padx=10)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        lower = tk.PanedWindow(self.root, orient="horizontal", sashwidth=6)
        lower.pack(fill="both", expand=True, padx=10, pady=(8,10))
        left = tk.Frame(lower)
        right = tk.Frame(lower)
        lower.add(left, minsize=380)
        lower.add(right, minsize=350)

        tk.Label(left, text="LOG DU SERVICE", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log_text = tk.Text(left, bg="#0e1116", fg="#d7dde7", insertbackground="white", wrap="none", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        tk.Label(right, text="JOURNAL CENTRAL BAZOR", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.all_text = tk.Text(right, bg="#0e1116", fg="#d7dde7", insertbackground="white", wrap="none", font=("Consolas", 9))
        self.all_text.pack(fill="both", expand=True)

    def log_path(self, sid):
        return LOG_DIR / f"{sid}.log"

    def matching(self, service):
        pat = service.get("match","").lower()
        out = []
        for p in self.proc_cache:
            cl = str(p.get("CommandLine") or "")
            if pat and pat in cl.lower():
                out.append(p)
        return out

    def service_state(self, service):
        procs = self.matching(service)
        port = port_open(service.get("port")) if service.get("port") else None
        healthy = http_ok(service.get("health")) if service.get("health") else None
        detail = ""
        if len(procs) > 1:
            state = "DUPLICATE"
            detail = f"{len(procs)} instances reconnues — garder une seule"
        elif len(procs) == 1:
            state = "OK"
            if healthy is False and service.get("health"):
                state = "ERROR"
                detail = "Processus actif mais service ne répond pas"
            elif service["id"] == "core" and mobile_working():
                state = "WORK"
                detail = "Tâche BAZOR en cours"
            else:
                detail = "Processus actif" + (" • port OK" if port else "")
        else:
            if port:
                state = "EXTERNAL"
                detail = "Port actif mais processus non identifié"
            else:
                state = "CLOSED"
                detail = "Arrêté"
        log = tail(self.log_path(service["id"]), 35)
        if state in ("OK","WORK") and ("Traceback (most recent call last)" in log or "[BLOQUE]" in log):
            detail += " • ancien incident présent dans le log"
        return state, procs, detail

    def refresh(self):
        self.proc_cache = powershell_processes()
        counts = {"OK":0,"WORK":0,"ERROR":0,"DUPLICATE":0,"CLOSED":0,"EXTERNAL":0}
        for svc in SERVICES:
            state, procs, detail = self.service_state(svc)
            counts[state] += 1
            label, tag = STATUS_UI[state]
            pid = ",".join(str(p.get("ProcessId")) for p in procs[:3]) or "—"
            vals = (label, svc["project"], svc["name"], pid, detail)
            if svc["id"] in self.rows:
                self.tree.item(self.rows[svc["id"]], values=vals, tags=(tag,))
            else:
                self.rows[svc["id"]] = self.tree.insert("", "end", values=vals, tags=(tag,), iid=svc["id"])
        self.summary.config(text=f"{counts['OK']} OK · {counts['WORK']} en cours · {counts['ERROR']+counts['DUPLICATE']} à voir · {counts['CLOSED']} fermés")
        self.update_security_code()
        self.root.after(2500, self.refresh)

    def update_security_code(self):
        text = tail(self.log_path("core"), 120)
        matches = re.findall(r">>>\s*([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})\s*<<<", text)
        if not matches:
            matches = re.findall(r"Code appairage mobile:\s*([A-Z0-9-]{10,20})", text)
        code = matches[-1] if matches else ""
        if code and code != self.security_code:
            self.security_code = code
        if self.security_code:
            self.code_label.config(text="🔐 APPAIRAGE : " + self.security_code)
            self.code_label.pack(side="right")
        else:
            self.code_label.pack_forget()

    def on_select(self, _evt=None):
        sel = self.tree.selection()
        self.selected_id = sel[0] if sel else None
        self.refresh_logs()

    def refresh_logs(self):
        if self.selected_id:
            content = tail(self.log_path(self.selected_id), 250)
            self.log_text.delete("1.0","end")
            self.log_text.insert("end", content or "Pas de log central pour ce service.")
            self.log_text.see("end")
        combined = []
        for svc in SERVICES[:3]:
            txt = tail(self.log_path(svc["id"]), 45)
            if txt:
                combined.append(f"===== {svc['name']} =====\n{txt}")
        self.all_text.delete("1.0","end")
        self.all_text.insert("end", "\n\n".join(combined) or "Aucun log central pour l'instant.")
        self.all_text.see("end")
        self.root.after(3000, self.refresh_logs)

    def start_service(self, svc):
        if not svc.get("managed") or not svc.get("command"):
            return False
        log = open(self.log_path(svc["id"]), "a", encoding="utf-8", buffering=1)
        env = os.environ.copy()
        if svc["id"] == "core":
            env["BAZOR_MOBILE_PORT"] = "8775"
        subprocess.Popen(
            svc["command"], cwd=svc.get("cwd") or str(ROOT), env=env,
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        )
        return True

    def stop_service(self, svc, all_instances=True):
        procs = self.matching(svc)
        for p in procs if all_instances else procs[1:]:
            pid = int(p.get("ProcessId") or 0)
            if pid and pid != os.getpid():
                subprocess.run(["taskkill","/PID",str(pid),"/T","/F"], capture_output=True, creationflags=CREATE_NO_WINDOW)
        return len(procs)

    def selected_service(self):
        return next((s for s in SERVICES if s["id"] == self.selected_id), None)

    def start_selected(self):
        svc = self.selected_service()
        if not svc:
            return
        if self.matching(svc):
            messagebox.showinfo("BAZOR", "Ce service est déjà actif.")
            return
        if not self.start_service(svc):
            messagebox.showinfo("BAZOR", "Service détecté mais non géré automatiquement par le Hub.")
        self.root.after(800, self.refresh)

    def stop_selected(self):
        svc = self.selected_service()
        if not svc:
            return
        if not svc.get("managed"):
            messagebox.showinfo("BAZOR", "Le Hub ne ferme pas automatiquement ce programme externe.")
            return
        self.stop_service(svc)
        self.root.after(700, self.refresh)

    def restart_selected(self):
        svc = self.selected_service()
        if not svc or not svc.get("managed"):
            return
        self.stop_service(svc)
        self.root.after(600, lambda: (self.start_service(svc), self.refresh()))

    def close_duplicates(self):
        n = 0
        self.proc_cache = powershell_processes()
        for svc in SERVICES:
            if not svc.get("managed"):
                continue
            procs = self.matching(svc)
            if len(procs) > 1:
                # Conserve l'instance au PID le plus élevé (généralement la plus récente).
                procs = sorted(procs, key=lambda p:int(p.get("ProcessId") or 0))
                for p in procs[:-1]:
                    pid = int(p.get("ProcessId") or 0)
                    subprocess.run(["taskkill","/PID",str(pid),"/T","/F"], capture_output=True, creationflags=CREATE_NO_WINDOW)
                    n += 1
        messagebox.showinfo("BAZOR", f"{n} doublon(s) BAZOR fermé(s).")
        self.root.after(700, self.refresh)

    def centralize(self):
        # Ne touche qu'aux trois composants BAZOR Mobile reconnus.
        self.proc_cache = powershell_processes()
        for svc in SERVICES[:3]:
            self.stop_service(svc)
        time.sleep(0.6)
        for svc in SERVICES[:3]:
            self.start_service(svc)
        self.root.after(1300, self.refresh)

    def open_log(self):
        svc = self.selected_service()
        if not svc:
            return
        p = self.log_path(svc["id"])
        p.touch(exist_ok=True)
        os.startfile(str(p))

    def on_close(self):
        # Fermer l'interface ne coupe pas les services cachés.
        self.stop_evt.set()
        try:self.lock_socket.close()
        except Exception:pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    Hub(centralize="--centralize" in sys.argv).run()
