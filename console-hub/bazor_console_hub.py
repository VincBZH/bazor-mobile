import json
import os
import queue
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
UPDATE_HELPER = ROOT / "console-hub" / "bazor_interface_update_restart.py"
MOBILE_REPAIR = ROOT / "console-hub" / "bazor_mobile_network_repair.ps1"
MOBILE_URL_FILE = DATA / "mobile_url.txt"
MOBILE_STATUS_FILE = DATA / "mobile_network_status.json"

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
        "id": "popup-guard", "project": "BAZOR Mobile", "name": "Popup Guard",
        "match": "bazor_popup_guard.py", "port": None, "health": None,
        "command": [sys.executable, str(ROOT / "console-hub" / "bazor_popup_guard.py")],
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

def kill_legacy_bazor_wrappers():
    """Stop only obsolete BAZOR CMD wrappers known to relaunch the watcher in a loop."""
    if os.name != "nt":
        return 0
    ps = r"""
$me=$PID
Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" |
Where-Object {
  $_.CommandLine -match 'DEMARRER_GITHUB_WATCHER\.cmd' -or
  $_.CommandLine -match 'BAZOR GITHUB WATCHER'
} |
ForEach-Object {
  if ($_.ProcessId -ne $me) { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
"""
    try:
        subprocess.run(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",ps],
                       capture_output=True,text=True,timeout=8,creationflags=CREATE_NO_WINDOW)
        return 1
    except Exception:
        return 0

def powershell_processes():
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
        "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8, creationflags=CREATE_NO_WINDOW)
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

def load_hub_state():
    try:
        if STATE_FILE.exists():
            data=json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data,dict):
                return data
    except Exception:
        pass
    return {"migration_version":0}

def save_hub_state(data):
    try:
        STATE_FILE.parent.mkdir(parents=True,exist_ok=True)
        STATE_FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    except Exception:
        pass

def mobile_network_summary():
    try:
        if MOBILE_STATUS_FILE.exists():
            d=json.loads(MOBILE_STATUS_FILE.read_text(encoding="utf-8-sig",errors="replace"))
            ip=d.get("ip") or "?"
            adapter=d.get("adapter") or "?"
            web_ok=bool(d.get("web_self_test"))
            core_ok=bool(d.get("core_self_test"))
            if web_ok and core_ok:
                return f"LAN OK · {ip} · {adapter}", "ok"
            if d.get("web_listen_all") or d.get("core_listen_all"):
                return f"LAN À VÉRIFIER · {ip} · {adapter}", "warn"
            return f"LAN HS · {ip} · {adapter}", "bad"
    except Exception:
        pass
    return "LAN non diagnostiqué", "warn"

def detect_mobile_url():
    try:
        if MOBILE_URL_FILE.exists():
            url=MOBILE_URL_FILE.read_text(encoding="utf-8-sig",errors="replace").strip()
            if url.startswith("http://"):
                return url
    except Exception:
        pass
    try:
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        sock.connect(("8.8.8.8",80))
        ip=sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return f"http://{ip}:8776/"
    except Exception:
        pass
    return "http://<IP-PC>:8776/"

