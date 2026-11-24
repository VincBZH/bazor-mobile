# -*- coding: utf-8 -*-
"""BAZOR PC Cleaner Ultimate: conservative, local-only Windows maintenance."""
import os
import sys
import json
import time
import shutil
import sqlite3
import threading
import queue
import subprocess
import ctypes
from ctypes import wintypes
from pathlib import Path
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

APP = "BAZOR PC CLEANER ULTIMATE"
VERSION = "4.0"
HOME = Path.home()
LOCAL = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
DATA = LOCAL / "BazorPCCleaner" / "data"
DB = DATA / "tracking.db"
STOP_FILE = DATA / "PANIC.stop"
DATA.mkdir(parents=True, exist_ok=True)
STOP = threading.Event()
UI = queue.Queue()

# Explicitly regenerable cache locations. Never include AI models, environments,
# CUDA toolkits, application data, Windows Installer, or personal folders.
CACHE_ROOTS = [
    (LOCAL / "pip" / "Cache" / "http-v2", "Cache pip HTTP", "Cache HTTP reconstructible; roues de paquets conservées."),
    (LOCAL / "pip" / "Cache" / "wheels", "Cache roues pip", "Roues de paquets mises en cache uniquement; paquets installés inchangés."),
    (LOCAL / "NVIDIA" / "DXCache", "Cache NVIDIA DX", "Shaders compilés, recréés automatiquement par le pilote."),
    (LOCAL / "NVIDIA" / "GLCache", "Cache NVIDIA GL", "Shaders compilés, recréés automatiquement par le pilote."),
    (LOCAL / "Temp", "Temporaires utilisateur anciens", "Uniquement fichiers temporaires de plus de 7 jours, déverrouillés."),
    (Path(os.environ.get("WINDIR", r"C:\Windows")) / "Temp", "Temporaires Windows anciens", "Uniquement fichiers temporaires de plus de 14 jours, accessibles et déverrouillés."),
]
TEMP_AGE = {"Temporaires utilisateur anciens": 7, "Temporaires Windows anciens": 14}


def connect_db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, ts TEXT, action TEXT, path TEXT, bytes INTEGER, result TEXT)")
    c.commit()
    return c


def record(action, path, size, result):
    try:
        with connect_db() as c:
            c.execute("INSERT INTO events(ts,action,path,bytes,result) VALUES(?,?,?,?,?)",
                      (datetime.now().isoformat(timespec="seconds"), action, str(path), int(size), result))
    except Exception:
        pass


def human(n):
    n = float(n)
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or unit == "To":
            return f"{n:.2f} {unit}" if unit != "o" else f"{int(n)} o"
        n /= 1024


def disk_state():
    out = []
    for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = Path(f"{d}:\\")
        if root.exists():
            try:
                u = shutil.disk_usage(root)
                out.append((str(root), u.total, u.free))
            except OSError:
                pass
    return out


def panic_requested():
    return STOP.is_set() or STOP_FILE.exists()


def locked_file(path):
    """Best-effort exclusive-open test on Windows; non-Windows fallback is conservative."""
    if os.name != "nt":
        return True
    try:
        k32 = ctypes.windll.kernel32
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        h = k32.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
        if h == ctypes.c_void_p(-1).value:
            return True
        k32.CloseHandle(h)
        return False
    except Exception:
        return True


def inventory(progress=None):
    rows = []
    for root, label, why in CACHE_ROOTS:
        if STOP.is_set(): break
        if not root.is_dir():
            continue
        total = count = eligible = 0
        cutoff = time.time() - TEMP_AGE.get(label, 0) * 86400
        try:
            for base, dirs, files in os.walk(root, topdown=True):
                dirs[:] = [d for d in dirs if d not in ("Quarantine", "quarantine")]
                for name in files:
                    if STOP.is_set(): break
                    p = Path(base) / name
                    try:
                        st = p.stat()
                        total += st.st_size; count += 1
                        if label not in TEMP_AGE or st.st_mtime < cutoff:
                            if not locked_file(p): eligible += st.st_size
                    except (OSError, PermissionError):
                        pass
                if progress and count and count % 1000 == 0:
                    progress(f"Analyse {label} : {count} fichiers")
                if STOP.is_set(): break
        except OSError:
            pass
        if count:
            risk = "TRÈS FAIBLE" if label in ("Cache pip HTTP", "Cache roues pip", "Cache NVIDIA DX", "Cache NVIDIA GL") else "FAIBLE — fichiers anciens seulement"
            rows.append({"path": str(root), "label": label, "reason": why, "size": total,
                         "eligible": eligible, "count": count, "risk": risk,
                         "safe": True, "age_days": TEMP_AGE.get(label, 0)})
    return rows


