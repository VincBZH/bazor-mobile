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
USB_BRIDGE = ROOT / "console-hub" / "bazor_usb_android_bridge.ps1"
USB_STATUS_FILE = DATA / "usb_android_status.json"
H3_REPAIR = ROOT / "console-hub" / "bazor_minimax_h3_repair.py"
MOBILE_URL_FILE = DATA / "mobile_url.txt"
MOBILE_STATUS_FILE = DATA / "mobile_network_status.json"

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
HUB_BUILD = "2026.09.18.16"

SERVICES = [
    {
        "id": "core", "project": "BAZOR Mobile", "name": "Core 8775",
        "match": "bazor_pc_relay_v3.py", "port": 8775,
        "health": "http://127.0.0.1:8775/api/v1/security/status",
        "command": [sys.executable, str(ROOT / "pc-relay" / "bazor_pc_relay_v3.py")],
        "cwd": str(ROOT / "pc-relay"), "managed": True,
    },
    {
        "id": "web", "project": "BAZOR Mobile", "name": "Gateway Web/API 8776",
        "match": "bazor_mobile_gateway.py", "port": 8776,
        "health": "http://127.0.0.1:8776/api/v1/security/status",
        "command": [sys.executable, str(ROOT / "console-hub" / "bazor_mobile_gateway.py")],
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
        "launch_roots": [str(Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "BazorAIROOM")],
        "launch_candidates": ["LANCER_BAZOR_AI_ROOM.cmd","LANCER_AI_ROOM.cmd","Lancer.cmd","start.cmd","app.py","main.py","server.py"],
    },
    {
        "id": "comfy", "project": "AI Simple Studio", "name": "ComfyUI 8188",
        "match": "ComfyUI", "port": 8188, "health": "http://127.0.0.1:8188/",
        "managed": False,
        "launch_roots": [r"C:\AI\ComfyUI\ComfyUI_windows_portable", r"C:\AI\ComfyUI"],
        "launch_candidates": ["run_nvidia_gpu.bat","run_nvidia_gpu_fast_fp16_accumulation.bat","run_cpu.bat"],
    },
    {
        "id": "studio", "project": "AI Simple Studio", "name": "Studio 8191",
        "match": "SimpleStudio", "port": 8191, "health": "http://127.0.0.1:8191/",
        "managed": False,
        "launch_roots": [r"C:\AI\SimpleStudioV2"],
        "launch_candidates": ["LANCER_BAZOR_STUDIO.cmd","LANCER_STUDIO.cmd","Lancer.cmd","start.cmd","run.cmd","app.py","main.py","server.py"],
    },
    {
        "id": "wii", "project": "Projet Wii AI Relay", "name": "Wii Bridge",
        "match": "Wii_AI_Bridge", "port": None, "health": None,
        "managed": False,
        "launch_roots": [r"C:\projetWII\Wii_AI_Bridge"],
        "launch_candidates": ["start_bridge.ps1","LANCER_WII_BRIDGE.cmd","start.cmd"],
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

def listening_pids(port):
    if not port or os.name != "nt":
        return []
    ps = (
        "$p=" + str(int(port)) + ";"
        "Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess -Unique | ConvertTo-Json -Compress"
    )
    try:
        p=subprocess.run(
            ["powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",ps],
            capture_output=True,text=True,encoding="utf-8",errors="replace",
            timeout=4,creationflags=CREATE_NO_WINDOW
        )
        raw=(p.stdout or "").strip()
        if not raw:
            return []
        data=json.loads(raw)
        vals=data if isinstance(data,list) else [data]
        return sorted({int(x) for x in vals if str(x).isdigit()})
    except Exception:
        return []

def http_ok(url):
    if not url:
        return None
    # Un seul timeout court produisait un faux rouge/vert toutes les ~3 s.
    # Deux essais et un délai raisonnable évitent de confondre latence et panne.
    for timeout in (1.2, 2.2):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return 200 <= getattr(r, "status", 200) < 500
        except Exception:
            pass
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

def usb_status_summary():
    try:
        if USB_STATUS_FILE.exists():
            d=json.loads(USB_STATUS_FILE.read_text(encoding="utf-8-sig",errors="replace"))
            if d.get("ok") and d.get("connected"):
                return "USB ANDROID OK · biométrie localhost prête", "ok"
            if d.get("reason") == "unauthorized":
                return "USB Android · autorisation ADB à accepter sur le téléphone", "warn"
            if d.get("reason") == "adb_missing":
                return "USB Android · ADB introuvable", "warn"
            if d.get("connected"):
                return "USB Android détecté · pont à réparer", "warn"
    except Exception:
        pass
    return "USB Android non détecté", "warn"

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
        if USB_STATUS_FILE.exists():
            d=json.loads(USB_STATUS_FILE.read_text(encoding="utf-8-sig",errors="replace"))
            if d.get("ok") and d.get("connected") and d.get("web_reverse"):
                return "http://127.0.0.1:8776/"
    except Exception:
        pass
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
        self.qr_photo = None
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
        self.stable_states = {}
        self.state_fail_counts = {}
        self.build_ui()
        threading.Thread(target=kill_legacy_bazor_wrappers, daemon=True).start()
        if centralize:
            self.root.after(700, self.centralize)
        self.root.after(100, self._drain_ui_queue)
        self.root.after(300, self.refresh)
        self.root.after(1400, self.refresh_logs)
        self.root.after(1700, self.ensure_pairing_code)

    def build_ui(self):
        top = tk.Frame(self.root, bg="#11151b", padx=12, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="BAZOR CONSOLE HUB", fg="white", bg="#11151b", font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Label(top, text="v"+HUB_BUILD, fg="#6dc8ff", bg="#11151b", font=("Consolas", 9, "bold")).pack(side="left", padx=(8,0))
        self.summary = tk.Label(top, text="Analyse…", fg="#aeb8c5", bg="#11151b", font=("Segoe UI", 10))
        self.summary.pack(side="left", padx=16)
        self.mobile_url_label = tk.Label(top, text=detect_mobile_url(), fg="#6dc8ff", bg="#11151b", font=("Consolas", 10, "bold"), cursor="hand2")
        self.mobile_url_label.pack(side="left", padx=10)
        self.mobile_url_label.bind("<Button-1>", lambda _e: self.copy_mobile_url())
        net_text,net_state=mobile_network_summary()
        net_color={"ok":"#42d483","warn":"#f2c94c","bad":"#ff6b6b"}.get(net_state,"#f2c94c")
        self.mobile_net_label = tk.Label(top, text=net_text, fg=net_color, bg="#11151b", font=("Segoe UI", 9, "bold"))
        self.mobile_net_label.pack(side="left", padx=8)
        usb_text,usb_state=usb_status_summary()
        usb_color={"ok":"#42d483","warn":"#f2c94c","bad":"#ff6b6b"}.get(usb_state,"#f2c94c")
        self.usb_label = tk.Label(top, text=usb_text, fg=usb_color, bg="#11151b", font=("Segoe UI", 9, "bold"))
        self.usb_label.pack(side="left", padx=8)
        self.code_label = tk.Label(top, text="", fg="black", bg="#f6d04d", font=("Consolas", 13, "bold"), padx=10, pady=5)
        self.code_label.pack(side="right")
        self.code_label.pack_forget()

        bar = tk.Frame(self.root, padx=10, pady=8)
        bar.pack(fill="x")
        for text, cmd in [
            ("↻ MAJ + RELANCE BAZOR", self.update_restart_bazor),
            ("RÉPARER MOBILE", self.repair_mobile_access),
            ("USB TÉLÉPHONE", self.usb_mobile),
            ("RÉPARER H3", self.repair_h3),
            ("APPAIRER TÉLÉPHONE", self.open_pairing_qr),
            ("NOUVEAU CODE", self.new_pairing_code),
            ("CENTRALISER / ADOPTER", self.centralize),
            ("ACTUALISER", self.refresh),
            ("VOIR LOG", self.open_log),
            ("DÉMARRER", self.start_selected),
            ("REDÉMARRER", self.restart_selected),
            ("FERMER", self.stop_selected),
            ("FERMER DOUBLONS", self.close_duplicates),
        ]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=3)

        self.pair_frame = tk.Frame(self.root, bg="#fff7cc", bd=1, relief="solid", padx=10, pady=8)
        self.qr_label = tk.Label(self.pair_frame, bg="white", width=20, height=10)
        self.qr_label.pack(side="left", padx=(0,12))
        self.pair_text = tk.Label(
            self.pair_frame,
            text="",
            justify="left",
            anchor="w",
            bg="#fff7cc",
            fg="#111111",
            font=("Segoe UI", 11, "bold")
        )
        self.pair_text.pack(side="left", fill="x", expand=True)
        ttk.Button(self.pair_frame, text="NOUVEAU QR", command=self.new_pairing_code).pack(side="right", padx=(12,0))
        self.pair_text.config(text="APPAIRAGE BAZOR\nPréparation du QR…")
        self.qr_label.config(text="QR…", image="", width=20, height=10)
        self.pair_frame.pack(fill="x", padx=10, pady=(0,8))

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
                elif kind == "h3_ok":
                    self._h3_done()
                elif kind == "h3_error":
                    self._h3_failed(item[1])
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
        port_num = service.get("port")
        port = port_open(port_num) if port_num else None
        healthy = http_ok(service.get("health")) if service.get("health") else None
        listeners = listening_pids(port_num) if port_num else []
        detail = ""

        # Pour les applis externes (ComfyUI/Studio), plusieurs processus lies
        # peuvent appartenir a UNE seule instance. Seuls plusieurs LISTENERS
        # sur le port comptent comme vrai doublon.
        if not service.get("managed") and port_num:
            if len(listeners) > 1:
                state = "DUPLICATE"
                detail = f"{len(listeners)} écouteurs réels sur le port {port_num}"
            elif healthy:
                state = "OK"
                detail = f"Actif • port OK • {len(procs)} processus lié(s)"
            elif procs:
                state = "ERROR"
                detail = "Processus présent mais service ne répond pas"
            elif port:
                state = "EXTERNAL"
                detail = "Port actif mais processus non identifié"
            else:
                state = "CLOSED"
                detail = "Arrêté"
        elif len(procs) > 1:
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
        # Pas de clignotement "analyse/OK" toutes les 2,5 s.
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

    def _stable_snapshot(self, snapshot):
        out=[]
        for sid,state,project,name,pid,detail in snapshot:
            prev=self.stable_states.get(sid)
            # OK/WORK are accepted immediately. A transient ERROR/CLOSED/EXTERNAL
            # must repeat 3 times before changing a previously healthy display.
            bad=state in ("ERROR","CLOSED","EXTERNAL")
            prev_good=prev and prev[0] in ("OK","WORK")
            if bad and prev_good:
                n=self.state_fail_counts.get(sid,0)+1
                self.state_fail_counts[sid]=n
                if n < 3:
                    out.append(prev)
                    continue
            else:
                self.state_fail_counts[sid]=0
            row=(sid,state,project,name,pid,detail)
            self.stable_states[sid]=row
            out.append(row)
        return out

    def _apply_refresh(self, snapshot, counts):
        try:
            snapshot=self._stable_snapshot(snapshot)
            counts={"OK":0,"WORK":0,"ERROR":0,"DUPLICATE":0,"CLOSED":0,"EXTERNAL":0}
            for row in snapshot:
                counts[row[1]] = counts.get(row[1],0) + 1
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
            try:
                usb_text,usb_state=usb_status_summary()
                usb_color={"ok":"#42d483","warn":"#f2c94c","bad":"#ff6b6b"}.get(usb_state,"#f2c94c")
                self.usb_label.config(text=usb_text,fg=usb_color)
            except Exception:pass
            self.update_security_code()
        finally:
            self.refresh_inflight = False
            try:
                self.root.after(5000, self.refresh)
            except Exception:
                pass

    def _refresh_failed(self, error_name):
        self.refresh_inflight = False
        try:
            self.summary.config(text=f"Analyse temporairement indisponible : {error_name}")
            self.root.after(5000, self.refresh)
        except Exception:
            pass

    def _pairing_qr_url(self, code):
        base=detect_mobile_url().strip()
        if not base.endswith("/"):
            base += "/"
        # Fragment volontaire: le code n'est jamais envoyé au serveur HTTP ni inscrit dans ses logs.
        return base + "#pair=" + urllib.parse.quote(str(code))

    def _ensure_qr_modules(self):
        try:
            import qrcode  # noqa
            from PIL import ImageTk  # noqa
            return True
        except Exception:
            return False

    def _install_qr_modules_async(self):
        def worker():
            try:
                subprocess.run(
                    [sys.executable,"-m","pip","install","qrcode[pil]","--disable-pip-version-check","-q"],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120,
                    creationflags=CREATE_NO_WINDOW
                )
            except Exception:
                pass
            try:
                self.root.after(0, lambda: self.show_pairing_qr(self.security_code) if self.security_code else None)
            except Exception:
                pass
        threading.Thread(target=worker,daemon=True).start()

    def show_pairing_qr(self, code):
        if not code:
            self.pair_text.config(text="APPAIRAGE BAZOR\nEn attente d'une clé du Core…")
            self.qr_label.config(image="",text="QR en attente",width=20,height=10)
            self.pair_frame.pack(fill="x", padx=10, pady=(0,8))
            return
        url=self._pairing_qr_url(code)
        mode="USB" if url.startswith("http://127.0.0.1:") else "Wi-Fi"
        self.pair_text.config(
            text=f"APPAIRAGE BAZOR • {mode}\n"
                 f"Scanne ce QR avec le téléphone.\n"
                 f"Appairage automatique après ouverture.\n"
                 f"Code secours : {code}"
        )
        self.pair_frame.pack(fill="x", padx=10, pady=(0,8))
        if self._ensure_qr_modules():
            try:
                import qrcode
                from PIL import ImageTk
                qr=qrcode.QRCode(version=None,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=6,border=4)
                qr.add_data(url)
                qr.make(fit=True)
                img=qr.make_image(fill_color="black",back_color="white").convert("RGB")
                img=img.resize((180,180))
                self.qr_photo=ImageTk.PhotoImage(img)
                self.qr_label.config(image=self.qr_photo,text="",width=180,height=180)
                return
            except Exception:
                pass
        self.qr_label.config(image="",text="Installation QR…",width=20,height=10)
        self._install_qr_modules_async()

    def open_pairing_qr(self):
        # Un clic = une fenêtre d'appairage très visible avec QR.
        if not self.security_code:
            info=self._local_pairing_info(rotate=False)
            if not (info and info.get("code")):
                info=self._local_pairing_info(rotate=True)
            if info and info.get("code"):
                self.security_code=str(info["code"])
                self.code_label.config(text="🔐 APPAIRAGE : "+self.security_code)
                self.code_label.pack(side="right")

        try:
            if getattr(self,"pair_win",None) and self.pair_win.winfo_exists():
                self.pair_win.lift()
                self.pair_win.focus_force()
                self._render_pairing_window()
                return
        except Exception:
            pass

        self.pair_win=tk.Toplevel(self.root)
        self.pair_win.title("BAZOR • APPAIRER TÉLÉPHONE")
        self.pair_win.geometry("520x650")
        self.pair_win.minsize(480,600)
        self.pair_win.configure(bg="#0f141b")
        self.pair_win.transient(self.root)
        try:
            self.pair_win.attributes("-topmost", True)
            self.pair_win.after(1200, lambda: self.pair_win.attributes("-topmost", False))
        except Exception:
            pass

        self.pair_title=tk.Label(
            self.pair_win,text="APPAIRER LE TÉLÉPHONE",
            bg="#0f141b",fg="white",font=("Segoe UI",20,"bold")
        )
        self.pair_title.pack(pady=(18,6))

        self.pair_subtitle=tk.Label(
            self.pair_win,text="Scanne le QR avec le téléphone",
            bg="#0f141b",fg="#8fd3ff",font=("Segoe UI",11,"bold")
        )
        self.pair_subtitle.pack(pady=(0,10))

        self.pair_qr_big=tk.Label(
            self.pair_win,bg="white",fg="#111111",
            text="Préparation du QR…",font=("Segoe UI",12,"bold"),
            width=34,height=17
        )
        self.pair_qr_big.pack(pady=8)

        self.pair_code_big=tk.Label(
            self.pair_win,text="",
            bg="#f6d04d",fg="#111111",
            font=("Consolas",18,"bold"),padx=16,pady=8
        )
        self.pair_code_big.pack(pady=10)

        self.pair_hint=tk.Label(
            self.pair_win,
            text="Le QR contient l'adresse locale BAZOR + la clé d'appairage.\n"
                 "La clé n'est pas envoyée dans les logs HTTP.",
            bg="#0f141b",fg="#cfd7e3",font=("Segoe UI",10),justify="center"
        )
        self.pair_hint.pack(pady=8)

        btns=tk.Frame(self.pair_win,bg="#0f141b")
        btns.pack(pady=10)
        ttk.Button(btns,text="NOUVEAU QR",command=self.new_pairing_code).pack(side="left",padx=5)
        ttk.Button(btns,text="FERMER",command=self.pair_win.destroy).pack(side="left",padx=5)

        self._render_pairing_window()

    def _render_pairing_window(self):
        if not getattr(self,"pair_win",None) or not self.pair_win.winfo_exists():
            return
        code=self.security_code
        if not code:
            self.pair_qr_big.config(image="",text="En attente du Core…",width=34,height=17)
            self.pair_code_big.config(text="CLÉ EN ATTENTE")
            self.pair_subtitle.config(text="Le Core prépare la clé d'appairage…")
            self.pair_win.after(1200,self._retry_pairing_window)
            return

        self.pair_code_big.config(text=code)
        url=self._pairing_qr_url(code)
        mode="USB" if url.startswith("http://127.0.0.1:") else "Wi-Fi"
        self.pair_subtitle.config(text=f"Scanne le QR • mode {mode}")

        if not self._ensure_qr_modules():
            self.pair_qr_big.config(image="",text="Installation du générateur QR…",width=34,height=17)
            self._install_qr_modules_async()
            self.pair_win.after(1800,self._render_pairing_window)
            return

        try:
            import qrcode
            from PIL import ImageTk
            qr=qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=9,border=4
            )
            qr.add_data(url)
            qr.make(fit=True)
            img=qr.make_image(fill_color="black",back_color="white").convert("RGB")
            img=img.resize((360,360))
            self.pair_qr_big_photo=ImageTk.PhotoImage(img)
            self.pair_qr_big.config(
                image=self.pair_qr_big_photo,text="",
                width=360,height=360
            )
            self.show_pairing_qr(code)
        except Exception:
            self.pair_qr_big.config(image="",text="QR indisponible • clique NOUVEAU QR",width=34,height=17)

    def _retry_pairing_window(self):
        info=self._local_pairing_info(rotate=False)
        if not (info and info.get("code")):
            info=self._local_pairing_info(rotate=True)
        if info and info.get("code"):
            self.security_code=str(info["code"])
            self.code_label.config(text="🔐 APPAIRAGE : "+self.security_code)
            self.code_label.pack(side="right")
        self._render_pairing_window()

    def _local_pairing_info(self, rotate=False):
        try:
            suffix = "?new=1" if rotate else ""
            with urllib.request.urlopen("http://127.0.0.1:8775/api/v1/security/pairing-local"+suffix, timeout=1.2) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            return None

    def ensure_pairing_code(self):
        # Le Hub PC doit toujours afficher une cle utilisable.
        # Si le Core n'en a pas en memoire, on en cree une seule fois ici.
        info = self._local_pairing_info(rotate=False)
        if info and info.get("code"):
            self.security_code = str(info["code"])
            self.code_label.config(text="🔐 APPAIRAGE : " + self.security_code)
            self.code_label.pack(side="right")
            self.show_pairing_qr(self.security_code)
            return
        info = self._local_pairing_info(rotate=True)
        if info and info.get("code"):
            self.security_code = str(info["code"])
            self.code_label.config(text="🔐 APPAIRAGE : " + self.security_code)
            self.code_label.pack(side="right")
            self.show_pairing_qr(self.security_code)
            self.summary.config(text="Clé + QR d’appairage prêts")
            return
        self.show_pairing_qr(None)
        self.summary.config(text="Appairage : attente du Core…")
        self.root.after(1800, self.ensure_pairing_code)

    def new_pairing_code(self):
        info = self._local_pairing_info(rotate=True)
        if info and info.get("code"):
            self.security_code = str(info["code"])
            self.code_label.config(text="🔐 APPAIRAGE : " + self.security_code)
            self.code_label.pack(side="right")
            self.show_pairing_qr(self.security_code)
            try:self._render_pairing_window()
            except Exception:pass
            self.summary.config(text="Nouveau QR d’appairage prêt")
        else:
            self.summary.config(text="Core non joignable pour l’appairage")

    def update_security_code(self):
        # Source fiable: mémoire du Core via endpoint loopback uniquement.
        info = self._local_pairing_info(rotate=False)
        code = str((info or {}).get("code") or "")
        if not code:
            # Compatibilité avec un ancien Core : repli sur le log.
            text = tail(self.log_path("core"), 120)
            matches = re.findall(r">>>\s*([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})\s*<<<", text)
            if not matches:
                matches = re.findall(r"Code appairage mobile:\s*([A-Z0-9-]{10,20})", text)
            code = matches[-1] if matches else ""
        self.security_code = code
        if self.security_code:
            self.code_label.config(text="🔐 APPAIRAGE : " + self.security_code)
            self.code_label.pack(side="right")
            self.show_pairing_qr(self.security_code)
        else:
            self.code_label.pack_forget()
            self.show_pairing_qr(None)

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

    def resolve_external_launcher(self, svc):
        roots=[Path(x) for x in (svc.get("launch_roots") or [])]
        for root in roots:
            for name in (svc.get("launch_candidates") or []):
                p=root / name
                if p.is_file():
                    return p
        # Fallback discovery stays shallow and refuses installer/repair/delete tools.
        safe_words=("lancer","launch","start","run","main","server","app")
        denied=("install","uninstall","setup","repair","update","upgrade","clean","delete","remove","reset")
        for root in roots:
            if not root.is_dir():
                continue
            try:
                for p in list(root.glob("*.cmd"))+list(root.glob("*.bat"))+list(root.glob("*.ps1"))+list(root.glob("*.py")):
                    n=p.name.lower()
                    if any(x in n for x in denied):
                        continue
                    if any(x in n for x in safe_words):
                        return p
            except Exception:
                continue
        return None

    def start_external_service(self, svc):
        launcher=self.resolve_external_launcher(svc)
        if not launcher:
            self.summary.config(text=f"{svc['name']} : aucun lanceur sûr trouvé")
            return False
        log=open(self.log_path(svc["id"]), "a", encoding="utf-8", buffering=1)
        ext=launcher.suffix.lower()
        if ext in (".cmd",".bat"):
            cmd=["cmd.exe","/c",str(launcher)]
        elif ext==".ps1":
            cmd=["powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",str(launcher)]
        elif ext==".py":
            cmd=[sys.executable,str(launcher)]
        else:
            self.summary.config(text=f"{svc['name']} : type de lanceur refusé")
            return False
        try:
            subprocess.Popen(
                cmd, cwd=str(launcher.parent),
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
            )
            self.summary.config(text=f"{svc['name']} : démarrage lancé via {launcher.name}")
            self.root.after(1800,self.refresh)
            return True
        except Exception as exc:
            self.summary.config(text=f"{svc['name']} : démarrage impossible ({type(exc).__name__})")
            return False

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
            self.summary.config(text="Sélectionne un service à démarrer")
            return
        cache=powershell_processes()
        self.proc_cache=cache
        if self.matching(svc,cache):
            self.summary.config(text=f"{svc['name']} est déjà actif")
            return
        if svc.get("managed"):
            ok=self.start_service(svc)
            self.summary.config(text=f"{svc['name']} : démarrage lancé" if ok else f"{svc['name']} : démarrage impossible")
        else:
            self.start_external_service(svc)
        self.root.after(900, self.refresh)

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
                procs = sorted(procs, key=lambda p:int(p.get("ProcessId") or 0))
                for p in procs[:-1]:
                    pid = int(p.get("ProcessId") or 0)
                    if pid:
                        subprocess.run(["taskkill","/PID",str(pid),"/T","/F"], capture_output=True, creationflags=CREATE_NO_WINDOW)
                        n += 1
        self.summary.config(text=(f"{n} vrai(s) doublon(s) BAZOR fermé(s)" if n else "Aucun vrai doublon BAZOR à fermer"))
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

    def repair_h3(self):
        if not H3_REPAIR.exists():
            self.summary.config(text="Réparateur MiniMax H3 absent")
            return
        self.summary.config(text="MiniMax H3 : réparation en cours… téléchargement possible ~2,6 Go")
        self.selected_id="comfy"
        self.refresh_logs()
        threading.Thread(target=self._repair_h3_worker,daemon=True).start()

    def _repair_h3_worker(self):
        log_path=self.log_path("comfy")
        try:
            with open(log_path,"a",encoding="utf-8",buffering=1) as log:
                log.write("\n===== BAZOR H3 REPAIR =====\n")
                p=subprocess.run(
                    [sys.executable,str(H3_REPAIR)],
                    cwd=str(ROOT),
                    stdout=log,stderr=subprocess.STDOUT,
                    creationflags=CREATE_NO_WINDOW
                )
            if p.returncode==0:
                self.ui_queue.put(("h3_ok",None))
            else:
                self.ui_queue.put(("h3_error",f"code {p.returncode}"))
        except Exception as exc:
            self.ui_queue.put(("h3_error",type(exc).__name__))

    def _h3_done(self):
        self.summary.config(text="MiniMax H3 réparé • redémarrage ComfyUI…")
        svc=next((x for x in SERVICES if x.get("id")=="comfy"),None)
        if svc:
            try:
                self.stop_service(svc)
            except Exception:
                pass
            try:
                self.start_external_service(svc)
            except Exception:
                pass
        self.root.after(1800,self.refresh)

    def _h3_failed(self,detail):
        self.summary.config(text=f"MiniMax H3 : réparation bloquée ({detail})")
        self.selected_id="comfy"
        self.refresh_logs()

    def usb_mobile(self):
        if not USB_BRIDGE.exists():
            messagebox.showerror("BAZOR","Outil USB Android absent.")
            return
        try:
            cmd=[
                "powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",
                str(USB_BRIDGE),"-Root",str(ROOT),"-OpenPhone"
            ]
            subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=CREATE_NO_WINDOW)
            self.summary.config(text="Connexion USB Android + ouverture mobile…")
            self.root.after(2200,self._refresh_mobile_url)
        except Exception as exc:
            messagebox.showerror("BAZOR",f"USB Android impossible : {type(exc).__name__}")

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
