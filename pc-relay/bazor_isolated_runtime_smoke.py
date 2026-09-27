"""Read-only BAZOR isolated-runtime probe; one local Ollama turn only with explicit opt-in.

Unlike the one-click launcher, this file DOES NOT start, stop, replace or
install services. It never contacts GitHub, Mammouth or the OpenAI API.
A 200 HTTP response alone is not evidence of an operational Core or AI Room.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import bazor_multiai_oneclick as oneclick

CORE_PORT = 8875
ROOM_PORT = 8768
STATIC_MARKER = "BAZOR_LOCAL_OK"
PRODUCTION_CORE = "http://127.0.0.1:8775/api/v1/health"
PRODUCTION_CORE_STATUS = "http://127.0.0.1:8775/api/v1/security/status"
PRODUCTION_ROOM = "http://127.0.0.1:8765/api/status"
ISOLATED_CORE = "http://127.0.0.1:8875/api/v1/health"
ISOLATED_ROOM = "http://127.0.0.1:8768/api/status"
LOCAL_MODELS = "http://127.0.0.1:11434/api/tags"


def expected_signature(root: Path) -> str | None:
    """Same hash contract as the existing one-click launcher."""
    digest = hashlib.sha256()
    try:
        for name in oneclick.CORE_FILES:
            path = root / "pc-relay" / name
            if not path.is_file():
                return None
            digest.update(name.encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()
    except OSError:
        return None


def stable_live(before, after) -> str:
    """Absence of an endpoint is UNKNOWN, never a confirmation of preservation."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return "NOT_VERIFIED"
    if before.get("ok") is not True or after.get("ok") is not True:
        return "NOT_VERIFIED"
    keys = ("pid", "runtime_signature")
    if not all(before.get(k) is not None and after.get(k) is not None for k in keys):
        return "NOT_VERIFIED"
    return "UNCHANGED" if all(before[k] == after[k] for k in keys) else "CHANGED"


def stable_core(before, after, status_before, status_after, pid_before, pid_after) -> str:
    """Verify legacy Core using its security-status API and listener owner.

    Prefer /health PID + runtime signature when both exist. A fallback requires
    the same positive Windows listener PID plus two valid BAZOR status replies.
    """
    verified = stable_live(before, after)
    if verified != "NOT_VERIFIED":
        if (pid_before is not None and pid_after is not None
                and pid_before != pid_after):
            return "CHANGED"
        return verified
    if not (isinstance(pid_before, int) and pid_before > 0
            and isinstance(pid_after, int) and pid_after > 0):
        return "NOT_VERIFIED"
    if pid_before != pid_after:
        return "CHANGED"
    for health in (before, after):
        if isinstance(health, dict):
            if health.get("ok") is False:
                return "NOT_VERIFIED"
            if health.get("pid") is not None and health.get("pid") != pid_before:
                return "NOT_VERIFIED"
    if not (isinstance(status_before, dict) and isinstance(status_after, dict)
            and status_before.get("ok") is True and status_after.get("ok") is True
            and status_before.get("mode") == status_after.get("mode") == "device-proof"):
        return "NOT_VERIFIED"
    for field in ("runtime_signature", "service", "version"):
        if isinstance(before, dict) and isinstance(after, dict):
            left, right = before.get(field), after.get(field)
            if left is not None and right is not None and left != right:
                return "CHANGED"
            if (left is None) != (right is None):
                return "NOT_VERIFIED"
    return "UNCHANGED"