def clean_candidate(item):
    root = Path(item["path"]).resolve()
    allowed = [p.resolve() for p, _, _ in CACHE_ROOTS]
    if root not in allowed or not root.is_dir():
        return 0, "Refus : chemin hors périmètre autorisé"
    cutoff = time.time() - item.get("age_days", 0) * 86400
    freed = errors = 0
    for base, dirs, files in os.walk(root, topdown=False):
        if panic_requested(): break
        for name in files:
            if panic_requested(): break
            p = Path(base) / name
            try:
                st = p.stat()
                if item.get("age_days") and st.st_mtime >= cutoff:
                    continue
                if locked_file(p):
                    continue
                size = st.st_size
                p.unlink()
                freed += size
                record("DELETE_CACHE_FILE", p, size, "deleted")
            except (OSError, PermissionError):
                errors += 1
        for name in dirs:
            p = Path(base) / name
            try: p.rmdir()
            except OSError: pass
    return freed, f"{errors} fichier(s) ignoré(s) (verrouillés ou inaccessibles)" if errors else "Terminé"


def active_system():
    facts = []
    try:
        r = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        facts.append("Pilote NVIDIA : " + (next((x.strip() for x in r.stdout.splitlines() if "CUDA Version" in x), "détection indisponible")))
    except Exception:
        facts.append("Pilote NVIDIA : nvidia-smi indisponible")
    for path in (Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"),):
        if path.is_dir():
            versions = sorted(p.name for p in path.iterdir() if p.is_dir())
            facts.append("Toolkits CUDA installés : " + (", ".join(versions) if versions else "aucun"))
            facts.append("Aucune désinstallation CUDA n'est effectuée automatiquement.")
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=1) as r:
            facts.append("ComfyUI port 8188 : répond (moteur existant conservé; aucun second moteur lancé).")
    except Exception:
        facts.append("ComfyUI port 8188 : aucune réponse locale constatée; aucun moteur n'a été démarré.")
    return facts


