"""Read-only live readiness gate for BAZOR V24 on the Windows PC.

This module never enables process mutation, never issues a transaction
authorization and never calls a paid provider.  It combines the existing
filesystem/backup preflight with process identity checks for the currently
running Core and Room.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import bazor_compat_preflight as compat
from bazor_windows_process_backend import LaunchSpec, WindowsProcessBackend

CORE_PORT = 8775
ROOM_PORT = 8765
OLLAMA_PORT = 11434

SPECS = {
    "core": LaunchSpec("unused.py", "/api/v1/health", "BAZOR API"),
    # Room V2.4 exposes its status on /api/status, not /health.
    "room": LaunchSpec("unused.py", "/api/status"),
}
PORTS = {"core": CORE_PORT, "room": ROOM_PORT}

PUBLIC = {
    "OK", "BLOCKED", "NOT_WINDOWS", "HAS_MODELS", "NO_MODELS",
    "READY_FOR_ISOLATED_TEST", "READY_FOR_AUTHORIZATION_REVIEW",
}


def _identity_state(identity, component: str, port: int) -> str:
    if identity is None:
        return "BLOCKED"
    return "OK" if (
        identity.component == component
        and identity.port == port
        and identity.pid > 0
        and identity.owned_by_current_user
        and isinstance(identity.executable_sha256, str)
        and len(identity.executable_sha256) == 64
    ) else "BLOCKED"


def decide(preflight: dict, core_state: str, room_state: str,
           ollama_state: str, platform: str) -> str:
    if platform != "nt":
        return "NOT_WINDOWS"
    if (
        preflight.get("gate") == "READY_FOR_ISOLATED_TEST"
        and core_state == "OK"
        and room_state == "OK"
        and ollama_state == "HAS_MODELS"
    ):
        return "READY_FOR_AUTHORIZATION_REVIEW"
    return "BLOCKED"


def audit(localappdata: Path) -> dict:
    preflight = compat.audit(localappdata)
    report = {
        "schema": "bazor_live_readiness_v1",
        "mode": "READ_ONLY_NO_PROCESS_CHANGES_NO_PAID_API",
        "platform": "WINDOWS" if os.name == "nt" else "NOT_WINDOWS",
        "preflight_gate": preflight.get("gate", "BLOCKED"),
        "core_identity": "BLOCKED",
        "room_identity": "BLOCKED",
        "ollama": compat.probe(
            f"http://127.0.0.1:{OLLAMA_PORT}/api/tags", models=True),
        "process_mutation": "DISABLED",
        "authorization_issued": "NO",
        "paid_ai_calls": 0,
    }
    if os.name == "nt":
        try:
            backend = WindowsProcessBackend(SPECS, PORTS, allow_process_changes=False)
            core = backend.inspect_port(CORE_PORT)
            room = backend.inspect_port(ROOM_PORT)
            report["core_identity"] = _identity_state(core, "core", CORE_PORT)
            report["room_identity"] = _identity_state(room, "room", ROOM_PORT)
            # Keep sensitive process details local only.  They are useful for
            # comparing a later authorized transaction, but public_summary()
            # deliberately excludes them.
            report["local_identity"] = {
                "core": None if core is None else {
                    "pid": core.pid,
                    "executable_sha256": core.executable_sha256,
                },
                "room": None if room is None else {
                    "pid": room.pid,
                    "executable_sha256": room.executable_sha256,
                },
            }
        except Exception:
            report["core_identity"] = "BLOCKED"
            report["room_identity"] = "BLOCKED"
    report["readiness"] = decide(
        preflight, report["core_identity"], report["room_identity"],
        report["ollama"], os.name)
    return report


def public_summary(report: dict) -> str:
    def closed(value: str) -> str:
        return value if value in PUBLIC else "BLOCKED"
    return "\n".join((
        "[BAZOR-LIVE-READINESS]",
        "MODE: READ_ONLY",
        "PLATFORM: " + ("WINDOWS" if report.get("platform") == "WINDOWS" else "NOT_WINDOWS"),
        "PREFLIGHT: " + closed(str(report.get("preflight_gate"))),
        "CORE_IDENTITY: " + closed(str(report.get("core_identity"))),
        "ROOM_IDENTITY: " + closed(str(report.get("room_identity"))),
        "OLLAMA: " + closed(str(report.get("ollama"))),
        "PROCESS_MUTATION: DISABLED",
        "AUTHORIZATION_ISSUED: NO",
        "PAID_AI_CALLS: ZERO",
        "READINESS: " + closed(str(report.get("readiness"))),
        "NEXT: local human authorization is still required before any real transaction",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BAZOR V24 live readiness, lecture seule")
    parser.add_argument(
        "--localappdata", type=Path,
        default=Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"))
    parser.add_argument("--public-only", action="store_true")
    args = parser.parse_args()

    report = audit(args.localappdata)
    print(public_summary(report))
    if not args.public_only:
        target = args.localappdata / "BAZOR" / "Reports" / "live_readiness_latest.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Rapport local enregistre sous BAZOR/Reports/live_readiness_latest.json")
    return 0 if report["readiness"] == "READY_FOR_AUTHORIZATION_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
