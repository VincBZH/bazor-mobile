"""BAZOR transactional installer prototype — DISPOSABLE FIXTURES ONLY.

This module cannot accept a production path, invoke processes or read live files.
Both Core and Room are synthetic fixtures under a newly created private temporary
directory. Crash injection tests rename ordering, journal persistence and recovery.
No production installation, data migration, provider API or remote command execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

COMPONENTS = ("Core", "Room")
FIXTURE_MARKER = "BAZOR_DISPOSABLE_TRANSACTION_FIXTURE_V1"
DATA = "PRIVATE_TEST_HISTORY_DO_NOT_UPLOAD"
PHASES = ("INITIALIZED", "SWAPPING_CORE", "CORE_DONE",
          "SWAPPING_ROOM", "ROOM_DONE", "COMMITTED", "ROLLING_BACK", "ROLLED_BACK")
STATUS = {"PASS_SANDBOX", "BLOCKED", "RECOVERED", "INCOMPLETE"}
class UnsafeSandbox(ValueError):
    pass
class InjectedCrash(RuntimeError):
    pass


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_file(path: Path) -> str | None:
    try:
        return _hash(path.read_bytes()) if path.is_file() and not path.is_symlink() else None
    except OSError:
        return None


def _atomic_json(path: Path, value: dict) -> None:
    """Durable best-effort journal on one volume; never used for production."""
    tmp = path.with_suffix(".tmp")
    with tmp.open("x", encoding="utf-8") as out:
        json.dump(value, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def create_fixture(root: Path) -> None:
    """Never import production paths or accept caller-supplied program contents."""
    root.mkdir(parents=True, exist_ok=False)
    for name in COMPONENTS:
        for label, version in (("live", "OLD"), ("candidate", "NEW")):
            location = root / label / name
            location.mkdir(parents=True)
            (location / "version.txt").write_text(
                f"FAKE_{name}_{version}", encoding="ascii")
    data = root / "data"
    data.mkdir()
    (data / "history.txt").write_text(DATA, encoding="ascii")
    expected = {"marker": FIXTURE_MARKER, "phase": "INITIALIZED",
                "old": {n: _hash_file(root / "live" / n / "version.txt") for n in COMPONENTS},
                "new": {n: _hash_file(root / "candidate" / n / "version.txt") for n in COMPONENTS},
                "history": _hash_file(data / "history.txt")}
    _atomic_json(root / "journal.json", expected)


def _validated(root: Path) -> dict:
    """Fail closed if called on any nonfixture path, junction or symlink."""
    if root.is_symlink() or not root.is_dir() or not root.name.startswith("bazor_txn_fixture_"):
        raise UnsafeSandbox("not_disposable_fixture")
    try:
        # A fixed marker plus two independent fixture versions are required.
        journal = json.loads((root / "journal.json").read_text(encoding="utf-8"))
        if journal.get("marker") != FIXTURE_MARKER or journal.get("phase") not in PHASES:
            raise UnsafeSandbox("fixture_identity_invalid")
        if set(journal.get("old", {})) != set(COMPONENTS):
            raise UnsafeSandbox("fixture_manifest_invalid")
        if set(journal.get("new", {})) != set(COMPONENTS):
            raise UnsafeSandbox("fixture_manifest_invalid")
        for p in (root, root / "live", root / "candidate", root / "previous",
                  root / "data", root / "journal.json"):
            if p.is_symlink():
                raise UnsafeSandbox("symlink_blocked")
        for label in ("live", "candidate", "previous"):
            for name in COMPONENTS:
                p = root / label / name
                if p.is_symlink() or (p.exists() and (p / "version.txt").is_symlink()):
                    raise UnsafeSandbox("component_symlink_blocked")
        if (root / "data" / "history.txt").is_symlink():
            raise UnsafeSandbox("data_symlink_blocked")
        return journal
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise UnsafeSandbox("fixture_unreadable") from exc


def _save(root: Path, record: dict, phase: str) -> None:
    if phase not in PHASES:
        raise UnsafeSandbox("invalid_phase")
    record["phase"] = phase
    _atomic_json(root / "journal.json", record)


def _data_untouched(root: Path, record: dict) -> bool:
    return _hash_file(root / "data" / "history.txt") == record["history"]


def _move_step(root: Path, record: dict, name: str, crash: str | None) -> None:
    old = root / "live" / name
    new = root / "candidate" / name
    previous = root / "previous" / name
    if (_hash_file(old / "version.txt") != record["old"][name]
            or _hash_file(new / "version.txt") != record["new"][name]
            or previous.exists() or not _data_untouched(root, record)):
        raise UnsafeSandbox("manifest_drift")
    _save(root, record, "SWAPPING_" + name.upper())
    previous.parent.mkdir(exist_ok=True)
    old.rename(previous)
    if crash == f"after_save_{name.lower()}":
        raise InjectedCrash("after_old_generation_saved")
    new.rename(old)
    if crash == f"after_promote_{name.lower()}":
        raise InjectedCrash("after_new_generation_promoted")
    if _hash_file(old / "version.txt") != record["new"][name]:
        raise UnsafeSandbox("candidate_changed")
    _save(root, record, name.upper() + "_DONE")


def promote(root: Path, crash: str | None = None) -> str:
    """Perform a fake two-directory promotion; leave partial state on crash."""
    rec = _validated(root)
    if rec["phase"] != "INITIALIZED" or not _data_untouched(root, rec):
        raise UnsafeSandbox("transaction_not_ready")
    # Validate ALL candidate and live fixture components before first rename.
    # Otherwise drift in Room could leave a partially promoted Core.
    for name in COMPONENTS:
        if (_hash_file(root / "live" / name / "version.txt") != rec["old"][name]
                or _hash_file(root / "candidate" / name / "version.txt") != rec["new"][name]
                or (root / "previous" / name).exists()):
            raise UnsafeSandbox("manifest_drift")
    _move_step(root, rec, "Core", crash)
    _move_step(root, rec, "Room", crash)
    if not _data_untouched(root, rec):
        raise UnsafeSandbox("private_fixture_data_changed")
    _save(root, rec, "COMMITTED")
    return "PASS_SANDBOX"


def recover(root: Path) -> str:
    """Idempotent rollback of any incomplete fake promotion.

    If a generation has changed unexpectedly, preserve it and report BLOCKED:
    never overwrite unknown data even inside the synthetic sandbox.
    """
    rec = _validated(root)
    if rec["phase"] == "INITIALIZED":
        return "BLOCKED"
    if not _data_untouched(root, rec):
        return "BLOCKED"
    if rec["phase"] == "ROLLED_BACK":
        return "RECOVERED" if all(
            _hash_file(root / "live" / n / "version.txt") == rec["old"][n]
            for n in COMPONENTS) else "BLOCKED"
    # First validate BOTH components before any destructive rename.
    for name in COMPONENTS:
        old, new, prev = (root / label / name for label in ("live", "candidate", "previous"))
        live_hash, cand_hash, old_hash = (_hash_file(p / "version.txt") for p in (old, new, prev))
        expected_old, expected_new = rec["old"][name], rec["new"][name]
        if old_hash is not None:
            if old_hash != expected_old or live_hash not in (None, expected_new):
                return "BLOCKED"
            if cand_hash not in (None, expected_new):
                return "BLOCKED"
        elif live_hash != expected_old or cand_hash not in (None, expected_new):
            return "BLOCKED"
    _save(root, rec, "ROLLING_BACK")
    for name in reversed(COMPONENTS):
        current, candidate, previous = (root / label / name
                                        for label in ("live", "candidate", "previous"))
        if previous.is_dir():
            if current.exists():
                if candidate.exists():
                    # No overwrite or deletion of another generation if ambiguous.
                    return "BLOCKED"
                current.rename(candidate)
            previous.rename(current)
    if not _data_untouched(root, rec) or not all(
            _hash_file(root / "live" / n / "version.txt") == rec["old"][n]
            for n in COMPONENTS):
        return "BLOCKED"
    _save(root, rec, "ROLLED_BACK")
    return "RECOVERED"


def run_suite() -> dict:
    """Entry point runs scenarios only in separate, auto-deleted temp fixtures."""
    outcomes = {}
    for scenario in ("success", "after_save_core", "after_promote_core",
                     "after_save_room", "after_promote_room", "tampered_history"):
        with tempfile.TemporaryDirectory(prefix="bazor_txn_suite_") as outer:
            root = Path(outer) / "bazor_txn_fixture_001"
            create_fixture(root)
            try:
                promote(root, crash=scenario if scenario != "success" else None)
            except InjectedCrash:
                pass
            if scenario == "tampered_history":
                (root / "data" / "history.txt").write_text("USER_EDIT", encoding="ascii")
            outcome = recover(root)
            if scenario == "tampered_history":
                outcomes[scenario] = outcome == "BLOCKED"
            elif scenario == "success":
                outcomes[scenario] = outcome == "RECOVERED"
            else:
                outcomes[scenario] = outcome == "RECOVERED"
    return {"result": "PASS_SANDBOX" if all(outcomes.values()) else "BLOCKED",
            "scenarios_passed": sum(outcomes.values()),
            "scenarios_total": len(outcomes), "deployment": "NEVER_PERFORMED"}


def public_summary(report: dict) -> str:
    status = report.get("result")
    safe_status = status if status in STATUS else "BLOCKED"
    n, total = int(report.get("scenarios_passed", 0)), int(report.get("scenarios_total", 0))
    return "\n".join(("[BAZOR-TRANSACTION-SANDBOX]",
                      "RESULT: " + safe_status,
                      "SCENARIOS_PASSED: " + str(min(max(n, 0), 20)),
                      "SCENARIOS_TOTAL: " + str(min(max(total, 0), 20)),
                      "PRODUCTION_FILES_WRITTEN: ZERO",
                      "PAID_AI_CALLS: ZERO",
                      "ACTUAL_DEPLOYMENT_TESTED: NO"))


def main() -> int:
    parser = argparse.ArgumentParser(description="BAZOR offline disposable transaction tests")
    parser.add_argument("--simulate-only", action="store_true", required=True)
    parser.parse_args()
    result = run_suite()
    print(public_summary(result))
    return 0 if result["result"] == "PASS_SANDBOX" else 2


if __name__ == "__main__":
    raise SystemExit(main())
