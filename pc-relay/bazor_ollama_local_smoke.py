"""Independent local-only BAZOR/Ollama runtime probe.

No arbitrary shell, disk writes, external provider calls or Action Engine actions.
This is NOT a multi-provider / trio E2E certification.
"""
from __future__ import annotations

import importlib
import json
import secrets
import urllib.request
from datetime import datetime, timezone

CORE = "http://127.0.0.1:8775"
ROOM = "http://127.0.0.1:8765"
OLLAMA = "http://127.0.0.1:11434"
PREFERRED_MODELS = ("qwen2.5-coder:7b", "qwen3:8b", "llama3.2:3b")


def _request_json(url, payload=None, timeout=5):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError("http_status_unexpected")
        return json.loads(response.read().decode("utf-8"))


def _action_engine_api_present():
    # Import/class inspection only. Never instantiate ActionEngine or call apply().
    try:
        cls = importlib.import_module("bazor_action_engine").ActionEngine
        return all(callable(getattr(cls, method, None)) for method in (
            "apply", "parse_actions", "available_roots",
        ))
    except (ImportError, AttributeError, RuntimeError):
        return False


def run_probe(request=None, nonce=None):
    """Run an isolated loopback check. request may be injected for offline tests."""
    request = request or _request_json
    token = nonce or ("BAZOR_LOCAL_" + secrets.token_hex(6).upper())
    report = {
        "schema": "bazor-ollama-local-probe-v1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "LOCAL_ONLY_BLOCKED",
        "model": None,
        "checks": {
            "core": False,
            "room": False,
            "ollama": False,
            "core_ollama_response": False,
            "action_engine_api": False,
        },
        "action_engine_used": False,
        "files_changed": 0,
        "paid_api_used": False,
        "mammouth_used": False,
        "trio_ready": "NOT_EVALUATED",
        "reason": "unknown",
    }

    try:
        health = request(CORE + "/api/v1/health", timeout=4)
        report["checks"]["core"] = health.get("ok") is True
    except (OSError, ValueError, RuntimeError, TimeoutError, TypeError, AttributeError):
        pass

    try:
        room = request(ROOM + "/health", timeout=4)
        report["checks"]["room"] = isinstance(room, dict) and (
            room.get("ok") is True or room.get("status") in ("ok", "healthy")
        )
    except (OSError, ValueError, RuntimeError, TimeoutError, TypeError, AttributeError):
        pass

    try:
        tags = request(OLLAMA + "/api/tags", timeout=4)
        names = [
            str(row.get("name") or row.get("model") or "")
            for row in tags.get("models", []) if isinstance(row, dict)
        ]
        report["model"] = next((m for m in PREFERRED_MODELS if m in names), None)
        report["checks"]["ollama"] = bool(report["model"])
    except (OSError, ValueError, RuntimeError, TimeoutError, TypeError, AttributeError):
        pass

    report["checks"]["action_engine_api"] = _action_engine_api_present()

    if report["checks"]["core"] and report["checks"]["ollama"]:
        try:
            response = request(
                CORE + "/api/v1/chat",
                payload={
                    "target": "ollama",
                    "model": report["model"],
                    "room": "BAZOR LOCAL PROBE",
                    "text": "Local transport check. Reply with this exact token: " + token,
                },
                timeout=70,
            )
            ollama = response.get("ollama") or {}
            report["checks"]["core_ollama_response"] = (
                response.get("ok") is True
                and response.get("target") == "ollama"
                and ollama.get("ok") is True
                and ollama.get("provider") == "ollama"
                and ollama.get("model") == report["model"]
                and token in str(ollama.get("answer") or "")
            )
        except (OSError, ValueError, RuntimeError, TimeoutError, TypeError, AttributeError):
            pass

    failed = [key for key, ok in report["checks"].items() if not ok]
    report["reason"] = "ok" if not failed else "missing:" + ",".join(failed)
    if not failed:
        report["status"] = "LOCAL_ONLY_READY"
    return report


if __name__ == "__main__":
    print(json.dumps(run_probe(), ensure_ascii=True, sort_keys=True))