def pairing_busy():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8775/api/v1/security/status",timeout=0.8) as r:
            data=json.loads(r.read().decode("utf-8"))
        return bool(data.get("pairing_active")) or int(data.get("pairing_guard_seconds",0) or 0)>0
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
        self.hub_state = load_hub_state()
        self.lock_socket = socket.socket()
        try:
            self.lock_socket.bind(("127.0.0.1", LOCK_PORT))
            self.lock_socket.listen(1)
        except OSError:
            self.root.destroy()
            raise SystemExit(0)
        self.refresh_inflight = False
        self.centralize_inflight = False
        self.ui_queue = queue.Queue()
        self.build_ui()
        threading.Thread(target=kill_legacy_bazor_wrappers, daemon=True).start()
        if centralize:
            self.root.after(700, self.centralize)
        self.root.after(100, self._drain_ui_queue)
        self.root.after(300, self.refresh)
        self.root.after(1400, self.refresh_logs)

    def build_ui(self):
        top = tk.Frame(self.root, bg="#11151b", padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="BAZOR CONSOLE HUB", fg="white", bg="#11151b", font=("Segoe UI", 18, "bold")).pack(side="left")
        self.summary = tk.Label(top, text="Analyse…", fg="#aeb8c5", bg="#11151b", font=("Segoe UI", 10))
        self.summary.pack(side="left", padx=16)
        self.mobile_url_label = tk.Label(top, text=detect_mobile_url(), fg="#6dc8ff", bg="#11151b", font=("Consolas", 10, "bold"), cursor="hand2")
        self.mobile_url_label.pack(side="left", padx=10)
        self.mobile_url_label.bind("<Button-1>", lambda _e: self.copy_mobile_url())
        net_text,net_state=mobile_network_summary()
        net_color={"ok":"#42d483","warn":"#f2c94c","bad":"#ff6b6b"}.get(net_state,"#f2c94c")
        self.mobile_net_label = tk.Label(top, text=net_text, fg=net_color, bg="#11151b", font=("Segoe UI", 9, "bold"))
        self.mobile_net_label.pack(side="left", padx=8)
        self.code_label = tk.Label(top, text="", fg="black", bg="#f6d04d", font=("Consolas", 13, "bold"), padx=10, pady=5)
        self.code_label.pack(side="right")
        self.code_label.pack_forget()

        bar = tk.Frame(self.root, padx=10, pady=8)
        bar.pack(fill="x")
        for text, cmd in [
            ("↻ MAJ + RELANCE BAZOR", self.update_restart_bazor),
            ("RÉPARER MOBILE", self.repair_mobile_access),
            ("CENTRALISER / ADOPTER", self.centralize),
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

    def _drain_ui_queue(self):
        try:
            while True:
                item = self.ui_queue.get_nowait()
                kind = item[0]
                if kind == "refresh_ok":
                    self._apply_refresh(item[1], item[2])
                elif kind == "refresh_error":
                    self._refresh_failed(item[1])
                elif kind == "central_ok":
                    self._centralize_done(item[1])
                elif kind == "central_error":
                    self._centralize_failed(item[1])
        except queue.Empty:
            pass
        try:
            self.root.after(100, self._drain_ui_queue)
        except Exception:
            pass

    def log_path(self, sid):
        return LOG_DIR / f"{sid}.log"

    def matching(self, service, cache=None):
        pat = service.get("match","").lower()
        out = []
        source = self.proc_cache if cache is None else cache
        for p in source:
            cl = str(p.get("CommandLine") or "")
            if pat and pat in cl.lower():
                out.append(p)
        return out

    def service_state(self, service, cache=None):
        procs = self.matching(service, cache)
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
                detail = "Actif" + (" • port OK" if port else "") + (" • géré par le Hub" if service.get("managed") else " • externe")
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
        if self.refresh_inflight:
            return
        self.refresh_inflight = True
        try:
            self.summary.config(text="Analyse en arrière-plan…")
        except Exception:
            pass
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            cache = powershell_processes()
            counts = {"OK":0,"WORK":0,"ERROR":0,"DUPLICATE":0,"CLOSED":0,"EXTERNAL":0}
            snapshot = []
            for svc in SERVICES:
                state, procs, detail = self.service_state(svc, cache)
                counts[state] += 1
                pid = ",".join(str(p.get("ProcessId")) for p in procs[:3]) or "—"
                snapshot.append((svc["id"], state, svc["project"], svc["name"], pid, detail))
            self.proc_cache = cache
            self.ui_queue.put(("refresh_ok", snapshot, counts))
        except Exception as exc:
            self.ui_queue.put(("refresh_error", type(exc).__name__))

    def _apply_refresh(self, snapshot, counts):
        try:
            for sid, state, project, name, pid, detail in snapshot:
                label, tag = STATUS_UI[state]
                vals = (label, project, name, pid, detail)
                if sid in self.rows:
                    self.tree.item(self.rows[sid], values=vals, tags=(tag,))
                else:
                    self.rows[sid] = self.tree.insert("", "end", values=vals, tags=(tag,), iid=sid)
            self.summary.config(text=f"{counts['OK']} OK · {counts['WORK']} en cours · {counts['ERROR']+counts['DUPLICATE']} à voir · {counts['CLOSED']} fermés")
            try:self.mobile_url_label.config(text=detect_mobile_url())
            except Exception:pass
            try:
                net_text,net_state=mobile_network_summary()
                net_color={"ok":"#42d483","warn":"#f2c94c","bad":"#ff6b6b"}.get(net_state,"#f2c94c")
                self.mobile_net_label.config(text=net_text,fg=net_color)
            except Exception:pass
            self.update_security_code()
        finally:
            self.refresh_inflight = False
            try:
                self.root.after(2500, self.refresh)
            except Exception:
                pass

    def _refresh_failed(self, error_name):
        self.refresh_inflight = False
        try:
            self.summary.config(text=f"Analyse temporairement indisponible : {error_name}")
            self.root.after(2500, self.refresh)
        except Exception:
            pass

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
        env["BAZOR_HUB_MANAGED"] = "1"
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

    def _wait_port(self, port, wanted=True, seconds=6):
        if not port:
            time.sleep(0.4)
            return True
        end=time.time()+seconds
        while time.time()<end:
            if port_open(port) == wanted:
                return True
            time.sleep(0.25)
        return False

    def _migrate_service_hidden(self, svc):
        # Stop/restart one service at a time, never the whole stack at once.
        self.proc_cache = powershell_processes()
        procs = self.matching(svc)
        if not procs:
            return self.start_service(svc)
        self.stop_service(svc)
        self._wait_port(svc.get("port"), False, 4)
        ok=self.start_service(svc)
        if svc.get("port"):
            self._wait_port(svc.get("port"), True, 8)
        return ok

    def centralize(self):
        if self.centralize_inflight:
            return
        self.centralize_inflight = True
        try:
            self.summary.config(text="Centralisation en arrière-plan…")
        except Exception:
            pass
        threading.Thread(target=self._centralize_worker, daemon=True).start()

    def _centralize_worker(self):
        notes=[]
        try:
            # Première exécution: migrer les anciennes consoles visibles vers des processus cachés,
            # mais ne jamais couper Core pendant une tâche ou un appairage.
            first = int(self.hub_state.get("migration_version",0) or 0) < 2
            self.proc_cache = powershell_processes()

            if first:
                core = SERVICES[0]
                if self.matching(core):
                    if mobile_working() or pairing_busy():
                        notes.append("Core conservé temporairement : tâche/appairage en cours.")
                    else:
                        self._migrate_service_hidden(core)
                        notes.append("Core migré vers le Hub.")
                else:
                    self.start_service(core)
                    notes.append("Core démarré par le Hub.")

                for svc in SERVICES[1:3]:
                    self._migrate_service_hidden(svc)
                    notes.append(svc["name"]+" migré vers le Hub.")

                self.hub_state["migration_version"]=2
                self.hub_state["migration_at"]=time.time()
                save_hub_state(self.hub_state)
            else:
                for svc in SERVICES[:3]:
                    cache = powershell_processes()
                    self.proc_cache = cache
                    if not self.matching(svc, cache):
                        self.start_service(svc)
                        notes.append(svc["name"]+" était arrêté : redémarré.")

            self.ui_queue.put(("central_ok", notes))
        except Exception as exc:
            self.ui_queue.put(("central_error", type(exc).__name__))

    def _centralize_done(self, notes):
        self.centralize_inflight = False
        # Les démarrages/reprises normaux sont silencieux : pas de popup bloquante au lancement.
        # Les détails restent visibles dans le journal central du Hub.
        if notes:
            try:
                p = LOG_DIR / "hub.log"
                with p.open("a", encoding="utf-8") as log:
                    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    for note in notes:
                        log.write(f"[{stamp}] {note}\n")
            except Exception:
                pass
            self.summary.config(text="BAZOR prêt · services relancés")
        else:
            self.summary.config(text="Centralisation stable")
        self.refresh()

    def _centralize_failed(self, error_name):
        self.centralize_inflight = False
        self.summary.config(text=f"Centralisation bloquée : {error_name}")
        self.refresh()

    def copy_mobile_url(self):
        url=detect_mobile_url()
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.summary.config(text="Adresse mobile copiée : "+url)
        except Exception:
            pass

    def repair_mobile_access(self):
        if not MOBILE_REPAIR.exists():
            messagebox.showerror("BAZOR","Outil réseau mobile absent.")
            return
        try:
            cmd=[
                "powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",
                f"Start-Process powershell -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{str(MOBILE_REPAIR)}\" -Root \"{str(ROOT)}\"'"
            ]
            subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=CREATE_NO_WINDOW)
            self.summary.config(text="Réparation accès mobile lancée…")
            self.root.after(1800,self._refresh_mobile_url)
        except Exception as exc:
            messagebox.showerror("BAZOR",f"Réparation impossible : {type(exc).__name__}")

    def _refresh_mobile_url(self):
        try:
            self.mobile_url_label.config(text=detect_mobile_url())
        except Exception:
            pass
        self.refresh()

    def update_restart_bazor(self):
        if not UPDATE_HELPER.exists():
            messagebox.showerror("BAZOR", "Outil de mise à jour absent.")
            return
        try:
            flags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(
                [sys.executable, str(UPDATE_HELPER)],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )
            self.summary.config(text="Mise à jour + relance demandées…")
        except Exception as exc:
            messagebox.showerror("BAZOR", f"Relance impossible : {type(exc).__name__}")

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
