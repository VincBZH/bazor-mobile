# -*- coding: utf-8 -*-
"""Emergency stop signal for BAZOR PC Cleaner Ultimate (does not kill other apps)."""
import os
import time
import tkinter as tk
from pathlib import Path

DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "BazorPCCleaner" / "data"
STOP_FILE = DATA / "PANIC.stop"
ICON = Path(__file__).with_name("BAZOR_PC_CLEANER.ico")


def panic():
    DATA.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text("PANIC " + time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    status.config(text="ARRÊT DEMANDÉ — les opérations en cours s'interrompent.", fg="#ff788e")
    btn.config(state="disabled", text="ARRÊT DEMANDÉ")
    root.after(1200, root.destroy)


root = tk.Tk()
root.title("BAZOR PC CLEANER ULTIMATE — PANIC")
root.resizable(False, False)
root.configure(bg="#061018")
root.attributes("-topmost", True)
root.geometry("430x190")
try:
    root.iconbitmap(default=str(ICON))
except Exception:
    pass

tk.Label(root, text="BAZOR // EMERGENCY STOP", bg="#061018", fg="#ff4567",
         font=("Segoe UI", 14, "bold")).pack(pady=(20, 8))
status = tk.Label(root, text="Arrête uniquement BAZOR Cleaner.", bg="#061018", fg="#86a7ba",
                  font=("Segoe UI", 9))
status.pack()
btn = tk.Button(root, text="PANIC — ARRÊT IMMÉDIAT", command=panic,
                 bg="#35111a", fg="white", activebackground="#ff4567",
                 relief="flat", bd=0, font=("Segoe UI", 12, "bold"),
                 cursor="hand2", padx=22, pady=12)
btn.pack(pady=18)
root.mainloop()
