"""Read-only BAZOR isolated-runtime probe; one local Ollama turn only with explicit opt-in.

Unlike the one-click launcher, this file DOES NOT start, stop, replace or
install services. It never contacts GitHub, Mammouth or the OpenAI API.
A 200 HTTP response alone is not evidence of an operational Core or AI Room.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import bazor_multiai_oneclick as oneclick

CORE_PORT = 8875
ROOM_PORT = 8768
STATIC_MARKER = "BAZOR_LOCAL_OK"
PRODUCTION_CORE = "http://127.0.0.1:8775/api/v1/health"
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


def check(root: Path, *, allow_local_chat: bool = False, fetch=None) -> dict:
    """Fixed loopback endpoints only; publishes a fixed, non-sensitive report."""
    if fetch is None:
        fetch = oneclick.local_json
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
    live_room_before = local(PRODUCTION_ROOM)
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
    live_room_after = local(PRODUCTION_ROOM)
    report["production_core"] = stable_live(live_core_before, live_core_after)
    report["production_room"] = stable_live(live_room_before, live_room_after)
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
