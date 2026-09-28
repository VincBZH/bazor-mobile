"""BAZOR V24 transactional filesystem deployer with rollback and crash recovery.

This module is deliberately conservative:
- default action is PREPARE only;
- COMMIT requires a short-lived local authorization file matching the exact
  candidate manifest and transaction id;
- it never starts/stops processes, calls AI providers, or reads GitHub;
- previous generations are kept after success;
- every filesystem step is journaled durably before the next step;
- any failure triggers rollback; incomplete transactions are recoverable.

The first validation target is a disposable Windows copy. Live use remains
forbidden until the Windows fault-injection matrix is green.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

PROTECTED_ROOM = ("chat_history.json", "control.json", "projects.json", "state.json")
MAX_FILES = 20000
MAX_TOTAL = 2 * 1024**3
AUTH_TTL_SECONDS = 600
JOURNAL_VERSION = 1
PHASES = (
    "PREPARED", "AUTHORIZED", "CORE_OLD_MOVED", "CORE_NEW_MOVED",
    "ROOM_OLD_MOVED", "ROOM_NEW_MOVED", "VERIFIED", "ROLLED_BACK", "RECOVERED",
)
FAIL_POINTS = set(PHASES[:-3])


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError("missing_tree")
    rows, total = {}, 0
    base = root.resolve()
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError("symlink_forbidden")
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        if any(part in ("", ".", "..") or ":" in part or part.endswith((" ", "."))
               for part in rel.split("/")):
            raise ValueError("unsafe_name")
        resolved = p.resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            raise ValueError("path_escape")
        size = p.stat().st_size
        total += size
        if len(rows) >= MAX_FILES or total > MAX_TOTAL:
            raise ValueError("tree_too_large")
        rows[rel] = {"sha256": _hash(p), "size": size}
    if not rows:
        raise ValueError("empty_tree")
    return {"files": rows, "count": len(rows), "bytes": total}


def _manifest_id(core: dict, room: dict) -> str:
    raw = json.dumps({"core": core, "room": room}, sort_keys=True,
                     separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _protected_hashes(room: Path) -> dict:
    result = {}
    for name in PROTECTED_ROOM:
        p = room / name
        if not p.is_file():
            raise ValueError("protected_data_missing")
        result[name] = _hash(p)
    return result


def _write_json_atomic(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _copy_tree(src: Path, dst: Path):
    if dst.exists():
        raise ValueError("destination_exists")
    shutil.copytree(src, dst, symlinks=False)
    # Copytree follows no symlinks only after manifest already rejected them.


def _same_manifest(root: Path, expected: dict) -> bool:
    try:
        return _manifest(root) == expected
    except (OSError, ValueError):
        return False


def _journal_path(txroot: Path, txid: str) -> Path:
    return txroot / (txid + ".json")


def _state(txroot: Path, txid: str) -> dict:
    p = _journal_path(txroot, txid)
    if not p.is_file():
        raise ValueError("journal_missing")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if obj.get("version") != JOURNAL_VERSION or obj.get("txid") != txid:
        raise ValueError("journal_invalid")
    return obj


def _save(txroot: Path, state: dict, phase: str):
    if phase not in PHASES:
        raise ValueError("phase_invalid")
    state["phase"] = phase
    state["updated_at"] = int(time.time())
    _write_json_atomic(_journal_path(txroot, state["txid"]), state)


def _fault(name: str | None, phase: str):
    if name and name == phase:
        raise RuntimeError("injected_failure")


def prepare(core_live: Path, room_live: Path, core_candidate: Path,
            room_candidate: Path, txroot: Path, txid: str | None = None) -> dict:
    txid = txid or ("tx-" + uuid.uuid4().hex)
    if not core_live.is_dir() or not room_live.is_dir():
        raise ValueError("live_missing")
    if _journal_path(txroot, txid).exists():
        raise ValueError("transaction_exists")
    core_m = _manifest(core_candidate)
    room_m = _manifest(room_candidate)
    protected = _protected_hashes(room_live)
    # Candidate room receives exact current user data before manifest locking.
    staged_root = txroot / "staged" / txid
    staged_core, staged_room = staged_root / "Core", staged_root / "Room"
    staged_root.parent.mkdir(parents=True, exist_ok=True)
    if staged_root.exists():
        raise ValueError("staging_exists")
    _copy_tree(core_candidate, staged_core)
    _copy_tree(room_candidate, staged_room)
    for name in PROTECTED_ROOM:
        shutil.copy2(room_live / name, staged_room / name)
    staged_core_m, staged_room_m = _manifest(staged_core), _manifest(staged_room)
    manifest_id = _manifest_id(staged_core_m, staged_room_m)
    state = {
        "version": JOURNAL_VERSION, "txid": txid, "phase": "PREPARED",
        "created_at": int(time.time()), "updated_at": int(time.time()),
        "manifest_id": manifest_id,
        "core_live": str(core_live), "room_live": str(room_live),
        "staged_core": str(staged_core), "staged_room": str(staged_room),
        "core_manifest": staged_core_m, "room_manifest": staged_room_m,
        "protected_before": protected,
        "previous_core": str(core_live.with_name(core_live.name + ".previous." + txid)),
        "previous_room": str(room_live.with_name(room_live.name + ".previous." + txid)),
        "failed_core": str(core_live.with_name(core_live.name + ".failed." + txid)),
        "failed_room": str(room_live.with_name(room_live.name + ".failed." + txid)),
    }
    _save(txroot, state, "PREPARED")
    return {"txid": txid, "manifest_id": manifest_id, "phase": "PREPARED"}


def issue_authorization(txroot: Path, txid: str, auth_path: Path, ttl: int = AUTH_TTL_SECONDS):
    """Local helper. The caller/UI must perform the human confirmation."""
    st = _state(txroot, txid)
    if st["phase"] != "PREPARED":
        raise ValueError("not_prepared")
    now = int(time.time())
    auth = {
        "version": 1, "txid": txid, "manifest_id": st["manifest_id"],
        "issued_at": now, "expires_at": now + max(30, min(int(ttl), AUTH_TTL_SECONDS)),
        "nonce": uuid.uuid4().hex,
    }
    _write_json_atomic(auth_path, auth)
    return auth


def _consume_auth(txroot: Path, st: dict, auth_path: Path):
    if not auth_path.is_file():
        raise ValueError("authorization_missing")
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    now = int(time.time())
    ok = (auth.get("version") == 1 and auth.get("txid") == st["txid"]
          and auth.get("manifest_id") == st["manifest_id"]
          and isinstance(auth.get("expires_at"), int) and now <= auth["expires_at"]
          and isinstance(auth.get("issued_at"), int) and auth["issued_at"] <= now
          and isinstance(auth.get("nonce"), str) and len(auth["nonce"]) >= 16)
    if not ok:
        raise ValueError("authorization_invalid")
    # One-time: remove before any live rename.
    auth_path.unlink()
    _save(txroot, st, "AUTHORIZED")


def rollback(txroot: Path, txid: str, reason: str = "failure") -> dict:
    st = _state(txroot, txid)
    core_live, room_live = Path(st["core_live"]), Path(st["room_live"])
    pc, pr = Path(st["previous_core"]), Path(st["previous_room"])
    fc, fr = Path(st["failed_core"]), Path(st["failed_room"])
    try:
        # Move any promoted candidate aside, then restore previous generations.
        if pc.exists():
            if core_live.exists() and not fc.exists():
                os.replace(core_live, fc)
            if not core_live.exists():
                os.replace(pc, core_live)
        if pr.exists():
            if room_live.exists() and not fr.exists():
                os.replace(room_live, fr)
            if not room_live.exists():
                os.replace(pr, room_live)
        # Protected data must equal the snapshot unless the user modified it;
        # never overwrite a newer value during rollback.
        protected = _protected_hashes(room_live)
        if protected != st["protected_before"]:
            st["rollback_reason"] = "protected_data_drift"
            _save(txroot, st, "ROLLED_BACK")
            return {"ok": False, "phase": "ROLLED_BACK", "protected": "DRIFT"}
        st["rollback_reason"] = reason
        _save(txroot, st, "ROLLED_BACK")
        return {"ok": True, "phase": "ROLLED_BACK", "protected": "UNCHANGED"}
    except (OSError, ValueError) as exc:
        # Closed diagnostic only; never expose local paths or exception text.
        return {"ok": False, "phase": st.get("phase", "UNKNOWN"),
                "protected": "UNKNOWN", "error_kind": type(exc).__name__,
                "winerror": getattr(exc, "winerror", None)}


def commit(txroot: Path, txid: str, auth_path: Path, fault_after: str | None = None) -> dict:
    st = _state(txroot, txid)
    if st["phase"] != "PREPARED":
        raise ValueError("not_prepared")
    _consume_auth(txroot, st, auth_path)
    core_live, room_live = Path(st["core_live"]), Path(st["room_live"])
    staged_core, staged_room = Path(st["staged_core"]), Path(st["staged_room"])
    pc, pr = Path(st["previous_core"]), Path(st["previous_room"])
    try:
        if _protected_hashes(room_live) != st["protected_before"]:
            raise RuntimeError("protected_data_changed_before_commit")
        if not _same_manifest(staged_core, st["core_manifest"]) or not _same_manifest(staged_room, st["room_manifest"]):
            raise RuntimeError("candidate_changed")
        if pc.exists() or pr.exists():
            raise RuntimeError("previous_generation_collision")

        os.replace(core_live, pc)
        _save(txroot, st, "CORE_OLD_MOVED"); _fault(fault_after, "CORE_OLD_MOVED")
        os.replace(staged_core, core_live)
        _save(txroot, st, "CORE_NEW_MOVED"); _fault(fault_after, "CORE_NEW_MOVED")
        os.replace(room_live, pr)
        _save(txroot, st, "ROOM_OLD_MOVED"); _fault(fault_after, "ROOM_OLD_MOVED")
        os.replace(staged_room, room_live)
        _save(txroot, st, "ROOM_NEW_MOVED"); _fault(fault_after, "ROOM_NEW_MOVED")

        if not _same_manifest(core_live, st["core_manifest"]) or not _same_manifest(room_live, st["room_manifest"]):
            raise RuntimeError("post_commit_manifest_mismatch")
        if _protected_hashes(room_live) != st["protected_before"]:
            raise RuntimeError("protected_data_changed_after_commit")
        _save(txroot, st, "VERIFIED")
        return {"ok": True, "phase": "VERIFIED", "previous_kept": True}
    except Exception as exc:
        rb = rollback(txroot, txid, type(exc).__name__)
        return {"ok": False, "phase": rb["phase"], "rollback_ok": rb["ok"],
                "previous_kept": Path(st["previous_core"]).exists() or Path(st["previous_room"]).exists()}


def recover(txroot: Path, txid: str) -> dict:
    st = _state(txroot, txid)
    if st["phase"] in ("VERIFIED", "ROLLED_BACK", "RECOVERED"):
        return {"ok": True, "phase": st["phase"], "action": "NONE"}
    rb = rollback(txroot, txid, "recover_after_crash")
    if rb["ok"]:
        st = _state(txroot, txid)
        _save(txroot, st, "RECOVERED")
        return {"ok": True, "phase": "RECOVERED", "action": "ROLLBACK"}
    return {"ok": False, "phase": st["phase"], "action": "MANUAL_REQUIRED"}


def public_summary(result: dict) -> str:
    allowed_phase = set(PHASES) | {"UNKNOWN"}
    phase = result.get("phase") if result.get("phase") in allowed_phase else "UNKNOWN"
    return "\n".join((
        "[BAZOR-TRANSACTION]",
        "PHASE: " + phase,
        "OK: " + ("YES" if result.get("ok") else "NO"),
        "PREVIOUS_GENERATION_KEPT: " + ("YES" if result.get("previous_kept") else "NO"),
        "ROLLBACK_OK: " + ("YES" if result.get("rollback_ok") else "NO"),
        "PAID_AI_CALLS: ZERO",
        "PROCESSES_TOUCHED: ZERO",
    ))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("prepare", "authorize", "commit", "recover"))
    p.add_argument("--txroot", type=Path, required=True)
    p.add_argument("--txid")
    p.add_argument("--core-live", type=Path)
    p.add_argument("--room-live", type=Path)
    p.add_argument("--core-candidate", type=Path)
    p.add_argument("--room-candidate", type=Path)
    p.add_argument("--auth", type=Path)
    p.add_argument("--fault-after", choices=sorted(FAIL_POINTS))
    a = p.parse_args()
    if a.action == "prepare":
        out = prepare(a.core_live, a.room_live, a.core_candidate, a.room_candidate, a.txroot, a.txid)
        print(json.dumps(out, sort_keys=True)); return 0
    if not a.txid:
        p.error("--txid required")
    if a.action == "authorize":
        if not a.auth: p.error("--auth required")
        issue_authorization(a.txroot, a.txid, a.auth)
        print("[BAZOR-TRANSACTION-AUTH]\nAUTHORIZATION_FILE: CREATED_LOCAL_ONLY")
        return 0
    if a.action == "commit":
        if not a.auth: p.error("--auth required")
        out = commit(a.txroot, a.txid, a.auth, a.fault_after)
    else:
        out = recover(a.txroot, a.txid)
    print(public_summary(out))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
