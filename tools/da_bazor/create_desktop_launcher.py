"""Create a voluntary desktop launcher for this extracted Da Bazor folder."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def desktop_directory() -> Path:
    if os.name != "nt":
        raise OSError("Ce lanceur de bureau nécessite Windows")
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
        value, _ = winreg.QueryValueEx(key, "Desktop")
    path = Path(os.path.expandvars(value))
    if not path.is_dir():
        raise FileNotFoundError("Dossier Bureau Windows introuvable")
    return path


def launcher_content(python: Path, app: Path) -> str:
    for value in (str(python), str(app)):
        if any(character in value for character in ('%', '!', '\r', '\n', '"')):
            raise ValueError("Chemin incompatible avec un lanceur CMD ; ouvrir OUVRIR_DA_BAZOR.cmd dans le dossier extrait")
    command = subprocess.list2cmdline([str(python), str(app), "window"])
    return "@echo off\r\nsetlocal DisableDelayedExpansion\r\n" + command + "\r\nif errorlevel 1 pause\r\n"


def main() -> None:
    destination = desktop_directory() / "DA BAZOR.cmd"
    if destination.exists():
        raise FileExistsError("Un lanceur DA BAZOR existe déjà sur le Bureau ; rien n'a été remplacé")
    contents = launcher_content(Path(sys.executable).resolve(), Path(__file__).with_name("da_bazor.py").resolve())
    with destination.open("x", encoding="utf-8", newline="") as output:
        output.write(contents)
    print("Lanceur créé : " + str(destination))
    print("Il ouvre Da Bazor au centre du bureau seulement lorsque vous double-cliquez. Aucun démarrage automatique.")


if __name__ == "__main__":
    main()
