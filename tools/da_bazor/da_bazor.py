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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OLLAMA = "http://127.0.0.1:11434"
ROOM = "http://127.0.0.1:8765"
CORE = "http://127.0.0.1:8775"
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


def inspect(probe=json_get) -> dict:
    """Read-only probes. A positive health check never certifies a deliverable."""
    result = {"ollama": "INDISPONIBLE", "models": [], "core": "NON_CERTIFIÉ", "room": "NON_CERTIFIÉ"}
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
    return result


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
    lines += ["Core : " + state["core"], "Room : " + state["room"], ""]
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
        root.title("Da Bazor · Ollama local")
        root.geometry("880x680")
        root.configure(bg="#101827")
        self.state = {"ollama": "SONDE_EN_ATTENTE", "models": [], "core": "NON_CERTIFIÉ", "room": "NON_CERTIFIÉ"}
        self.briefed = False
        tk.Label(root, text="✦  Da Bazor", bg="#101827", fg="#7ee2cb", font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=24, pady=(18, 2))
        today = datetime.now().astimezone().strftime("%d/%m/%Y")
        tk.Label(root, text=f"Aujourd'hui {today} · point de départ volontaire · aucun service BAZOR lancé", bg="#101827", fg="#b6c4d5", font=("Segoe UI", 10)).pack(anchor="w", padx=26)
        self.status = tk.Label(root, text="Lecture des services…", bg="#172339", fg="#fff", justify="left", anchor="w", padx=14, pady=12)
        self.status.pack(fill="x", padx=24, pady=14)
        tk.Label(root, text="À faire, dans l'ordre", bg="#101827", fg="#fff", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=24)
        board = tk.Frame(root, bg="#101827")
        board.pack(fill="x", padx=24)
        for number, title, action, missing in TASKS:
            tk.Label(board, text=f"{number}  {title}  ·  {action}\n       En attente : {missing}", bg="#1b2a42", fg="#e9f0f8", anchor="w", justify="left", padx=12, pady=5, wraplength=800).pack(fill="x", pady=3)
        tk.Label(root, text="Parler à Ollama local", bg="#101827", fg="#fff", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=24, pady=(12, 4))
        row = tk.Frame(root, bg="#101827")
        row.pack(fill="x", padx=24)
        self.entry = ttk.Entry(row)
        self.entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Envoyer", command=self.ask).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Actualiser", command=self.refresh).pack(side="left", padx=(8, 0))
        self.answer = tk.Text(root, height=5, bg="#1b2a42", fg="#e9f0f8", wrap="word", relief="flat", padx=10, pady=10)
        self.answer.pack(fill="both", expand=True, padx=24, pady=(8, 16))
        self.answer.insert("end", "Chef : surveille une réponse locale. Arbitre : essaie au plus un autre modèle léger si le premier échoue. Exécutant : Ollama, modèle affiché avec sa réponse. Aucun PowerShell ni IA payante.\n")
        self.refresh()

    def refresh(self):
        def work():
            state = inspect()
            self.root.after(0, lambda: self.update(state))
        threading.Thread(target=work, daemon=True).start()

    def update(self, state):
        self.state = state
        self.status.configure(text=f"Ollama : {state['ollama']} · modèle conseillé : {choose_model(state['models']) or 'aucun'}\nCore : {state['core']} · Room : {state['room']}  (sondes seules)")
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