def windows_listening_pid(port: int) -> int | None:
    """Read a Windows loopback listener PID; never stop or modify the process.

    The installed Room v1/v2 does not always expose a PID via /api/status.
    netstat is used only for this local identity check, without shell=True.
    """
    if os.name != "nt":
        return None
    try:
        response = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
            timeout=6, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            encoding="utf-8", errors="replace", check=False,
        )
        if response.returncode != 0:
            return None
        loopback_owners, wildcard_owners = set(), set()
        for raw in response.stdout.splitlines():
            parts = raw.split()
            # The LISTENING state is localized on some Windows systems.
            # Prefer the exact loopback listener if a different process also
            # owns a wildcard socket on the same port. Multiple owners in
            # the selected class remain ambiguous and MUST NOT be certified.
            if (len(parts) >= 5 and parts[0].upper() == "TCP"
                    and parts[2] == "0.0.0.0:0" and parts[-1].isdigit()):
                pid = int(parts[-1])
                if pid > 0 and parts[1] == f"127.0.0.1:{port}":
                    loopback_owners.add(pid)
                elif pid > 0 and parts[1] == f"0.0.0.0:{port}":
                    wildcard_owners.add(pid)
        owners = loopback_owners if loopback_owners else wildcard_owners
        return next(iter(owners)) if len(owners) == 1 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def stable_room(before, after, before_pid, after_pid) -> str:
    """Stable listener PID + successful Room health, not an invented API PID."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return "NOT_VERIFIED"
    if before.get("ok") is not True or after.get("ok") is not True:
        return "NOT_VERIFIED"
    if not isinstance(before_pid, int) or before_pid <= 0 or not isinstance(after_pid, int):
        return "NOT_VERIFIED"
    if before_pid != after_pid:
        return "CHANGED"
    # A changed declared server identity blocks preservation claims.
    for field in ("version", "service"):
        if before.get(field) != after.get(field):
            return "CHANGED"
    return "UNCHANGED"


def check(root: Path, *, allow_local_chat: bool = False, fetch=None, owner=None) -> dict:
    """Fixed loopback endpoints only; publishes a fixed, non-sensitive report."""
    if fetch is None:
        fetch = oneclick.local_json
    if owner is None:
        owner = windows_listening_pid
    report = {
        "schema": "BAZOR_ISOLATED_RUNTIME_V1",
        "core": "NOT_TESTED", "room": "NOT_TESTED",
        "ollama": "NOT_TESTED", "local_chat": "NOT_AUTHORIZED",
        "production_core": "NOT_VERIFIED", "production_room": "NOT_VERIFIED",
        "result": "BLOCKED", "paid_calls": 0, "deployment": "NEVER_PERFORMED",
    }

    def local(url, payload=None, timeout=3):
        try:
            return fetch(url, payload, timeout)
        except Exception:
            # Never include a raw exception, URL, path or provider response.
            return None

    live_core_before = local(PRODUCTION_CORE)
    core_status_before = local(PRODUCTION_CORE_STATUS)
    core_pid_before = owner(8775)
    live_room_before = local(PRODUCTION_ROOM)
    if live_room_before is None:
        live_room_before = local('http://127.0.0.1:8765/health')
    room_pid_before = owner(8765)
    signature = expected_signature(root)
    if signature is None:
        report["core"] = "STAGE_FILES_MISSING"
        return report
    health = local(ISOLATED_CORE)
    if not oneclick.valid_core(health, signature):
        report["core"] = "ISOLATED_ABSENT_OR_IDENTITY_MISMATCH"
        return report
    report["core"] = "IDENTITY_VERIFIED"
    models = local(LOCAL_MODELS)
    if not isinstance(models, dict) or not isinstance(models.get("models"), list):
        report["ollama"] = "UNAVAILABLE"
        return report
    model = oneclick.choose_model(models["models"])
    if not model:
        report["ollama"] = "NO_SMALL_MODEL"
        return report
    report["ollama"] = "MODEL_AVAILABLE"
    room = local(ISOLATED_ROOM)
    engine = (room.get("engines") or {}).get("core") if isinstance(room, dict) else None
    if (not isinstance(room, dict) or room.get("ok") is not True
            or room.get("version") != "2.4-core-relay"
            or not isinstance(engine, dict) or engine.get("available") is not True
            or engine.get("port") != CORE_PORT
            or engine.get("runtime_signature") != signature
            or engine.get("configured_local_model") != model):
        report["room"] = "ISOLATED_ABSENT_OR_CORE_MISMATCH"
        return report
    report["room"] = "CONNECTED_TO_VERIFIED_CORE"

    if allow_local_chat:
        reply = local("http://127.0.0.1:8768/api/chat",
                      {"target": "ollama", "text": "Reponds uniquement BAZOR_LOCAL_OK."},
                      timeout=210)
        rows = reply.get("results") if isinstance(reply, dict) else None
        if (isinstance(reply, dict) and reply.get("ok") is True
                and isinstance(rows, list) and len(rows) == 1
                and isinstance(rows[0], dict)
                and rows[0].get("provider") == "ollama"
                and rows[0].get("ok") is True and rows[0].get("model") == model
                and isinstance(rows[0].get("text"), str)
                and rows[0]["text"].strip() == STATIC_MARKER):
            report["local_chat"] = "VERIFIED_REAL_LOCAL"
        else:
            report["local_chat"] = "FAILED_OR_UNVERIFIABLE"
    live_core_after = local(PRODUCTION_CORE)
    core_status_after = local(PRODUCTION_CORE_STATUS)
    core_pid_after = owner(8775)
    live_room_after = local(PRODUCTION_ROOM)
    if live_room_after is None:
        live_room_after = local('http://127.0.0.1:8765/health')
    room_pid_after = owner(8765)
    report["production_core"] = stable_core(
        live_core_before, live_core_after,
        core_status_before, core_status_after, core_pid_before, core_pid_after)
    report["production_room"] = stable_room(live_room_before, live_room_after,
                                             room_pid_before, room_pid_after)
    if report["production_core"] == "CHANGED" or report["production_room"] == "CHANGED":
        report["result"] = "BLOCKED_PRODUCTION_CHANGED"
    elif allow_local_chat:
        report["result"] = ("PASS_REAL_LOCAL" if report["local_chat"] == "VERIFIED_REAL_LOCAL"
                            and report["production_core"] == "UNCHANGED"
                            and report["production_room"] == "UNCHANGED"
                            else "BLOCKED")
    else:
        report["result"] = "IDENTITY_VERIFIED_CHAT_NOT_RUN"
    return report


def public_summary(report: dict) -> str:
    """Never include any fetched body or arbitrary field."""
    allowed = {
        "NOT_TESTED", "NOT_AUTHORIZED", "NOT_VERIFIED", "UNCHANGED", "CHANGED",
        "STAGE_FILES_MISSING", "ISOLATED_ABSENT_OR_IDENTITY_MISMATCH",
        "IDENTITY_VERIFIED", "UNAVAILABLE", "NO_SMALL_MODEL", "MODEL_AVAILABLE",
        "ISOLATED_ABSENT_OR_CORE_MISMATCH", "CONNECTED_TO_VERIFIED_CORE",
        "VERIFIED_REAL_LOCAL", "FAILED_OR_UNVERIFIABLE", "BLOCKED",
        "BLOCKED_PRODUCTION_CHANGED", "PASS_REAL_LOCAL",
        "IDENTITY_VERIFIED_CHAT_NOT_RUN",
    }
    def safe(v):
        return v if v in allowed else "BLOCKED"
    return "\n".join((
        "[BAZOR-ISOLATED-SMOKE]",
        "CORE: " + safe(report.get("core")),
        "ROOM: " + safe(report.get("room")),
        "OLLAMA: " + safe(report.get("ollama")),
        "LOCAL_CHAT: " + safe(report.get("local_chat")),
        "PRODUCTION_CORE: " + safe(report.get("production_core")),
        "PRODUCTION_ROOM: " + safe(report.get("production_room")),
        "RESULT: " + safe(report.get("result")),
        "PAID_AI_CALLS: ZERO",
        "DEPLOYMENT: NEVER_PERFORMED",
        "NOTE: This probe never proves restore-after-failed-deployment or Windows Hello.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description="BAZOR local isolated runtime smoke (no installation)")
    parser.add_argument("--allow-local-chat", action="store_true",
                        help="explicitly permit exactly one Ollama call via isolated Room")
    args = parser.parse_args()
    report = check(Path(__file__).resolve().parents[1],
                   allow_local_chat=args.allow_local_chat)
    print(public_summary(report))
    return 0 if report["result"] in ("PASS_REAL_LOCAL",
                                     "IDENTITY_VERIFIED_CHAT_NOT_RUN") else 2


if __name__ == "__main__":
    raise SystemExit(main())
