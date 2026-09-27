"""Da Bazor V0: local, opt-in dashboard and Ollama chat. Python standard library only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk
import webbrowser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OLLAMA = "http://127.0.0.1:11434"
ROOM = "http://127.0.0.1:8765"
CORE = "http://127.0.0.1:8775"
STUDIO = "http://127.0.0.1:8191"
COMFY = "http://127.0.0.1:8188"
MODELS = ("llama3.2:3b", "qwen2.5-coder:7b")
TASKS = (
    ("00", "Démarrage Windows", "Inventaire des démarrages et test après réouverture du PC", "PC Windows requis"),
    ("01", "Socle BAZOR", "Rollback réel après panne sur copies Windows, puis déploiement contrôlé", "Preuve Windows et autorisation locale requises"),
    ("02", "Sabrina simplifiée", "Vrai projet Repères, 8 cas P0, accès Sabrina et livraison", "Source Sites et essai Sabrina requis"),
    ("03", "Studio Expert", "Fidélité image, MP4 réel, contrôle visuel sur Studio 3.0.5", "Studio/ComfyUI du PC requis"),
    ("04", "Mission Locale", "Identifier la version finale et vérifier les exports", "Fichier faisant autorité requis"),
    ("05", "Room multi-IA", "Routage réel, superviseur, budget et reprise sur silence", "Connecteurs et preuves runtime requis"),
    ("06", "Windows Hello", "Autorisation native à usage unique pour actions typées", "Intégration Windows native non réalisée"),
)


def json_get(url: str, timeout: float = 1.5) -> object:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("HTTP non-200")
        return json.load(response)


def http_reachable(url: str, timeout: float = 1.5) -> bool:
    """A responsive page only means that a port answered, never a tested workflow."""
    with urlopen(Request(url, headers={"Accept": "text/html,application/json"}), timeout=timeout) as response:
        return response.status == 200


def inspect(probe=json_get, page_probe=http_reachable) -> dict:
    """Read-only probes. A positive health check never certifies a deliverable."""
    result = {"ollama": "INDISPONIBLE", "models": [], "core": "NON_CERTIFIÉ", "room": "NON_CERTIFIÉ",
              "studio": "NON_VÉRIFIÉ", "comfy": "NON_VÉRIFIÉ"}
    try:
        data = probe(OLLAMA + "/api/tags")
        models = data.get("models") if isinstance(data, dict) else None
        names = [x.get("name") for x in models if isinstance(x, dict) and isinstance(x.get("name"), str)] if isinstance(models, list) else []
        if names:
            result["ollama"] = "MODÈLES_DISPONIBLES"
            result["models"] = names
        else:
            result["ollama"] = "AUCUN_MODÈLE"
    except (OSError, ValueError, TypeError, KeyError):
        pass
    for label, url in (("core", CORE + "/api/v1/health"), ("room", ROOM + "/health")):
        try:
            data = probe(url)
            if isinstance(data, dict) and data.get("ok") is True:
                result[label] = "SONDE_OK_SEULEMENT"
            elif isinstance(data, dict) and data.get("ok") is False:
                result[label] = "ÉCHEC_DÉCLARÉ"
        except (OSError, ValueError, TypeError, KeyError):
            pass
    for label, url in (("studio", STUDIO + "/"), ("comfy", COMFY + "/system_stats")):
        try:
            result[label] = "PORT_RÉPOND_SEULEMENT" if page_probe(url) else "NON_VÉRIFIÉ"
        except (OSError, ValueError, TypeError, KeyError):
            pass
    return result


def allowed_destination(name: str, state: dict) -> str | None:
    """Only locally probed, fixed destinations may become clickable."""
    destinations = {
        "room": (ROOM, state.get("room") == "SONDE_OK_SEULEMENT"),
        "core": (CORE + "/api/v1/health", state.get("core") == "SONDE_OK_SEULEMENT"),
        "studio": (STUDIO, state.get("studio") == "PORT_RÉPOND_SEULEMENT"),
        "comfy": (COMFY, state.get("comfy") == "PORT_RÉPOND_SEULEMENT"),
    }
    url, ready = destinations.get(name, (None, False))
    return url if ready else None


def choose_model(names: list[str]) -> str | None:
    return next((name for name in MODELS if name in names), None)


def generate(prompt: str, model: str, timeout: float = 45) -> str:
    payload = json.dumps({"model": model, "stream": False, "prompt": prompt, "options": {"num_predict": 220}}).encode()
    req = Request(OLLAMA + "/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as response:
        data = json.load(response)
    if not isinstance(data, dict) or data.get("model") != model or not isinstance(data.get("response"), str) or not data["response"].strip():
        raise ValueError("Réponse ou identité du modèle non vérifiée")
    return data["response"].strip()


def local_answer(question: str, names: list[str], sender=generate) -> tuple[str, str]:
    """One local retry on a different available model; no cloud escalation."""
    available = [model for model in MODELS if model in names]
    if not available:
        return "BLOQUÉ", "Aucun modèle léger autorisé disponible. Vérifier Ollama."
    failures = []
    safe_context = "Tu es Ollama local dans Da Bazor. Réponds en français, brièvement. N'affirme aucune action Windows ou livraison sans preuve.\nQuestion : " + question[:1800]
    for model in available[:2]:
        try:
            return model, sender(safe_context, model)
        except (OSError, ValueError, TimeoutError, HTTPError, URLError):
            failures.append(model)
    return "BLOQUÉ", "Aucune réponse vérifiée. Modèles essayés : " + ", ".join(failures) + ". Diagnostic : vérifier service, mémoire et journal local Ollama."


def report(state: dict) -> str:
    lines = ["DA BAZOR — ÉTAT LOCAL", "Ollama : " + state["ollama"]]
    lines.append("Modèles détectés : " + (", ".join(state["models"]) if state["models"] else "aucun"))
    lines += ["Core : " + state["core"], "Room : " + state["room"],
              "Studio : " + state.get("studio", "NON_VÉRIFIÉ"),
              "ComfyUI : " + state.get("comfy", "NON_VÉRIFIÉ"), ""]
    lines.append("ORDRE DE TRAVAIL — aucun livrable certifié par ces sondes")
    for number, title, action, missing in TASKS:
        lines.append(f"{number} · {title} — {action}. BLOQUÉ : {missing}.")
    return "\n".join(lines)


def checkpoint(state: dict, directory: Path) -> dict:
    """Advance every independent diagnostic; record blockers without marking delivery."""
    results = []
    for number, title, action, missing in TASKS:
        finding = "SONDES_LOCALES_OK" if number == "01" and all(
            state[key] == "SONDE_OK_SEULEMENT" for key in ("core", "room")
        ) and state["ollama"] == "MODÈLES_DISPONIBLES" else "EN_ATTENTE"
        results.append({"id": number, "project": title, "diagnostic": finding,
                        "delivery": "NON_CERTIFIÉ", "next": action, "missing": missing})
    payload = {"schema": 1, "at_utc": datetime.now(timezone.utc).isoformat(),
               "services": state, "projects": results, "external_paid_calls": 0}
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "checkpoint.json"
    fd, temp_name = tempfile.mkstemp(prefix="checkpoint-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return payload


class Dashboard:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Da Bazor · menu des projets")
        width, height = 1080, 780
        root.geometry(f"{width}x{height}+{max(0, (root.winfo_screenwidth()-width)//2)}+{max(0, (root.winfo_screenheight()-height)//2)}")
        root.minsize(900, 650)
        root.configure(bg="#141116")
        self.state = {"ollama": "SONDE_EN_ATTENTE", "models": [], "core": "NON_CERTIFIÉ", "room": "NON_CERTIFIÉ",
                      "studio": "NON_VÉRIFIÉ", "comfy": "NON_VÉRIFIÉ"}
        self.briefed = False
        hero = tk.Frame(root, bg="#141116")
        hero.pack(fill="x", padx=22, pady=(10, 3))
        square = tk.Label(hero, text="DA\nBAZOR", bg="#cb172d", fg="white", width=10, height=4,
                          font=("Segoe UI", 20, "bold"), justify="center")
        square.pack(anchor="center")
        tk.Label(hero, text="LE MENU DES PROJETS  •  état vérifié sur ce PC à l'ouverture",
                 bg="#141116", fg="#f6dddd", font=("Segoe UI", 10, "bold")).pack(pady=(4, 0))
        self.status = tk.Label(root, text="Sondes locales en cours…", bg="#34212a", fg="#fff",
                               justify="left", anchor="w", padx=12, pady=8)
        self.status.pack(fill="x", padx=22, pady=(5, 8))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Bazor.TNotebook", background="#141116", borderwidth=0)
        style.configure("Bazor.TNotebook.Tab", background="#30242a", foreground="#fff", padding=(16, 9), font=("Segoe UI", 10, "bold"))
        style.map("Bazor.TNotebook.Tab", background=[("selected", "#bb1830")])
        self.tabs = ttk.Notebook(root, style="Bazor.TNotebook")
        self.tabs.pack(fill="both", expand=True, padx=22)
        self.operational = self.scroll_tab("Utilisables / à sonder")
        self.repair = self.scroll_tab("À réparer")
        self.parked = self.scroll_tab("En pause / écartés")
        self.map_frame = tk.Frame(self.tabs, bg="#201a21")
        self.tabs.add(self.map_frame, text="Carte mentale")
        self.build_cards()
        self.build_map()
        row = tk.Frame(root, bg="#141116")
        row.pack(fill="x", padx=22, pady=(7, 3))
        tk.Label(row, text="Ollama local", bg="#141116", fg="white", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 8))
        self.entry = ttk.Entry(row)
        self.entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Envoyer", command=self.ask).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Actualiser", command=self.refresh).pack(side="left", padx=(8, 0))
        self.answer = tk.Text(root, height=4, bg="#272029", fg="#f4e9ea", wrap="word", relief="flat", padx=10, pady=7)
        self.answer.pack(fill="x", padx=22, pady=(0, 12))
        self.answer.insert("end", "Une sonde HTTP indique seulement qu'un service répond. Chef = délai et suivi ; arbitre = repli entre deux modèles Ollama locaux.\n")
        self.refresh()

    def scroll_tab(self, title):
        outer = tk.Frame(self.tabs, bg="#201a21")
        self.tabs.add(outer, text=title)
        canvas = tk.Canvas(outer, bg="#201a21", highlightthickness=0)
        bar = ttk.Scrollbar(outer, command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg="#201a21")
        item = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(item, width=event.width))
        return inner

    def card(self, parent, title, text, accent="#c94350", key=None):
        box = tk.Frame(parent, bg="#30252d", highlightbackground=accent, highlightthickness=2)
        box.pack(fill="x", padx=15, pady=6)
        tk.Label(box, text=title, bg="#30252d", fg="#fff", font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(box, text=text, bg="#30252d", fg="#e8d8db", justify="left", anchor="w",
                 wraplength=930, font=("Segoe UI", 10)).pack(fill="x", padx=12)
        if key:
            button = ttk.Button(box, text="Ouvrir après sonde", state="disabled", command=lambda: self.open_local(key))
            button.pack(anchor="w", padx=12, pady=8)
            self.buttons[key] = button
        else:
            tk.Frame(box, height=8, bg="#30252d").pack()

    def build_cards(self):
        self.buttons = {}
        self.card(self.operational, "Ollama · 127.0.0.1:11434", "Conversation locale dans la zone du bas si un modèle autorisé répond. Une liste de modèles ne prouve pas encore une réponse.", key="ollama")
        self.card(self.operational, "BAZOR AI Room · 127.0.0.1:8765", "Interface de discussion. Parcours Room → Core → Ollama réussi le 27/09 sur copies Windows isolées ; vérifier l'instance actuelle.", key="room")
        self.card(self.operational, "BAZOR Core · 127.0.0.1:8775", "Orchestrateur et sécurité. Le bouton montre sa santé ; la sonde seule ne certifie pas le routage.", key="core")
        self.card(self.operational, "AI Simple Studio · 127.0.0.1:8191", "Interface image/vidéo. Port répondant ≠ média satisfaisant ; qualité et chaîne H3/Pony restent à qualifier.", key="studio")
        self.card(self.operational, "ComfyUI · 127.0.0.1:8188", "Moteur de génération derrière Studio. Son port répondant ne prouve ni modèle chargé ni rendu réussi.", key="comfy")
        self.card(self.repair, "P0 · Démarrage du PC", "Audit local : 2 tâches planifiées et 2 éléments du dossier Démarrage identifiés. Aucune entrée désactivée ; couverture partielle des tâches ; aucun redémarrage vérifié.")
        self.card(self.repair, "P0 · Room / Core / multi-IA", "Vérifier le parcours sur l'installation actuelle, le rollback réel, le pont Mammouth, les identités, les délais et les preuves de réponse. NoTrack a échoué en 401.")
        self.card(self.repair, "P0 · Studio Expert", "La vidéo MP4 de 8 images est une preuve technique, pas une qualité livrable. Pony XL exige un module AnimateDiff SDXL compatible ; M3d n'est pas exécuté. Corriger fidélité, H3 et analyse du média.")
        self.card(self.repair, "P0 · Sabrina / Repères", "Site source distinct ; simplification à trois questions et propagation des corrections du dossier. Tester l'accès de Sabrina et 8 parcours P0 avec des données fictives avant livraison.")
        self.card(self.repair, "P1 · Mission Locale / Windows Hello", "Identifier le compte rendu final et ses exports. L'autorisation native Windows Hello à usage court n'est pas intégrée dans ce pilote.")
        self.card(self.parked, "Router V3–V13 · versions parallèles", "V13 répondait sur 18795 le 26/09 ; cela prouve un ancien test de ports. Garder la fonction utile de routage/contexte, mais éviter d'en faire un second chef et un second démarrage.", "#a8774d")
        self.card(self.parked, "TOR · suspendu", "Un job a été créé et un dépôt inspecté, mais la chaîne ancienne était fragile et n'a révélé aucun workflow utile. Reprendre après le socle si un usage précis apparaît.", "#a8774d")
        self.card(self.parked, "Wii / PC / Switch · suspendu", "Le pont FileBus reste pertinent ; le jeu est reporté pour concentrer les preuves sur Core, Room et Studio.", "#a8774d")
        self.card(self.parked, "MODO Viewer et Festival · en pause", "Projets présents au registre ; pas de racine locale autorisée ni de test de bout en bout disponible dans cet audit.", "#a8774d")
        self.card(self.parked, "BRAIN A.1 · à refondre", "Son idée de mémoire structurée reste utile. La réunir avec l'index sûr et l'encyclopédie au lieu de créer une base divergente.", "#a8774d")
        self.card(self.parked, "Interaction téléphone · ABANDONNÉE (décision Vincent, 27/09)", "Déclasser Mobile/Command Center sur téléphone, découverte Wi-Fi/USB/ADB, BLE watchdog, BAZOR Montre, C28/Da Fit et relais de notifications : les coupures Bluetooth et l'éloignement rendent le lien trop peu fiable. Ne pas les relancer dans la feuille de route.", "#8a4949")
        self.card(self.parked, "FileBus et Core · composants conservés", "Le dépôt Wii contient aussi un bus GitHub sans téléphone. Garder les pièces de coordination utilisables sur PC ; le projet de jeu reste suspendu.", "#576e61")

    def build_map(self):
        tk.Button(self.map_frame, text="Lire l’encyclopédie des choix et abandons", bg="#cb172d", fg="white",
                  activebackground="#e13a51", activeforeground="white", relief="flat", pady=7,
                  command=lambda: webbrowser.open(Path(__file__).with_name("ENCYCLOPEDIE_REPRISE_20260927.md").as_uri())).pack(fill="x", padx=8, pady=5)
        canvas = tk.Canvas(self.map_frame, bg="#201a21", highlightthickness=0, scrollregion=(0, 0, 1250, 810))
        ybar = ttk.Scrollbar(self.map_frame, orient="vertical", command=canvas.yview)
        xbar = ttk.Scrollbar(self.map_frame, orient="horizontal", command=canvas.xview)
        canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        ybar.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        canvas.pack(fill="both", expand=True)
        nodes = {
            "da": (495, 25, "DA BAZOR\nmenu · preuves · priorités", "#bf1b34"),
            "room": (80, 195, "AI ROOM\n8765 · %LOCALAPPDATA%\\BazorAIROOM", "#53607a"),
            "core": (495, 195, "CORE + WATCHER\n8775 · BAZOR local / GitHub", "#53607a"),
            "studio": (910, 195, "STUDIO EXPERT\n8191 · dossier Studio local", "#53607a"),
            "ollama": (80, 395, "OLLAMA\n11434 · modèles locaux", "#386354"),
            "filebus": (495, 395, "FILEBUS / MAMMOUTH\n2 dépôts GitHub · pont à qualifier", "#765b45"),
            "comfy": (910, 395, "COMFYUI\n8188 · modèles / GPU", "#386354"),
            "sabrina": (80, 610, "REPÈRES / SABRINA\nsite distinct · accès à valider", "#765b45"),
            "knowledge": (495, 610, "ENCYCLOPÉDIE + REGISTRE\npreuves · versions · mémoire", "#765b45"),
            "mission": (910, 610, "MISSION LOCALE\ndocuments · livrable à identifier", "#765b45"),
        }
        edges = [("da", "room", "ouvre"), ("da", "core", "sonde"), ("da", "studio", "ouvre"),
                 ("room", "core", "tâches"), ("core", "ollama", "local"), ("core", "filebus", "handoff"),
                 ("studio", "comfy", "génération"), ("filebus", "knowledge", "traces"),
                 ("sabrina", "knowledge", "suivi"), ("mission", "knowledge", "références")]
        for a, b, label in edges:
            ax, ay = nodes[a][:2]; bx, by = nodes[b][:2]
            x1, y1 = ax+135, ay+60; x2, y2 = bx+135, by+60
            canvas.create_line(x1, y1, x2, y2, fill="#be9aa0", width=2, arrow="last")
            canvas.create_text((x1+x2)/2+12, (y1+y2)/2-12, text=label, fill="#eee", font=("Segoe UI", 9, "bold"))
        for x, y, label, color in nodes.values():
            canvas.create_rectangle(x, y, x+270, y+120, fill=color, outline="#f3d6da", width=2)
            canvas.create_text(x+135, y+60, text=label, fill="white", width=255, justify="center", font=("Segoe UI", 11, "bold"))
        canvas.create_text(620, 785, text="Flèches = rôle ou flux conçu ; seules les sondes et preuves affichées attestent l'état réel.", fill="#f2d4d8", font=("Segoe UI", 10))

    def open_local(self, name):
        if name == "ollama":
            if choose_model(self.state.get("models", [])):
                self.entry.focus_set()
            return
        url = allowed_destination(name, self.state)
        if url:
            webbrowser.open(url)

    def refresh(self):
        def work():
            state = inspect()
            self.root.after(0, lambda: self.update(state))
        threading.Thread(target=work, daemon=True).start()

    def update(self, state):
        self.state = state
        self.status.configure(text=f"SONDE ACTUELLE · Ollama : {state['ollama']} · modèle : {choose_model(state['models']) or 'aucun'}  |  Core : {state['core']}  |  Room : {state['room']}\nStudio : {state['studio']}  |  ComfyUI : {state['comfy']}   •   Aucun livrable certifié par ces sondes")
        for key, button in self.buttons.items():
            ready = bool(choose_model(state["models"])) if key == "ollama" else bool(allowed_destination(key, state))
            button.configure(state="normal" if ready else "disabled", text="Discuter ici" if key == "ollama" else "Ouvrir l'outil" if ready else "Hors ligne / non vérifié")
        if choose_model(state["models"]) and not self.briefed:
            self.briefed = True
            self.answer.insert("end", "\nChef : je demande à Ollama le programme du jour…\n")
            prompt = "Présente le programme d'aujourd'hui en trois priorités réalisables. Aucune tâche n'est déclarée livrée. Étapes connues : " + "; ".join(title + " : " + action for _, title, action, _ in TASKS)
            names = list(state["models"])
            def work():
                model, answer = local_answer(prompt, names)
                self.root.after(0, lambda: self.answer.insert("end", f"Programme du jour [{model}] : {answer}\n"))
            threading.Thread(target=work, daemon=True).start()

    def ask(self):
        question = self.entry.get().strip()
        if not question:
            return
        self.entry.delete(0, "end")
        self.answer.insert("end", "\nVous : " + question + "\nChef : attente de la réponse locale…\n")
        names = list(self.state["models"])
        def work():
            model, answer = local_answer(question, names)
            self.root.after(0, lambda: self.answer.insert("end", f"Exécutant [{model}] : {answer}\n"))
        threading.Thread(target=work, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description="Da Bazor V0 — aucun démarrage automatique")
    parser.add_argument("command", choices=("status", "run", "window"), nargs="?", default="window")
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "state") / "BAZOR" / "DaBazor")
    args = parser.parse_args()
    if args.command == "status":
        print(report(inspect()))
    elif args.command == "run":
        payload = checkpoint(inspect(), args.state_dir)
        print(f"{len(payload['projects'])} projets examinés ; 0 livraison certifiée ; 0 appel IA payant.")
        print("Compte rendu local : " + str(args.state_dir / "checkpoint.json"))
    else:
        root = tk.Tk()
        Dashboard(root)
        root.mainloop()


if __name__ == "__main__":
    main()
