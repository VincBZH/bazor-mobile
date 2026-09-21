import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "pc-relay" / "BAZOR_DATA"
DATA.mkdir(parents=True, exist_ok=True)
STATE_FILE = DATA / "project_dashboard_state.json"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
REFRESH_LOCAL_MS = 5000
REFRESH_GITHUB_SECONDS = 60
BUILD = "2026.09.21.2"

# IMPORTANT SECURITE:
# - seuls les lanceurs listes ici peuvent etre executes;
# - aucune commande provenant de GitHub n'est executee;
# - git pull est uniquement --ff-only et n'ecrase jamais volontairement des modifications locales.
PROJECTS = [
    {
        "id": "core", "priority": "P0", "project": "BAZOR CORE v3",
        "sub": "Core + Watcher + Action Engine",
        "launcher": "LANCER_BAZOR_CONSOLE_HUB.cmd",
        "health": ["http://127.0.0.1:8775/api/v1/health"],
        "process": "bazor_pc_relay_v3.py",
        "repo": "VincBZH/bazor-mobile", "issue": 151,
        "next": "Stabiliser les preuves runtime et le bridge Mammouth/Ollama.",
    },
    {
        "id": "bridge", "priority": "P0", "project": "Bridge Ollama ↔ Mammouth",
        "sub": "PR #150 / preuve E2E #151",
        "launcher": "LANCER_BAZOR_CONSOLE_HUB.cmd",
        "health": ["http://127.0.0.1:8775/api/v1/health"],
        "repo": "VincBZH/bazor-mobile", "issue": 151,
        "next": "Obtenir BAZOR_BRIDGE_E2E_OK sur le PC reel avant fusion #150.",
    },
    {
        "id": "room", "priority": "P0", "project": "BAZOR AI ROOM V3",
        "sub": "Cockpit / control",
        "launcher": "BAZOR_ROOM_V3_ONESHOT.cmd",
        "health": ["http://127.0.0.1:8765/control", "http://127.0.0.1:8765/"],
        "process": "BazorAIROOM",
        "repo": "VincBZH/bazor-mobile", "issue": 154,
        "next": "Retrouver/restaurer le chat multi-IA sans confondre /control et conversation.",
    },
    {
        "id": "quinto", "priority": "P0", "project": "AI ROOM",
        "sub": "QUINTO : GPT + Ollama + Mammouth + OpenRouter + NoTrack",
        "launcher": "BAZOR_ROOM_V3_ONESHOT.cmd",
        "health": ["http://127.0.0.1:8765/"],
        "repo": "VincBZH/bazor-mobile", "issue": 148,
        "next": "Enregistrer ROOM-QUINTO-001 puis prouver le routage reel.",
    },
    {
        "id": "studio", "priority": "P0", "project": "AI Simple Studio",
        "sub": "Studio certifie",
        "launcher": "LANCER_BAZOR_STUDIO_CERTIFIE.cmd",
        "health": ["http://127.0.0.1:8191/"],
        "process": "SimpleStudio",
        "repo": "VincBZH/bazor-mobile", "issue": 153,
        "next": "Conserver 8191 stable et poursuivre la chaine P0/P1 sans faux succes.",
    },
    {
        "id": "h3", "priority": "P0", "project": "AI Simple Studio",
        "sub": "MiniMax H3 video / dimensions",
        "launcher": "LANCER_BAZOR_STUDIO_CERTIFIE.cmd",
        "health": ["http://127.0.0.1:8188/", "http://127.0.0.1:8191/"],
        "repo": "VincBZH/bazor-mobile", "issue": 144,
        "next": "Corriger le mapping width/height H3 et valider un payload ComfyUI reel.",
    },
    {
        "id": "checkpoints", "priority": "P1", "project": "AI Simple Studio",
        "sub": "NoobAI / RealVisXL / Juggernaut XL",
        "launcher": "LANCER_BAZOR_STUDIO_CERTIFIE.cmd",
        "health": ["http://127.0.0.1:8191/"],
        "repo": "VincBZH/bazor-mobile", "issue": 143,
        "next": "Utiliser uniquement les checkpoints réellement presents.",
    },
    {
        "id": "seamless", "priority": "P1", "project": "AI Simple Studio",
        "sub": "Seamless Chain / video longue",
        "launcher": "LANCER_BAZOR_STUDIO_CERTIFIE.cmd",
        "health": ["http://127.0.0.1:8191/"],
        "repo": "VincBZH/bazor-mobile", "issue": 153,
        "next": "Debloquer STUDIO-P0-004 avant de poursuivre P1.",
    },
    {
        "id": "hub", "priority": "P1", "project": "BAZOR Console Hub",
        "sub": "Cockpit central / Autopilot",
        "launcher": "LANCER_BAZOR_CONSOLE_HUB.cmd",
        "process": "bazor_console_hub.py",
        "repo": "VincBZH/bazor-mobile",
        "next": "Utiliser ce tableau comme point d'entree unique.",
    },
    {
        "id": "mobile", "priority": "P1", "project": "BAZOR Mobile Command Center",
        "sub": "Telephone ↔ PC",
        "launcher": "LANCER_BAZOR_MOBILE_TOUT_EN_UN.cmd",
        "health": ["http://127.0.0.1:8776/", "http://127.0.0.1:8775/api/v1/health"],
        "repo": "VincBZH/bazor-mobile", "issue": 1,
        "next": "Stabiliser reconnexion, micro-coupures et preuve E2E telephone.",
    },
    {
        "id": "tor", "priority": "P2", "project": "BAZOR TOR",
        "sub": "Transport reseau optionnel",
        "launcher": "BAZOR_ROOM_V3_ONESHOT.cmd",
        "repo": "VincBZH/bazor-mobile", "issue": 147,
        "next": "Localiser le module existant, l'enregistrer et le tester sans casser le routage IA.",
    },
    {
        "id": "watch", "priority": "P2", "project": "BAZOR Montre",
        "sub": "Application + relais",
        "launcher": "INSTALLER_BAZOR_WATCH_USB.cmd",
        "repo": "VincBZH/bazor-mobile",
        "next": "Projet secondaire; APK et installateur presents.",
    },
    {
        "id": "filebus", "priority": "P2", "project": "BAZOR FileBus",
        "sub": "GPT ↔ Ollama ↔ Mammouth",
        "launcher": "RELANCER_WATCHER_FILEBUS.cmd",
        "process": "bazor_github_watcher.py",
        "repo": "VincBZH/bazor-mobile", "issue": 2,
        "next": "Consolider les anciens retries et garder un canal unique.",
    },
    {
        "id": "master", "priority": "P2", "project": "BAZOR MASTER SPEC",
        "sub": "Reference unique",
        "repo": "VincBZH/bazor-mobile", "issue": 149,
        "next": "Reference de cahier des charges; ne vaut pas preuve runtime.",
    },
    {
        "id": "wii", "priority": "P3", "project": "Jeu Wii / PC",
        "sub": "Wii AI Bridge / prototype jeu",
        "launch_candidates": [
            r"C:\projetWII\Wii_AI_Bridge\LANCER_WII_BRIDGE.cmd",
            r"C:\projetWII\Wii_AI_Bridge\start.cmd",
            r"C:\projetWII\Wii_AI_Bridge\start_bridge.ps1",
        ],
        "repo": "VincBZH/projetWII-ai-relay", "issue": 1,
        "next": "Suspendu derriere les priorites BAZOR; reprendre apres stabilisation du socle.",
    },
    {
        "id": "modo", "priority": "P3", "project": "MODO Viewer TikTok",
        "sub": "Moderation live",
        "next": "SUSPENDU : aucun lanceur recent certifie dans les depots BAZOR.",
        "forced_status": "SUSPENDU",
    },
    {
        "id": "mld", "priority": "P3", "project": "Mission Locale Douaisis",
        "sub": "Diaporama / PDF / affiche",
        "next": "Projet documentaire separe; pas de runtime logiciel a lancer.",
        "forced_status": "DOCUMENT",
    },
]

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
STATUS_COLOR = {
    "ACTIF": "#2fa36b", "VERIFIE": "#2fa36b", "PARTIEL": "#b77900",
    "EN COURS": "#b77900", "BLOQUE": "#d83c4a", "ARRETE": "#667085",
    "OUVERT": "#4377a8", "SUSPENDU": "#667085", "DOCUMENT": "#667085",
    "REFERENCE": "#7a5af8", "INCONNU": "#667085",
}

