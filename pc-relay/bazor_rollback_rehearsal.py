"""BAZOR rollback rehearsal: inject a failed update ONLY inside a temporary copy.

No service starts/stops; no installation, shell, provider API or private upload.
The installed Core/Room are opened for hashing only. Never write to them.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

from bazor_compat_preflight import CRITICAL_BACKUP, MAX_UNPACKED, safe_member

FAULT_TARGET = "Core/DEMARRER_BAZOR_PC_RELAY.cmd"
MAX_ENTRIES = 20000
MARKER = b"\nREM BAZOR_SIMULATED_FAULT_NO_PRODUCTION_CHANGE\n"


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def public_summary(result: dict) -> str:
    """Public output is fixed vocabulary only. Never echo a path or exception."""
    values = {
        "BACKUP": {"VALID", "ABSENT", "INVALID", "LOW_DISK"},
        "FAULT_INJECTION": {"PASS", "BLOCKED", "NOT_RUN"},
        "RESTORE": {"PASS", "FAILED", "NOT_RUN"},
        "LIVE_FILES": {"UNCHANGED", "CHANGED", "NOT_VERIFIED"},
        "RESULT": {"PASS_SIMULATED_ROLLBACK", "BLOCKED"},
    }
    out = ["[BAZOR-ROLLBACK-REHEARSAL]", "MODE: TEMP_DIRECTORY_ONLY"]
    for field in ("BACKUP", "FAULT_INJECTION", "RESTORE", "LIVE_FILES", "RESULT"):
        value = result.get(field, "BLOCKED")
        out.append(field + ": " + (value if value in values[field] else "BLOCKED"))
    out.extend(("PAID_AI_CALLS: ZERO", "PRODUCTION_FILES_WRITTEN: ZERO",
                "ACTUAL_DEPLOYMENT_ROLLBACK_TESTED: NO"))
    return "\n".join(out)


def _archive_entries(zf):
    entries = zf.infolist()
    names = [z.filename.rstrip("/") for z in entries]
    if (not entries or len(entries) > MAX_ENTRIES or len(names) != len(set(names))
            or not all(safe_member(z) for z in entries)
            or not set(CRITICAL_BACKUP).issubset(set(names))
            or not any(z.filename == FAULT_TARGET for z in entries)):
        return None
    if sum(z.file_size for z in entries if not z.is_dir()) > MAX_UNPACKED:
        return None
    return entries


def _copy_into(zf, entries, target: Path):
    """Extract controlled ZIP members without extractall or path traversal."""
    for info in entries:
        dest = target.joinpath(*PurePosixPath(info.filename).parts)
        if info.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, dest.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        if dest.stat().st_size != info.file_size:
            raise ValueError("entry_size_mismatch")


def _verify_snapshot(zf, entries, target: Path) -> bool:
    for info in entries:
        dest = target.joinpath(*PurePosixPath(info.filename).parts)
        if info.is_dir():
            if not dest.is_dir():
                return False
            continue
        h = hashlib.sha256()
        with zf.open(info) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        if not dest.is_file() or digest_file(dest) != h.hexdigest():
            return False
    return True


def live_snapshot(local: Path):
    core, room = local / "BAZOR" / "Core", local / "BazorAIROOM"
    out = {}
    for item in CRITICAL_BACKUP:
        label, name = item.split("/", 1)
        path = (core if label == "Core" else room) / name
        if not path.is_file():
            return None
        out[item] = digest_file(path)
    return out


def rehearsal(archive: Path, local: Path, work: Path) -> dict:
    result = {"BACKUP": "ABSENT", "FAULT_INJECTION": "NOT_RUN",
              "RESTORE": "NOT_RUN", "LIVE_FILES": "NOT_VERIFIED",
              "RESULT": "BLOCKED"}
    if not archive.is_file():
        return result
    initial = live_snapshot(local)
    if not initial:
        return result
    try:
        with zipfile.ZipFile(archive) as zf:
            entries = _archive_entries(zf)
            if entries is None:
                result["BACKUP"] = "INVALID"
                return result
            unpacked = sum(info.file_size for info in entries if not info.is_dir())
            # Only one extracted tree is necessary. Rehearsal modifies its
            # designated test file and then restores that file from the ZIP.
            work.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(work).free < unpacked + 64 * 1024 * 1024:
                result["BACKUP"] = "LOW_DISK"
                return result
            if zf.testzip() is not None:
                result["BACKUP"] = "INVALID"
                return result
            result["BACKUP"] = "VALID"
            with tempfile.TemporaryDirectory(prefix="bazor_rollback_", dir=work) as td:
                root = Path(td)
                _copy_into(zf, entries, root)
                if not _verify_snapshot(zf, entries, root):
                    result["RESTORE"] = "FAILED"
                    return result
                fault = root / FAULT_TARGET
                with fault.open("ab") as stream:
                    stream.write(MARKER)
                if not fault.read_bytes().endswith(MARKER):
                    return result
                result["FAULT_INJECTION"] = "PASS"
                # Simulate failure-triggered rollback: restore damaged file
                # from the verified archive; all other saved entries must match.
                with zf.open(FAULT_TARGET) as src, fault.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                result["RESTORE"] = ("PASS" if _verify_snapshot(zf, entries, root)
                                     else "FAILED")
        after = live_snapshot(local)
        result["LIVE_FILES"] = ("UNCHANGED" if after == initial and after is not None
                                else "CHANGED")
        if (result["FAULT_INJECTION"] == result["RESTORE"] == "PASS"
                and result["LIVE_FILES"] == "UNCHANGED"):
            result["RESULT"] = "PASS_SIMULATED_ROLLBACK"
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        result["BACKUP"] = "INVALID" if result["BACKUP"] == "ABSENT" else result["BACKUP"]
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="BAZOR simulation de rollback sans déploiement")
    ap.add_argument("--localappdata", type=Path,
                    default=Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"))
    ap.add_argument("--archive", type=Path)
    args = ap.parse_args()
    backups = args.localappdata / "BAZOR" / "Backups"
    archives = list(backups.glob("PRE_MULTI_IA_*.zip"))
    source = args.archive or (max(archives, key=lambda p: p.stat().st_mtime)
                              if archives else backups / "__missing__.zip")
    result = rehearsal(source, args.localappdata, args.localappdata / "BAZOR" / "Reports")
    print(public_summary(result))
    return 0 if result["RESULT"] == "PASS_SIMULATED_ROLLBACK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
