"""BAZOR v24: audit de compatibilite en lecture seule, sans activation des fournisseurs IA.

Ce programme ne modifie jamais les installations Core / AI Room existantes.
Il restaure la sauvegarde dans un dossier temporaire distinct pour controler
son integrite. Le rapport public ne contient aucun chemin, contenu ou secret.
Un succes ici ne vaut PAS autorisation de deploiement ni certification runtime.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.request
import zipfile

EXPECTED_BRIDGE_SHA16 = "C21AEDF6ACD2AC72"
REQUIRED_STAGE = (
    "pc-relay/bazor_bridge.py",
    "pc-relay/bazor_pc_relay_v3.py",
    "pc-relay/bazor_security.py",
    "pc-relay/mammouth_client.py",
    "pc-relay/bazor_multiai_oneclick.py",
    "room-payload/v2.4/app/room_v2_server.py",
)
CRITICAL_BACKUP = (
    "Core/DEMARRER_BAZOR_PC_RELAY.cmd",
    "AI_Room/DEMARRER_BAZOR_AI_ROOM.cmd",
    "AI_Room/chat_history.json",
    "AI_Room/control.json",
    "AI_Room/projects.json",
    "AI_Room/state.json",
)
MAX_UNPACKED = 2 * 1024**3
PUBLIC_STATES = {
    "OK", "ABSENT", "BLOCKED", "INVALID", "NOT_TESTED", "RESPONDS",
    "HAS_MODELS", "NO_MODELS", "BACKUP_CHANGED", "RESTORE_SIMULATED",
    "LOW_DISK", "PATCH_MISMATCH", "SYNTAX_ERRORS", "READY_FOR_ISOLATED_TEST",
}


def sha16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16].upper()


def safe_member(info: zipfile.ZipInfo) -> bool:
    raw = info.filename
    if not raw or "\\" in raw or raw.startswith("/"):
        return False
    path = PurePosixPath(raw)
    if ".." in path.parts or path.is_absolute() or ":" in path.parts[0]:
        return False
    mode = info.external_attr >> 16
    return not stat.S_ISLNK(mode)


def restore_test(archive: Path, work: Path, current_core: Path, current_room: Path) -> dict:
    """Restore *only* to a temporary directory; no side effects on live services."""
    result = {"backup": "BLOCKED", "entries": 0, "live_data_drift": False}
    if not archive.is_file():
        result["backup"] = "ABSENT"
        return result
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            names = {x.filename.rstrip("/") for x in entries}
            if (not entries or len(names) != len(entries)
                    or any(not safe_member(x) for x in entries)
                    or not set(CRITICAL_BACKUP).issubset(names)):
                result["backup"] = "INVALID"
                return result
            size = sum(x.file_size for x in entries if not x.is_dir())
            if size > MAX_UNPACKED:
                result["backup"] = "BLOCKED"
                return result
            work.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(work).free < size + 32 * 1024**2:
                result["backup"] = "LOW_DISK"
                return result
            with tempfile.TemporaryDirectory(prefix="bazor_restore_", dir=work) as temporary:
                destination = Path(temporary)
                for member in entries:
                    target = destination.joinpath(*PurePosixPath(member.filename).parts)
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(member) as src, target.open("xb") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                    if target.stat().st_size != member.file_size:
                        result["backup"] = "INVALID"
                        return result
                # Compare only fixed known files. A live change is a reason to
                # take a *new* backup, never a reason to overwrite live data.
                drift = False
                for label, root in (("Core", current_core), ("AI_Room", current_room)):
                    for relative in (("DEMARRER_BAZOR_PC_RELAY.cmd",) if label == "Core"
                                     else ("DEMARRER_BAZOR_AI_ROOM.cmd", "chat_history.json",
                                           "control.json", "projects.json", "state.json")):
                        live, saved = root / relative, destination / label / relative
                        # An absent live file is also drift: never allow a stale
                        # backup to replace a changed or removed installation.
                        if (not live.is_file() or not saved.is_file()
                                or sha16(live) != sha16(saved)):
                            drift = True
                result.update(backup="RESTORE_SIMULATED", entries=len(entries),
                              live_data_drift=drift)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, ValueError):
        result["backup"] = "INVALID"
    return result


def stage_test(stage: Path, expected_hash: str = EXPECTED_BRIDGE_SHA16) -> dict:
    result = {"stage": "BLOCKED", "python_files": 0, "syntax_errors": 0,
              "patch_hash16": "-", "stage_missing": 0}
    if not stage.is_dir():
        result["stage"] = "ABSENT"
        return result
    missing = [name for name in REQUIRED_STAGE if not (stage / name).is_file()]
    result["stage_missing"] = len(missing)
    if missing:
        return result
    result["patch_hash16"] = sha16(stage / REQUIRED_STAGE[0])
    if result["patch_hash16"] != expected_hash:
        result["stage"] = "PATCH_MISMATCH"
        return result
    # Parse, but NEVER import or execute staged code during preflight.
    scripts = [p for p in stage.rglob("*.py")
               if p.is_file() and len(p.relative_to(stage).parts) < 9][:250]
    result["python_files"] = len(scripts)
    for script in scripts:
        try:
            if script.stat().st_size > 2_000_000:
                raise ValueError("script_too_large")
            ast.parse(script.read_text(encoding="utf-8-sig"), filename="staged.py")
        except (OSError, UnicodeError, SyntaxError, ValueError):
            result["syntax_errors"] += 1
    result["stage"] = "SYNTAX_ERRORS" if result["syntax_errors"] else "OK"
    return result


def json_files_test(room: Path) -> dict:
    states = {}
    for name in ("chat_history.json", "control.json", "projects.json", "state.json"):
        path = room / name
        if not path.is_file():
            states[name] = "ABSENT"
            continue
        try:
            with path.open(encoding="utf-8-sig") as reader:
                json.load(reader)
            states[name] = "OK"
        except (OSError, UnicodeError, ValueError):
            states[name] = "INVALID"
    return states


def probe(url: str, models: bool = False) -> str:
    # Fixed local addresses, no proxy, no requests to user-controlled URLs.
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=2) as response:
            if not 200 <= response.status < 300:
                return "BLOCKED"
            raw = response.read(65537)
            if len(raw) > 65536:
                return "BLOCKED"
            obj = json.loads(raw.decode("utf-8"))
            if not isinstance(obj, dict):
                return "BLOCKED"
            if models:
                names = obj.get("models")
                return "HAS_MODELS" if isinstance(names, list) and bool(names) else "NO_MODELS"
            # A bare HTTP 200 or arbitrary JSON must never pass as BAZOR health.
            return "RESPONDS" if obj.get("ok") is True else "BLOCKED"
    except (OSError, ValueError, UnicodeError):
        return "BLOCKED"


def latest(directory: Path, pattern: str, folders: bool = False) -> Path | None:
    matches = [p for p in directory.glob(pattern)
               if p.is_dir() if folders] if folders else [p for p in directory.glob(pattern) if p.is_file()]
    return max(matches, key=lambda p: p.stat().st_mtime, default=None)


def audit(local: Path, stage: Path | None = None, archive: Path | None = None,
          expected_hash: str = EXPECTED_BRIDGE_SHA16) -> dict:
    core, room = local / "BAZOR" / "Core", local / "BazorAIROOM"
    stage = stage or latest(local / "BAZOR" / "Staging", "multiia_v24_*", folders=True)
    archive = archive or latest(local / "BAZOR" / "Backups", "PRE_MULTI_IA_*.zip")
    report = {
        "schema": "bazor_compat_v1", "mode": "READ_ONLY_NO_PAID_API",
        "core_launcher": "OK" if (core / "DEMARRER_BAZOR_PC_RELAY.cmd").is_file() else "ABSENT",
        "room_launcher": "OK" if (room / "DEMARRER_BAZOR_AI_ROOM.cmd").is_file() else "ABSENT",
        "room_data": json_files_test(room),
        "stage": stage_test(stage, expected_hash) if stage else {"stage": "ABSENT"},
        "restore": restore_test(archive, local / "BAZOR" / "Reports", core, room)
                   if archive else {"backup": "ABSENT"},
        "health": {
            "core_8775": probe("http://127.0.0.1:8775/api/v1/health"),
            "room_8765": probe("http://127.0.0.1:8765/api/status"),
            "ollama_11434": probe("http://127.0.0.1:11434/api/tags", models=True),
        },
    }
    all_json = all(v == "OK" for v in report["room_data"].values())
    passed = (report["core_launcher"] == report["room_launcher"] == "OK"
              and all_json and report["stage"].get("stage") == "OK"
              and report["restore"].get("backup") == "RESTORE_SIMULATED"
              and not report["restore"].get("live_data_drift")
              and report["health"]["core_8775"] == "RESPONDS"
              and report["health"]["room_8765"] == "RESPONDS"
              and report["health"]["ollama_11434"] == "HAS_MODELS")
    report["gate"] = "READY_FOR_ISOLATED_TEST" if passed else "BLOCKED"
    report["deployment"] = "NEVER_PERFORMED"
    report["runtime_certified"] = False
    return report


def public_summary(report: dict) -> str:
    # Fixed vocabulary only; never print raw launchers, paths, JSON or exceptions.
    def state(value: str) -> str:
        return value if value in PUBLIC_STATES else "BLOCKED"
    stage, restore = report["stage"], report["restore"]
    h = report["health"]
    return "\n".join((
        "[BAZOR-COMPAT-PREFLIGHT]",
        "GATE: " + state(report["gate"]),
        "STAGE: " + state(stage["stage"]),
        "STAGE_PYTHON_FILES: " + str(int(stage.get("python_files", 0))),
        "STAGE_SYNTAX_ERRORS: " + str(int(stage.get("syntax_errors", 0))),
        "BACKUP: " + state(restore["backup"]),
        "BACKUP_ENTRIES: " + str(int(restore.get("entries", 0))),
        "LIVE_DATA_CHANGED: " + ("YES" if restore.get("live_data_drift") else "NO"),
        "CORE_8775: " + state(h["core_8775"]),
        "ROOM_8765: " + state(h["room_8765"]),
        "OLLAMA_11434: " + state(h["ollama_11434"]),
        "DEPLOYMENT: NEVER_PERFORMED",
        "RUNTIME_CERTIFIED: NO",
        "NEXT: isolated runtime smoke + verified rollback required before install",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description="BAZOR preflight sans installation ni API payante")
    parser.add_argument("--localappdata", type=Path, default=Path(
        os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"))
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--public-only", action="store_true")
    args = parser.parse_args()
    result = audit(args.localappdata, args.stage, args.archive)
    print(public_summary(result))
    if not args.public_only:
        path = args.localappdata / "BAZOR" / "Reports" / "compat_preflight_latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Rapport local enregistre sous BAZOR/Reports/compat_preflight_latest.json")
    return 0 if result["gate"] == "READY_FOR_ISOLATED_TEST" else 2


if __name__ == "__main__":
    raise SystemExit(main())