class Cleaner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP} v{VERSION}")
        self.geometry("1040x700"); self.minsize(850, 560)
        self.configure(bg="#07131b")
        self.rows = []; self.busy = False
        self._style(); self._build()
        self.after(300, self._pump); self.after(2000, self._monitor)
        self.refresh_history()

    def _style(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background="#102635", fieldbackground="#102635", foreground="#eaf7ff", rowheight=27)
        s.configure("Treeview.Heading", background="#143346", foreground="#75f1ff")

    def _build(self):
        head = tk.Frame(self, bg="#07131b"); head.pack(fill="x", padx=18, pady=14)
        tk.Label(head, text="BAZOR", fg="#00ddff", bg="#07131b", font=("Segoe UI", 24, "bold")).pack(side="left")
        tk.Label(head, text=" PC CLEANER ULTIMATE  v4.0", fg="white", bg="#07131b", font=("Segoe UI", 18, "bold")).pack(side="left")
        self.disk_lbl = tk.Label(head, text="Disque : mesure…", fg="#8affdc", bg="#07131b", font=("Segoe UI", 10)); self.disk_lbl.pack(side="right")
        bar = tk.Frame(self, bg="#07131b"); bar.pack(fill="x", padx=18, pady=(0, 10))
        self.scan_btn = self._button(bar, "ANALYSER", self.scan, "#00ddff")
        self.clean_btn = self._button(bar, "NETTOYER ET OPTIMISER", self.clean, "#00f2a9")
        self.panic_btn = self._button(bar, "PANIC", self.panic, "#ff4567", side="right")
        self.status = tk.Label(self, text="Analyse locale uniquement — aucun appel IA/API.", fg="#86a7ba", bg="#07131b", anchor="w")
        self.status.pack(fill="x", padx=20, pady=(0, 6))
        cols = ("risk", "label", "size", "gain", "detail", "path")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        headers = {"risk":"Risque", "label":"Zone", "size":"Taille", "gain":"Récupérable sûr", "detail":"Détail", "path":"Chemin"}
        widths = {"risk":90, "label":180, "size":105, "gain":115, "detail":310, "path":360}
        for c in cols:
            self.tree.heading(c, text=headers[c]); self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=18, pady=5)
        self.system = tk.Text(self, height=5, bg="#0e2230", fg="#b9d8e7", relief="flat", wrap="word")
        self.system.pack(fill="x", padx=18, pady=(7, 4)); self.system.insert("end", "Contrôles de protection…")
        self.history = tk.Label(self, text="Historique : prêt", fg="#86a7ba", bg="#07131b", anchor="w")
        self.history.pack(fill="x", padx=20, pady=(3, 12))

    def _button(self, parent, text, cmd, color, side="left"):
        b = tk.Button(parent, text=text, command=cmd, bg="#102635", fg=color, activebackground="#143346",
                      activeforeground="white", bd=1, relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=10)
        b.pack(side=side, padx=(0, 8)); return b

    def scan(self):
        if self.busy: return
        STOP.clear()
        try:
            if STOP_FILE.exists(): STOP_FILE.unlink()
        except OSError: pass
        self.busy = True; self.status.config(text="Inventaire des caches temporaires explicitement régénérables…")
        self.system.delete("1.0", "end"); self.system.insert("end", "\n".join(active_system()))
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        try:
            rows = inventory(lambda s: UI.put(("status", s)))
            if panic_requested(): UI.put(("error", "Analyse interrompue par PANIC"))
            else: UI.put(("scan", rows))
        except Exception as e: UI.put(("error", str(e)))

    def clean(self):
        if self.busy: return
        STOP.clear()
        try:
            if STOP_FILE.exists(): STOP_FILE.unlink()
        except OSError: pass
        if not self.rows:
            self.scan(); self.status.config(text="Analyse en cours — relancez NETTOYER ET OPTIMISER après l'inventaire."); return
        selected = self.tree.selection()
        chosen = [self.rows[int(self.tree.item(i, "tags")[0])] for i in selected] if selected else [r for r in self.rows if r["safe"]]
        if not chosen: return
        risky = [x for x in chosen if x["label"] not in ("Cache pip HTTP", "Cache roues pip", "Cache NVIDIA DX", "Cache NVIDIA GL")]
        if risky:
            labels = "\n".join(f"• {x['label']} — {human(x['eligible'])}" for x in risky)
            if not messagebox.askyesno(APP + " — temporaires anciens", f"Confirmer aussi la suppression des fichiers anciens et déverrouillés ?\n\n{labels}\n\nLes caches pip/NVIDIA sont régénérables. Les temporaires ignorés restent intacts."):
                chosen = [x for x in chosen if x not in risky]
                if not chosen: return
        estimate = sum(x["eligible"] for x in chosen)
        if not messagebox.askyesno(APP, f"Supprimer définitivement les fichiers de cache listés ?\n\nGain maximum estimé : {human(estimate)}\nAucun modèle, environnement Python, CUDA, pilote, configuration ou donnée personnelle ne sera touché."):
            return
        self.busy = True; STOP.clear(); self.status.config(text="Nettoyage sécurisé en cours…")
        threading.Thread(target=self._clean_worker, args=(chosen,), daemon=True).start()

    def _clean_worker(self, chosen):
        total = 0
        for item in chosen:
            if STOP.is_set(): break
            freed, msg = clean_candidate(item); total += freed
            UI.put(("status", f"{item['label']} : {human(freed)} — {msg}"))
        UI.put(("cleaned", total))

    def panic(self):
        STOP.set()
        try: STOP_FILE.write_text("PANIC " + datetime.now().isoformat(), encoding="utf-8")
        except OSError: pass
        self.status.config(text="PANIC : arrêt demandé; aucun nouveau fichier ne sera traité.")

    def _monitor(self):
        try:
            info = " | ".join(f"{d} libre {human(f)} / {human(t)}" for d, t, f in disk_state())
            self.disk_lbl.config(text=info or "Aucun volume détecté")
        except Exception: pass
        self.after(10000, self._monitor)

    def refresh_history(self):
        try:
            with connect_db() as c:
                n, b = c.execute("SELECT COUNT(*), COALESCE(SUM(bytes),0) FROM events WHERE action='DELETE_CACHE_FILE'").fetchone()
            self.history.config(text=f"Historique des suppressions : {n} fichier(s), {human(b)} cumulés — journal local SQLite")
        except Exception: pass

    def _pump(self):
        try:
            while True:
                typ, data = UI.get_nowait()
                if typ == "status": self.status.config(text=data)
                elif typ == "scan":
                    self.rows = data; self.tree.delete(*self.tree.get_children())
                    for idx, r in enumerate(self.rows):
                        self.tree.insert("", "end", values=(r["risk"], r["label"], human(r["size"]), human(r["eligible"]), r["reason"], r["path"]), tags=(str(idx),))
                    self.status.config(text=f"Analyse terminée : {len(data)} zone(s) sûres. Les versions CUDA/modèles/données non classés sont préservés.")
                    self.busy = False
                elif typ == "cleaned":
                    self.busy = False; self.refresh_history()
                    free = shutil.disk_usage(Path.home().anchor).free
                    self.status.config(text=f"Nettoyage terminé : {human(data)} supprimés. Espace libre actuel sur le volume système : {human(free)}. Relancez l'analyse pour le bilan final.")
                    messagebox.showinfo(APP, f"Suppression terminée : {human(data)} récupérés réellement selon les tailles des fichiers supprimés.")
                elif typ == "error": self.busy = False; self.status.config(text="Erreur : " + data)
        except queue.Empty: pass
        self.after(150, self._pump)


if __name__ == "__main__":
    Cleaner().mainloop()
