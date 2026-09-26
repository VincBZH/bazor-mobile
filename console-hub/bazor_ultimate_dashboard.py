"""BAZOR ULTIMATE V0: surcouche de diagnostic du Hub Tkinter EXISTANT.

Ne lance ni ne répare les services. Démarrage sans --centralize : conserve
l'instance unique du Hub d'origine et son tableau de processus. Le test de
conversation n'est possible que par clic explicite.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

from bazor_console_hub import Hub
from bazor_diagnostics import Check, State, diagnose, test_local_chat

COLORS = {
    State.GREEN: "#18834d",
    State.YELLOW: "#916200",
    State.RED: "#bf293a",
    State.GRAY: "#5d6470",
}
LABELS = {"core": "Core · 8775", "room": "AI Room · 8765",
          "ollama": "Ollama · 11434", "link": "Liaison déclarée"}


class UltimateHub(Hub):
    def __init__(self):
        self.diag_queue = queue.Queue()
        self.diag_busy = False
        self.chat_busy = False
        super().__init__(centralize=False)
        self.root.title("BAZOR ULTIMATE — Centre de contrôle")
        self.root.geometry("1160x820")
        self.root.after(100, self._poll_diag_queue)
        self.root.after(1500, self.refresh_diagnostics)
        self.root.after(30000, self._periodic_diagnostics)

    def build_ui(self):
        super().build_ui()
        # Nouveau panneau avant l'ancienne liste, sans modifier la logique du Hub.
        panel = tk.LabelFrame(self.root, text="DIAGNOSTICS LOCAUX — API, sans génération",
                              padx=9, pady=6, bg="#f2f4f7", fg="#17212d",
                              font=("Segoe UI", 10, "bold"))
        panel.pack(fill="x", padx=10, pady=4, before=self.tree)
        header = tk.Frame(panel, bg="#f2f4f7")
        header.pack(fill="x", pady=(0, 5))
        self.diag_summary = tk.Label(header, text="GRIS · En attente du premier diagnostic",
                                     fg=COLORS[State.GRAY], bg="#f2f4f7",
                                     font=("Segoe UI", 10, "bold"))
        self.diag_summary.pack(side="left", padx=(0, 14))
        self.diag_button = ttk.Button(header, text="Actualiser les diagnostics",
                                      command=self.refresh_diagnostics)
        self.diag_button.pack(side="left", padx=4)
        self.chat_button = ttk.Button(header, text="Tester la conversation LOCALE",
                                      command=self.start_chat_test)
        self.chat_button.pack(side="left", padx=4)
        for i in range(4):
            panel.grid_columnconfigure(i, weight=1)
        row = tk.Frame(panel, bg="#f2f4f7")
        row.pack(fill="x")
        self.diag_labels = {}
        for i, (key, title) in enumerate(LABELS.items()):
            cell = tk.Frame(row, bg="#f2f4f7", padx=6, pady=3)
            cell.grid(row=0, column=i, sticky="nsew")
            row.grid_columnconfigure(i, weight=1, uniform="diag")
            tk.Label(cell, text=title, bg="#f2f4f7", fg="#17212d",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            state_label = tk.Label(cell, text="GRIS · Non vérifié", bg="#f2f4f7",
                                   fg=COLORS[State.GRAY], anchor="w", justify="left",
                                   wraplength=240, font=("Segoe UI", 9))
            state_label.pack(anchor="w", fill="x")
            self.diag_labels[key] = state_label
        self.chat_result = tk.Label(panel,
            text="Test de génération : non lancé (clic manuel uniquement ; ajoute un message à l'historique local).",
            bg="#f2f4f7", fg=COLORS[State.GRAY], anchor="w", justify="left",
            font=("Segoe UI", 9))
        self.chat_result.pack(fill="x", pady=(5, 0))
        # L'ancien tableau contrôle surtout processus/ports, pas le dialogue réel.
        self.tree.heading("status", text="ÉTAT HISTORIQUE (PORT)")

    def refresh_diagnostics(self):
        if self.diag_busy or self.stop_evt.is_set():
            return
        self.diag_busy = True
        self.diag_button.config(state="disabled")
        threading.Thread(target=self._diag_worker, daemon=True).start()

    def _diag_worker(self):
        try:
            self.diag_queue.put(("report", diagnose()))
        except Exception as exc:
            self.diag_queue.put(("report_error", type(exc).__name__))

    def start_chat_test(self):
        if self.chat_busy or self.stop_evt.is_set():
            return
        self.chat_busy = True
        self.chat_button.config(state="disabled")
        self.chat_result.config(text="Génération locale en cours…", fg=COLORS[State.GRAY])
        threading.Thread(target=self._chat_worker, daemon=True).start()

    def _chat_worker(self):
        try:
            self.diag_queue.put(("chat", test_local_chat()))
        except Exception as exc:
            self.diag_queue.put(("chat", Check("Conversation locale", State.GRAY,
                                                f"Test impossible ({type(exc).__name__})")))

    def _poll_diag_queue(self):
        try:
            while True:
                kind, payload = self.diag_queue.get_nowait()
                if kind == "report":
                    self.diag_busy = False
                    self.diag_button.config(state="normal")
                    self._show_report(payload)
                elif kind == "report_error":
                    self.diag_busy = False
                    self.diag_button.config(state="normal")
                    self.diag_summary.config(text=f"GRIS · Diagnostic impossible ({payload})",
                                             fg=COLORS[State.GRAY])
                elif kind == "chat":
                    self.chat_busy = False
                    self.chat_button.config(state="normal")
                    self.chat_result.config(text=f"{payload.state.value} · {payload.detail}",
                                             fg=COLORS[payload.state])
        except queue.Empty:
            pass
        if not self.stop_evt.is_set():
            self.root.after(100, self._poll_diag_queue)

    def _show_report(self, report: dict[str, Check]):
        overall = report["overall"]
        self.diag_summary.config(text=f"{overall.state.value} · BAZOR local",
                                 fg=COLORS[overall.state])
        for key, widget in self.diag_labels.items():
            item = report[key]
            widget.config(text=f"{item.state.value} · {item.detail}", fg=COLORS[item.state])

    def _periodic_diagnostics(self):
        if not self.stop_evt.is_set():
            self.refresh_diagnostics()
            self.root.after(30000, self._periodic_diagnostics)


if __name__ == "__main__":
    UltimateHub().run()