def _port_open(port):
    s = socket.socket()
    s.settimeout(0.35)
    try:
        return s.connect_ex(("127.0.0.1", int(port))) == 0
    finally:
        s.close()

def _http_ok(url):
    for timeout in (0.8, 1.6):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return 200 <= getattr(r, "status", 200) < 500
        except Exception:
            pass
    return False

def _process_present(pattern):
    if os.name != "nt" or not pattern:
        return False
    ps = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -match '" + pattern.replace("'", "''") + "' } | "
        "Select-Object -First 1 -ExpandProperty ProcessId"
    )
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True, text=True, timeout=4, creationflags=CREATE_NO_WINDOW
        )
        return bool((p.stdout or "").strip())
    except Exception:
        return False

def _safe_pull():
    try:
        p = subprocess.run(
            ["git", "-C", str(ROOT), "pull", "--ff-only"],
            capture_output=True, text=True, timeout=25, creationflags=CREATE_NO_WINDOW
        )
        return p.returncode == 0, (p.stdout or p.stderr or "").strip()
    except Exception as exc:
        return False, type(exc).__name__

def _find_launcher(project):
    launch = project.get("launcher")
    if launch:
        p = ROOT / launch
        if p.is_file():
            return p
    for raw in project.get("launch_candidates") or []:
        p = Path(os.path.expandvars(raw))
        if p.is_file():
            return p
    return None

