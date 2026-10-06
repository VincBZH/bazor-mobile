"""Read-only Windows logon/startup inventory for BAZOR. No service/process change."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

BAZOR = re.compile(r"bazor|bazorairoom|wii[ _-]*ai[ _-]*bridge", re.I)
RUN_KEYS = (r"Software\Microsoft\Windows\CurrentVersion\Run",
            r"Software\Microsoft\Windows\CurrentVersion\RunOnce")


def looks_bazor(*values: object) -> bool:
    return any(BAZOR.search(str(value or "")) for value in values)


def record(kind: str, identity: str, status: str, detail: dict) -> dict:
    return {"kind": kind, "id": hashlib.sha256((kind + "\0" + identity).encode("utf-8")).hexdigest()[:12],
            "name": identity, "status": status, "private": detail}


def registry_entries(items: list, coverage: list) -> None:
    import winreg
    for hive_name, hive in (("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE)):
        for key_name in RUN_KEYS:
            for view_name, view in (("64", winreg.KEY_WOW64_64KEY), ("32", winreg.KEY_WOW64_32KEY)):
                try:
                    with winreg.OpenKey(hive, key_name, 0, winreg.KEY_READ | view) as key:
                        index = 0
                        while True:
                            try:
                                name, command, value_type = winreg.EnumValue(key, index)
                            except OSError:
                                break
                            index += 1
                            if looks_bazor(name, command):
                                identity = f"{hive_name} {key_name.rsplit(chr(92), 1)[-1]} [{view_name}] {name}"
                                items.append(record("REGISTRY", identity, "PRÉSENT",
                                                    {"hive": hive_name, "key": key_name, "view": view_name,
                                                     "value": name, "command": str(command), "type": value_type}))
                except FileNotFoundError:
                    continue
                except OSError:
                    coverage.append(f"REGISTRY_{hive_name}_{view_name}_INCOMPLET")


def startup_folders(items: list, coverage: list) -> None:
    folders = (("USER", Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"),
               ("ALL_USERS", Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"))
    for label, folder in folders:
        if not (os.environ.get("APPDATA") if label == "USER" else os.environ.get("PROGRAMDATA")):
            coverage.append(f"STARTUP_{label}_INCOMPLET")
            continue
        try:
            for path in folder.iterdir():
                if looks_bazor(path.name):
                    items.append(record("STARTUP_FOLDER", f"{label} {path.name}", "PRÉSENT", {"path": str(path)}))
        except FileNotFoundError:
            continue
        except OSError:
            coverage.append(f"STARTUP_{label}_INCOMPLET")


def scheduled_tasks(items: list, coverage: list) -> None:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    tasks = system_root / "System32" / "Tasks"
    if os.environ.get("PROCESSOR_ARCHITEW6432"):
        tasks = system_root / "Sysnative" / "Tasks"
    if not tasks.is_dir():
        coverage.append("TASKS_INCOMPLET")
        return
    errors = []
    def onerror(error):
        errors.append(error)
    for directory, _, files in os.walk(tasks, onerror=onerror):
        for filename in files:
            path = Path(directory) / filename
            try:
                if path.stat().st_size > 1024 * 1024:
                    continue
                root = ET.parse(path).getroot()
                texts = [node.text or "" for node in root.iter()
                         if node.tag.rsplit("}", 1)[-1] in ("Command", "Arguments", "URI")]
                name = "\\" + str(path.relative_to(tasks)).replace(os.sep, "\\")
                if looks_bazor(name, *texts):
                    settings = [node.text for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "Enabled"]
                    status = "DÉSACTIVÉ" if settings and settings[-1] == "false" else "CONFIGURÉ"
                    items.append(record("SCHEDULED_TASK", name, status, {"xml": str(path)}))
            except (OSError, ET.ParseError, ValueError):
                errors.append(str(path))
    if errors:
        coverage.append("TASKS_PARTIEL")


def services(items: list, coverage: list) -> None:
    import winreg
    key_name = r"SYSTEM\CurrentControlSet\Services"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name) as parent:
            count, _, _ = winreg.QueryInfoKey(parent)
            for index in range(count):
                try:
                    name = winreg.EnumKey(parent, index)
                    with winreg.OpenKey(parent, name) as child:
                        def get(field):
                            try:
                                return winreg.QueryValueEx(child, field)[0]
                            except OSError:
                                return None
                        command, display, start = get("ImagePath"), get("DisplayName"), get("Start")
                        if looks_bazor(name, command, display):
                            status = "AUTOMATIQUE" if start == 2 else "AUTRE"
                            items.append(record("SERVICE", name, status,
                                                {"display": display, "image": command, "start": start}))
                except OSError:
                    coverage.append("SERVICES_PARTIEL")
    except OSError:
        coverage.append("SERVICES_INCOMPLET")


def sanitized(items: list, coverage: list) -> str:
    unique = {(item["kind"], item["id"]): item for item in items}
    lines = ["[DA-BAZOR-STARTUP-AUDIT]", "MODE: READ_ONLY", "CHANGES: ZERO",
             "RESULT: INVENTORY_ONLY", "SOURCES: RUN_KEYS, STARTUP_FOLDERS, SCHEDULED_TASKS, SERVICES",
             "COVERAGE: " + ("COMPLETE_FOR_LISTED_SOURCES" if not coverage else "PARTIAL"),
             "UNREADABLE: " + (",".join(sorted(set(coverage))) if coverage else "NONE"),
             "MATCHES: " + str(len(unique)), "ITEMS:"]
    for item in sorted(unique.values(), key=lambda x: (x["kind"], x["name"])):
        # Name alone can contain arbitrary private text: only expose category, fingerprint and state.
        lines.append(f"- {item['kind']} {item['id']} {item['status']}")
    lines += ["STARTUP_DISABLED: NO", "REBOOT_VERIFIED: NO", "PRIVATE_COMMANDS_OR_PATHS: NOT_INCLUDED"]
    return "\n".join(lines) + "\n"


def audit() -> tuple[list, list]:
    if os.name != "nt":
        raise RuntimeError("Windows requis pour cet inventaire")
    items, coverage = [], []
    registry_entries(items, coverage)
    startup_folders(items, coverage)
    scheduled_tasks(items, coverage)
    services(items, coverage)
    return items, coverage


def main() -> int:
    try:
        items, coverage = audit()
    except RuntimeError as exc:
        print(exc)
        return 2
    private_dir = Path(os.environ["LOCALAPPDATA"]) / "BAZOR" / "DaBazor" / "startup_audit"
    private_dir.mkdir(parents=True, exist_ok=True)
    (private_dir / "inventory_private.json").write_text(
        json.dumps({"items": items, "coverage": coverage}, ensure_ascii=False, indent=2), encoding="utf-8")
    safe_report = sanitized(items, coverage)
    report_path = Path(__file__).resolve().parent / "RAPPORT_DA_BAZOR_DEMARRAGE.txt"
    try:
        report_path.write_text(safe_report, encoding="utf-8")
    except OSError:
        report_path = private_dir / "RAPPORT_DA_BAZOR_DEMARRAGE.txt"
        report_path.write_text(safe_report, encoding="utf-8")
    print(safe_report)
    print("Rapport à transmettre : " + str(report_path))
    print("Inventaire détaillé privé conservé sur ce PC ; ne pas le publier sur GitHub.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
