"""Disable exactly four audited BAZOR startup entries; local backup and undo.

No shell, no registry edits, no service edits, no process termination. This is
bound to the fingerprints in Vincent's 2026-09-27 sanitized audit. All paths
and task definitions remain on the local Windows PC.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from startup_audit import audit, sanitized

EXPECTED = {
    ("SCHEDULED_TASK", "635de36d28df"),
    ("SCHEDULED_TASK", "8aa310dd7015"),
    ("STARTUP_FOLDER", "31f37c914c02"),
    ("STARTUP_FOLDER", "5234a8801824"),
}
KINDS = {"SCHEDULED_TASK", "STARTUP_FOLDER"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def task_enabled(xml_path: Path) -> bool:
    root = ET.fromstring(xml_path.read_bytes())
    enabled = [node.text for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "Enabled"]
    return not enabled or enabled[-1].strip().lower() != "false"


def task_definition_signature(raw: bytes) -> str:
    """Protect the task's actions and trigger schedule across schtasks rewrites.

    Windows schtasks materializes default Settings and Principal fields on a
    /Change call, so a whole-file hash cannot establish task identity.
    """
    root = ET.fromstring(raw)
    parts = []
    for node in root:
        if node.tag.rsplit("}", 1)[-1] not in ("Actions", "Triggers"):
            continue
        copy = ET.fromstring(ET.tostring(node))
        for parent in copy.iter():
            for child in list(parent):
                if child.tag.rsplit("}", 1)[-1] == "Enabled":
                    parent.remove(child)
        parts.append(ET.canonicalize(ET.tostring(copy, encoding="unicode"), strip_text=True))
    if not any("Actions" in part for part in parts):
        raise RuntimeError("TASK_ACTIONS_MISSING")
    return digest("\n".join(parts).encode("utf-8"))


def task_change(name: str, enable: bool) -> None:
    command = shutil.which("schtasks.exe")
    if not command:
        raise RuntimeError("SCHTASKS_ABSENT")
    proc = subprocess.run([command, "/Change", "/TN", name, "/ENABLE" if enable else "/DISABLE"],
                          capture_output=True, timeout=20, shell=False)
    if proc.returncode:
        raise RuntimeError("TASK_CHANGE_FAILED")


def planned(current: list[dict], prior: list[dict]) -> list[dict]:
    """Match audit identities AND local inventory bytes; reject new targets."""
    def index(entries):
        found = {}
        for item in entries:
            key = (item.get("kind"), item.get("id"))
            if key in found:
                raise RuntimeError("DUPLICATE_ID")
            found[key] = item
        return found
    now, before = index(current), index(prior)
    active = {k for k, v in now.items() if v.get("kind") in KINDS and v.get("status") != "DÉSACTIVÉ"}
    if active != EXPECTED or set(now) != EXPECTED or set(before) != EXPECTED:
        raise RuntimeError("AUDIT_CHANGED")
    for key in EXPECTED:
        if now[key] != before[key]:
            raise RuntimeError("AUDIT_CHANGED")
    return [now[key] for key in sorted(EXPECTED)]


def local_path(item: dict) -> Path:
    value = item["private"]
    if item["kind"] == "SCHEDULED_TASK":
        path = Path(value["xml"])
        root = Path(os.environ["SystemRoot"]) / "System32" / "Tasks"
        if os.environ.get("PROCESSOR_ARCHITEW6432"):
            root = Path(os.environ["SystemRoot"]) / "Sysnative" / "Tasks"
        expected_name = "\\" + str(path.relative_to(root)).replace(os.sep, "\\")
        if expected_name != item["name"]:
            raise RuntimeError("TASK_PATH_CHANGED")
    else:
        path = Path(value["path"])
        label, filename = item["name"].split(" ", 1)
        base = os.environ["APPDATA"] if label == "USER" else os.environ["PROGRAMDATA"] if label == "ALL_USERS" else ""
        root = Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if not base or path.parent != root or path.name != filename:
            raise RuntimeError("STARTUP_PATH_CHANGED")
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("ENTRY_NOT_REGULAR_FILE")
    return path


def backup_plan(items: list[dict], folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=False)
    records = []
    for number, item in enumerate(items):
        path = local_path(item)
        raw = path.read_bytes()
        copy = folder / f"entry_{number}.bin"
        with copy.open("xb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        records.append({"id": item["id"], "kind": item["kind"], "name": item["name"],
                        "source": str(path), "copy": copy.name, "sha256": digest(raw),
                        "was_enabled": task_enabled(path) if item["kind"] == "SCHEDULED_TASK" else True})
    manifest = {"schema": 1, "phase": "BACKED_UP", "records": records}
    atomic_json(folder / "manifest.json", manifest)
    return manifest


def apply(manifest: dict, folder: Path, change=task_change) -> None:
    manifest_path = folder / "manifest.json"
    manifest["phase"] = "APPLYING"
    atomic_json(manifest_path, manifest)
    try:
        for entry in manifest["records"]:
            path = Path(entry["source"])
            copy = folder / entry["copy"]
            if digest(copy.read_bytes()) != entry["sha256"]:
                raise RuntimeError("BACKUP_CHANGED")
            if entry["kind"] == "SCHEDULED_TASK":
                if digest(path.read_bytes()) != entry["sha256"] or not task_enabled(path):
                    raise RuntimeError("TASK_CHANGED")
                change(entry["name"], False)
                if task_enabled(path):
                    raise RuntimeError("TASK_STILL_ENABLED")
            else:
                if digest(path.read_bytes()) != entry["sha256"]:
                    raise RuntimeError("STARTUP_CHANGED")
                dest = folder / (entry["copy"] + ".moved")
                if dest.exists():
                    raise RuntimeError("BACKUP_COLLISION")
                os.replace(path, dest)
                if digest(dest.read_bytes()) != entry["sha256"]:
                    raise RuntimeError("MOVE_CHANGED")
        manifest["phase"] = "DISABLED"
        atomic_json(manifest_path, manifest)
    except BaseException:
        # Recovery inspects actual state, including an interrupted operation.
        restore(manifest, folder, change=change)
        raise


def restore(manifest: dict, folder: Path, change=task_change) -> None:
    errors = []
    for entry in reversed(manifest["records"]):
        path = Path(entry["source"])
        moved = folder / (entry["copy"] + ".moved")
        try:
            if entry["kind"] == "SCHEDULED_TASK":
                if not path.is_file():
                    raise RuntimeError("TASK_GONE")
                saved = (folder / entry["copy"]).read_bytes()
                if task_definition_signature(path.read_bytes()) != task_definition_signature(saved):
                    raise RuntimeError("TASK_DEFINITION_CHANGED")
                if entry["was_enabled"] and not task_enabled(path):
                    change(entry["name"], True)
                    if not task_enabled(path):
                        raise RuntimeError("TASK_NOT_RESTORED")
            elif moved.exists():
                if path.exists() or digest(moved.read_bytes()) != entry["sha256"]:
                    raise RuntimeError("STARTUP_CONFLICT")
                os.replace(moved, path)
            elif not path.is_file() or digest(path.read_bytes()) != entry["sha256"]:
                raise RuntimeError("STARTUP_MISSING_OR_CHANGED")
        except (OSError, RuntimeError):
            errors.append(entry["id"])
    manifest["phase"] = "RESTORE_INCOMPLETE" if errors else "RESTORED"
    atomic_json(folder / "manifest.json", manifest)
    if errors:
        raise RuntimeError("RESTORE_INCOMPLETE")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("disable", "restore"))
    args = parser.parse_args()
    if os.name != "nt":
        print("Windows requis.")
        return 2
    audit_dir = Path(os.environ["LOCALAPPDATA"]) / "BAZOR" / "DaBazor" / "startup_audit"
    manifest_file = audit_dir / "inventory_private.json"
    report_path = Path(__file__).resolve().parent / "RAPPORT_DESACTIVATION_BAZOR.txt"
    def publish(lines):
        report = "\n".join(lines) + "\n"
        print(report)
        try:
            report_path.write_text(report, encoding="utf-8")
        except OSError:
            pass
    try:
        if args.mode == "disable":
            prior = json.loads(manifest_file.read_text(encoding="utf-8"))["items"]
            current, coverage = audit()
            items = planned(current, prior)
            folder = audit_dir / ("disable_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
            manifest = backup_plan(items, folder)
            apply(manifest, folder)
            publish(["[DA-BAZOR-STARTUP]", "RESULT: FOUR_ENTRIES_DISABLED",
                     "TASKS: 2; STARTUP_SHORTCUTS: 2; REGISTRY: UNCHANGED; SERVICES: UNCHANGED",
                     "BACKUP: LOCAL; REBOOT_VERIFIED: NO; COVERAGE: " + ("PARTIAL" if coverage else "COMPLETE_FOR_LISTED_SOURCES")])
            print("Dossier de restauration local : " + str(folder))
        else:
            folders = sorted(audit_dir.glob("disable_*/manifest.json"), reverse=True)
            if not folders:
                raise RuntimeError("NO_BACKUP")
            folder = folders[0].parent
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            if manifest["phase"] not in ("DISABLED", "APPLYING", "RESTORE_INCOMPLETE"):
                raise RuntimeError("NOT_DISABLED")
            restore(manifest, folder)
            publish(["[DA-BAZOR-STARTUP]", "RESULT: RESTORED_FROM_LOCAL_BACKUP"])
        return 0
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        known = {"AUDIT_CHANGED", "DUPLICATE_ID", "TASK_PATH_CHANGED", "STARTUP_PATH_CHANGED",
                 "ENTRY_NOT_REGULAR_FILE", "TASK_CHANGE_FAILED", "SCHTASKS_ABSENT", "BACKUP_CHANGED",
                 "TASK_CHANGED", "TASK_STILL_ENABLED", "STARTUP_CHANGED", "BACKUP_COLLISION",
                 "MOVE_CHANGED", "TASK_GONE", "TASK_DEFINITION_CHANGED", "TASK_NOT_RESTORED",
                 "STARTUP_CONFLICT", "STARTUP_MISSING_OR_CHANGED", "RESTORE_INCOMPLETE",
                 "NO_BACKUP", "NOT_DISABLED"}
        reason = str(exc) if str(exc) in known else "LOCAL_FILE_OR_PERMISSION_ERROR"
        publish(["[DA-BAZOR-STARTUP]", "RESULT: BLOCKED", "REASON: " + reason,
                 "REBOOT_VERIFIED: NO", "Conserver le dossier de sauvegarde local."])
        return 1


if __name__ == "__main__":
    sys.exit(main())