def _run_launcher(path):
    ext = path.suffix.lower()
    if ext in (".cmd", ".bat"):
        cmd = ["cmd.exe", "/c", str(path)]
    elif ext == ".ps1":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    elif ext == ".py":
        cmd = [sys.executable, str(path)]
    else:
        raise RuntimeError("launcher_type_refused")
    subprocess.Popen(
        cmd, cwd=str(path.parent),
        creationflags=CREATE_NEW_PROCESS_GROUP
    )

def _gh_json(project):
    repo = project.get("repo")
    num = project.get("issue")
    if not repo or not num:
        return None
    try:
        p = subprocess.run(
            ["gh", "issue", "view", str(num), "--repo", repo,
             "--json", "state,title,updatedAt,url,comments"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10, creationflags=CREATE_NO_WINDOW
        )
        if p.returncode != 0:
            return None
        return json.loads(p.stdout)
    except Exception:
        return None

def _github_status(data):
    if not data:
        return None, ""
    comments = data.get("comments") or []
    last = comments[-1].get("body", "") if comments else ""
    text = (last or "")[-6000:].upper()
    if any(k in text for k in ("BAZOR_BRIDGE_E2E_BLOCKED", "STATUT: BLOCKED", "STATUS: BLOCKED", "STATUT: BLOQUE", "UNKNOWN_REGISTRY_TASK", "DEPENDENCIES_NOT_DONE")):
        return "BLOQUE", _compact(last)
    if any(k in text for k in ("STATUT: VERIFIE", "STATUS: VERIFIED", "ETAPE VALIDEE", "BAZOR_BRIDGE_E2E_OK", "DELIVERED")):
        return "VERIFIE", _compact(last)
    if any(k in text for k in ("EN COURS", "RUNNING", "STATUS: START", "STATUT: START")):
        return "EN COURS", _compact(last)
    if str(data.get("state", "")).upper() == "CLOSED":
        return "VERIFIE", _compact(last)
    return "OUVERT", _compact(last)

def _compact(text, limit=150):
    text = " ".join((text or "").replace("\r", " ").replace("\n", " ").split())
    return text[:limit] + ("…" if len(text) > limit else "")

class Dashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("BAZOR • PROJETS DYNAMIQUES")
        self.root.geometry("1460x820")
        self.root.minsize(1080, 620)
        self.github_cache = {}
        self.github_last = 0.0
        self.github_refreshing = False
        self.refreshing = False
        self.rows = {}
        self._build()
        self.root.after(200, self.refresh)

    def _build(self):
        top = tk.Frame(self.root, bg="#10151d", padx=14, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="BAZOR • TABLEAU DES PROJETS", bg="#10151d", fg="white",
                 font=("Segoe UI", 19, "bold")).pack(side="left")
        tk.Label(top, text="v" + BUILD, bg="#10151d", fg="#6dc8ff",
                 font=("Consolas", 9, "bold")).pack(side="left", padx=(8, 18))
        self.summary = tk.Label(top, text="Analyse…", bg="#10151d", fg="#c5ced8",
                                font=("Segoe UI", 10))
        self.summary.pack(side="left")
        ttk.Button(top, text="↻ ACTUALISER", command=self.force_refresh).pack(side="right", padx=4)
        ttk.Button(top, text="↻ MAJ GIT --FF-ONLY", command=self.update_repo).pack(side="right", padx=4)
        ttk.Button(top, text="OUVRIR HUB", command=lambda: self.launch_by_id("hub")).pack(side="right", padx=4)

        info = tk.Frame(self.root, padx=14, pady=6)
        info.pack(fill="x")
        self.last_label = tk.Label(info, text="", anchor="w", font=("Segoe UI", 9))
        self.last_label.pack(side="left")
        tk.Label(info, text="Actualisation PC: 5 s • GitHub: 60 s • aucun ordre GitHub n'est exécuté",
                 anchor="e", fg="#667085", font=("Segoe UI", 9)).pack(side="right")

        headers = tk.Frame(self.root, bg="#e9edf2", padx=6, pady=5)
        headers.pack(fill="x", padx=10)
        widths = [7, 28, 32, 13, 20, 62, 13, 12]
        titles = ["PRIO", "PROJET", "SOUS-PROJET", "ETAT", "RUNTIME", "BLOCAGE / PROCHAINE ACTION", "LANCER", "TACHE"]
        for i, (title, width) in enumerate(zip(titles, widths)):
            tk.Label(headers, text=title, width=width, anchor="w", bg="#e9edf2",
                     font=("Segoe UI", 9, "bold")).grid(row=0, column=i, sticky="ew", padx=2)
        headers.grid_columnconfigure(5, weight=1)

        outer = tk.Frame(self.root)
        outer.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.body = tk.Frame(canvas)
        self.body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        for project in sorted(PROJECTS, key=lambda x: (PRIORITY_ORDER.get(x["priority"], 9), x["project"], x["sub"])):
            self._add_row(project)

        bottom = tk.Frame(self.root, padx=12, pady=7, bg="#10151d")
        bottom.pack(fill="x")
        self.message = tk.Label(bottom, text="Prêt.", bg="#10151d", fg="#c5ced8", anchor="w")
        self.message.pack(fill="x")

    def _add_row(self, project):
        row = tk.Frame(self.body, bd=0, padx=5, pady=4)
        row.pack(fill="x")
        row.grid_columnconfigure(5, weight=1)
        prio = tk.Label(row, text=project["priority"], width=7, anchor="w", font=("Segoe UI", 9, "bold"))
        name = tk.Label(row, text=project["project"], width=28, anchor="w", font=("Segoe UI", 9, "bold"))
        sub = tk.Label(row, text=project["sub"], width=32, anchor="w", justify="left")
        status = tk.Label(row, text="…", width=13, anchor="w", font=("Segoe UI", 9, "bold"))
        runtime = tk.Label(row, text="…", width=20, anchor="w")
        detail = tk.Label(row, text=project["next"], anchor="w", justify="left", wraplength=500)
        prio.grid(row=0, column=0, sticky="nw", padx=2)
        name.grid(row=0, column=1, sticky="nw", padx=2)
        sub.grid(row=0, column=2, sticky="nw", padx=2)
        status.grid(row=0, column=3, sticky="nw", padx=2)
        runtime.grid(row=0, column=4, sticky="nw", padx=2)
        detail.grid(row=0, column=5, sticky="ew", padx=4)

        launch_path = _find_launcher(project)
        b_launch = ttk.Button(row, text="▶ LANCER", command=lambda pid=project["id"]: self.launch_by_id(pid))
        if not launch_path:
            b_launch.state(["disabled"])
        b_launch.grid(row=0, column=6, padx=3, sticky="n")

        b_task = ttk.Button(row, text="↗ TACHE", command=lambda pid=project["id"]: self.open_task(pid))
        if not project.get("repo"):
            b_task.state(["disabled"])
        b_task.grid(row=0, column=7, padx=3, sticky="n")
        ttk.Separator(self.body, orient="horizontal").pack(fill="x", pady=1)
        self.rows[project["id"]] = {
            "project": project, "status": status, "runtime": runtime, "detail": detail,
            "launch": b_launch,
        }

    def _project(self, pid):
        return next((x for x in PROJECTS if x["id"] == pid), None)

    def force_refresh(self):
        self.github_last = 0
        self.refresh()

    def refresh(self):
        if self.refreshing:
            return
        self.refreshing = True
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        now = time.time()
        if (now - self.github_last) >= REFRESH_GITHUB_SECONDS and not self.github_refreshing:
            self.github_refreshing = True
            threading.Thread(target=self._github_worker, daemon=True).start()
        snapshots = []
        for p in PROJECTS:
            healths = p.get("health") or []
            checks = [_http_ok(u) for u in healths]
            runtime_ok = bool(checks) and all(checks)
            proc_ok = _process_present(p.get("process")) if p.get("process") else False
            if runtime_ok:
                runtime = "ONLINE"
            elif proc_ok:
                runtime = "PROCESSUS ACTIF"
            elif healths or p.get("process"):
                runtime = "ARRETE / HS"
            else:
                runtime = "—"

            gh_status, gh_detail = _github_status(self.github_cache.get(p["id"]))
            forced = p.get("forced_status")
            if forced:
                status = forced
            elif runtime_ok and gh_status == "BLOQUE":
                status = "PARTIEL"
            elif runtime_ok:
                status = "ACTIF"
            elif gh_status:
                status = gh_status
            elif proc_ok:
                status = "ACTIF"
            elif p["id"] == "master":
                status = "REFERENCE"
            else:
                status = "INCONNU"

            detail = p["next"]
            if gh_detail and status in ("BLOQUE", "PARTIEL", "VERIFIE", "EN COURS"):
                detail = gh_detail
            snapshots.append((p["id"], status, runtime, detail, _find_launcher(p) is not None))
        self.root.after(0, lambda: self._apply(snapshots))

    def _github_worker(self):
        targets = [p for p in PROJECTS if p.get("repo") and p.get("issue")]
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                future_map = {pool.submit(_gh_json, p): p["id"] for p in targets}
                for future in concurrent.futures.as_completed(future_map):
                    pid = future_map[future]
                    try:
                        self.github_cache[pid] = future.result()
                    except Exception:
                        self.github_cache[pid] = None
            self.github_last = time.time()
        finally:
            self.github_refreshing = False
            try:
                self.root.after(0, self.refresh)
            except Exception:
                pass

    def _apply(self, snapshots):
        counts = {}
        for pid, status, runtime, detail, launch_ok in snapshots:
            row = self.rows.get(pid)
            if not row:
                continue
            row["status"].config(text=status, fg=STATUS_COLOR.get(status, "#667085"))
            row["runtime"].config(text=runtime)
            row["detail"].config(text=detail)
            if launch_ok:
                row["launch"].state(["!disabled"])
            else:
                row["launch"].state(["disabled"])
            counts[status] = counts.get(status, 0) + 1
        self.summary.config(
            text=f"{counts.get('ACTIF',0)} actifs · {counts.get('VERIFIE',0)} verifies · "
                 f"{counts.get('PARTIEL',0)+counts.get('BLOQUE',0)} a traiter"
        )
        self.last_label.config(text="Derniere actualisation : " + time.strftime("%H:%M:%S"))
        self.refreshing = False
        self.root.after(REFRESH_LOCAL_MS, self.refresh)

    def launch_by_id(self, pid):
        p = self._project(pid)
        if not p:
            return
        launcher = _find_launcher(p)
        if not launcher:
            self.message.config(text=f"{p['project']} : aucun lanceur certifie trouve.")
            return
        self.message.config(text=f"{p['project']} : mise a jour sure puis lancement…")
        def worker():
            ok, note = _safe_pull()
            try:
                _run_launcher(launcher)
                msg = f"{p['project']} lance via {launcher.name}"
                if not ok:
                    msg += " • git pull non applique (modifs locales ou reseau), fichiers locaux preserves"
            except Exception as exc:
                msg = f"{p['project']} : lancement bloque ({type(exc).__name__})"
            self.root.after(0, lambda: self.message.config(text=msg))
            self.root.after(1500, self.refresh)
        threading.Thread(target=worker, daemon=True).start()

    def open_task(self, pid):
        p = self._project(pid)
        if not p or not p.get("repo"):
            return
        if p.get("issue"):
            url = f"https://github.com/{p['repo']}/issues/{p['issue']}"
        else:
            url = f"https://github.com/{p['repo']}"
        webbrowser.open(url)

    def update_repo(self):
        self.message.config(text="Mise a jour Git --ff-only…")
        def worker():
            ok, note = _safe_pull()
            msg = "Depot BAZOR a jour." if ok else "Mise a jour non appliquee; modifications locales preservees."
            if note:
                msg += " " + _compact(note, 180)
            self.root.after(0, lambda: self.message.config(text=msg))
            self.github_last = 0
            self.root.after(500, self.refresh)
        threading.Thread(target=worker, daemon=True).start()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    Dashboard().run()
