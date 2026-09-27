"""Restore-after-partial-update rehearsal on a DISPOSABLE COPY of a local backup.

Never starts, stops, installs, patches or imports code from a live BAZOR
installation. Does not call a paid provider. A green result is NOT permission
to deploy: the real installer, rollback and Windows Hello remain untested.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

from bazor_compat_preflight import CRITICAL_BACKUP, MAX_UNPACKED, latest

MAX_ENTRIES = 10000
CHUNK = 1024 * 1024
MARKER = "BAZOR_ROLLBACK_SIM_ONLY.txt"
MUTATED = (
    "Core/DEMARRER_BAZOR_PC_RELAY.cmd",
    "AI_Room/DEMARRER_BAZOR_AI_ROOM.cmd",
)
PROTECTED = (
    "AI_Room/chat_history.json",
    "AI_Room/control.json",
    "AI_Room/projects.json",
    "AI_Room/state.json",
)


def _valid_archive(zipped: zipfile.ZipFile) -> tuple[list[zipfile.ZipInfo], int]:
    entries = zipped.infolist()
    if not entries or len(entries) > MAX_ENTRIES:
        raise ValueError("invalid_archive")
    seen, total = set(), 0
    present = set()
    for entry in entries:
        name = entry.filename
        if (not name or "\\" in name or name.startswith("/")
                or any(part in ("", ".", "..") or ":" in part or part.endswith((" ", "."))
                       for part in name.rstrip("/").split("/"))):
            raise ValueError("unsafe_archive_path")
        parts = name.rstrip("/").split("/")
        if not parts or parts[0] not in ("Core", "AI_Room"):
            raise ValueError("unexpected_archive_root")
        if stat.S_ISLNK(entry.external_attr >> 16):
            raise ValueError("archive_symlink")
        canonical = name.rstrip("/").casefold()
        if canonical in seen:
            raise ValueError("duplicate_archive_path")
        seen.add(canonical)
        if not entry.is_dir():
            total += entry.file_size
            present.add(name)
        if total > MAX_UNPACKED:
            raise ValueError("archive_too_large")
    if not set(CRITICAL_BACKUP).issubset(present):
        raise ValueError("critical_files_missing")
    return entries, total


def _extract(zipped: zipfile.ZipFile, entries: list[zipfile.ZipInfo],
             destination: Path) -> dict[str, str]:
    fingerprints = {}
    for entry in entries:
        path = destination.joinpath(*entry.filename.rstrip("/").split("/"))
        if entry.is_dir():
            path.mkdir(parents=True, exist_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with zipped.open(entry) as source, path.open("xb") as target:
            while True:
                block = source.read(CHUNK)
                if not block:
                    break
                digest.update(block)
                target.write(block)
        if path.stat().st_size != entry.file_size:
            raise ValueError("extracted_size_mismatch")
        fingerprints[entry.filename] = digest.hexdigest()
    return fingerprints


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def rehearse(archive: Path, reports: Path) -> dict:
    """The only mutations are under a fresh TemporaryDirectory in reports."""
    result = {
        "archive": "NOT_TESTED", "backup_entries": 0,
        "simulated_failure": "NOT_INJECTED", "rollback": "NOT_TESTED",
        "protected_data": "NOT_TESTED", "live_services": "NOT_TOUCHED",
        "paid_ai_calls": 0, "deployment": "SIMULATION_ONLY",
        "result": "BLOCKED",
    }
    if not archive.is_file():
        result["archive"] = "ABSENT"
        return result
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries, total = _valid_archive(zipped)
            if zipped.testzip() is not None:
                result["archive"] = "INVALID_CRC"
                return result
            result["archive"] = "CRC_OK"
            result["backup_entries"] = len(entries)
            reports.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(reports).free < total + 128 * 1024**2:
                result["archive"] = "LOW_DISK"
                return result
            with tempfile.TemporaryDirectory(prefix="bazor_rollback_sim_", dir=reports) as tmp:
                workspace = Path(tmp)
                target = workspace / "INSTALLATION_FICTIVE"
                target.mkdir()
                baseline = _extract(zipped, entries, target)
                if not all(item in baseline for item in MUTATED + PROTECTED):
                    raise ValueError("missing_critical_fingerprints")
                # Rehearse a partially applied update and a failure WITHOUT
                # running either the backup's or the candidate's launchers.
                for item in MUTATED:
                    (target / item).write_bytes(b"INCOMPLETE_SIMULATED_UPDATE\n")
                (target / "Core" / MARKER).write_text(
                    "DISPOSABLE SIMULATION ONLY\n", encoding="ascii")
                result["simulated_failure"] = "INJECTED"
                if all(_file_hash(target / item) == baseline[item] for item in MUTATED):
                    raise ValueError("update_not_injected")
                # Roll back only the disposable sandbox. Remove stray files,
                # then restore the complete snapshot (not just launchers).
                shutil.rmtree(target)
                target.mkdir()
                restored = _extract(zipped, entries, target)
                if restored != baseline or (target / "Core" / MARKER).exists():
                    result["rollback"] = "FAILED"
                    return result
                result["rollback"] = "VERIFIED"
                result["protected_data"] = (
                    "MATCHES_ARCHIVE"
                    if all(_file_hash(target / p) == baseline[p] for p in PROTECTED)
                    else "DIFFERS")
                if result["protected_data"] == "MATCHES_ARCHIVE":
                    result["result"] = "PASS_SIMULATED_ROLLBACK"
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile,
            zipfile.LargeZipFile):
        if result["archive"] == "NOT_TESTED":
            result["archive"] = "INVALID"
        if result["simulated_failure"] == "INJECTED":
            result["rollback"] = "FAILED"
    return result


def public_summary(result: dict) -> str:
    """Closed vocabulary: never expose local paths, archive names or data."""
    allowed = {
        "NOT_TESTED", "ABSENT", "INVALID", "INVALID_CRC", "CRC_OK", "LOW_DISK",
        "NOT_INJECTED", "INJECTED", "VERIFIED", "FAILED", "MATCHES_ARCHIVE",
        "DIFFERS", "NOT_TOUCHED", "SIMULATION_ONLY", "PASS_SIMULATED_ROLLBACK",
        "BLOCKED",
    }
    def state(name: str) -> str:
        value = result.get(name)
        return value if isinstance(value, str) and value in allowed else "BLOCKED"
    return "\n".join((
        "[BAZOR-ROLLBACK-SIMULATION]",
        "ARCHIVE: " + state("archive"),
        "BACKUP_ENTRIES: " + str(min(max(0, int(result.get("backup_entries", 0))), MAX_ENTRIES)),
        "SIMULATED_FAILURE: " + state("simulated_failure"),
        "ROLLBACK: " + state("rollback"),
        "PROTECTED_DATA: " + state("protected_data"),
        "LIVE_SERVICES: NOT_TOUCHED",
        "PAID_AI_CALLS: ZERO",
        "DEPLOYMENT: SIMULATION_ONLY",
        "RESULT: " + state("result"),
        "NEXT: live deployment and rollback remain unverified",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description="BAZOR: disposable offline rollback simulation")
    parser.add_argument("--localappdata", type=Path,
                        default=Path(os.environ.get("LOCALAPPDATA")
                                     or Path.home() / "AppData" / "Local"))
    parser.add_argument("--archive", type=Path,
                        help="Local backup archive (optional; default newest PRE_MULTI_IA_*.zip)")
    args = parser.parse_args()
    archive = args.archive or latest(args.localappdata / "BAZOR" / "Backups",
                                     "PRE_MULTI_IA_*.zip")
    report = (rehearse(archive, args.localappdata / "BAZOR" / "Reports")
              if archive else rehearse(Path("__BAZOR_MISSING_BACKUP__"),
                                       args.localappdata / "BAZOR" / "Reports"))
    print(public_summary(report))
    return 0 if report["result"] == "PASS_SIMULATED_ROLLBACK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
