from __future__ import annotations

import datetime as dt
import json
import os
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path

NOTRACK_URL = "https://api.notrack.ai/v1/chat/completions"
NOTRACK_MODEL = "notrack-uncensored"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("BAZOR_DATA_DIR") or (BASE_DIR / "BAZOR_DATA")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
_USAGE_LOCK = threading.Lock()


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def enabled():
    return _truthy(os.getenv("BAZOR_NOTRACK_ENABLED", ""))


def has_key():
    return bool(os.getenv("NOTRACK_API_KEY", "").strip())


def configured():
    return enabled() and has_key()


def daily_call_cap():
    try:
        return max(0, int(os.getenv("BAZOR_NOTRACK_DAILY_CALL_CAP", "0")))
    except (TypeError, ValueError):
        return 0


def _day_key():
    return dt.datetime.now().astimezone().date().isoformat()


def _usage_file():
    return DATA_DIR / f"notrack_usage_{_day_key()}.json"


def usage_state():
    path = _usage_file()
    if not path.exists():
        return {"day": _day_key(), "attempted_calls": 0, "successful_calls": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "day": _day_key(),
            "attempted_calls": int(data.get("attempted_calls", 0) or 0),
            "successful_calls": int(data.get("successful_calls", 0) or 0),
        }
    except Exception:
        return {"day": _day_key(), "attempted_calls": 0, "successful_calls": 0}


def status():
    state = usage_state()
    cap = daily_call_cap()
    attempted = state["attempted_calls"]
    return {
        "enabled": enabled(),
        "key_present": has_key(),
        "configured": configured(),
        "model": NOTRACK_MODEL,
        "daily_call_cap": cap,
        "attempted_calls": attempted,
        "successful_calls": state["successful_calls"],
        "remaining_calls": max(0, cap - attempted),
        "blocked": (not configured()) or cap <= 0 or attempted >= cap,
        "day": _day_key(),
    }


def _record_attempt():
    with _USAGE_LOCK:
        state = usage_state()
        state["attempted_calls"] += 1
        _usage_file().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _mark_last_attempt_success():
    with _USAGE_LOCK:
        state = usage_state()
        state["successful_calls"] += 1
        _usage_file().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _redact_text(value, limit=1200):
    text = str(value or "")
    secret = os.getenv("NOTRACK_API_KEY", "").strip()
    if secret:
        text = text.replace(secret, "[REDACTED]")
    return text[:limit]


def _request(payload, key, timeout):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        NOTRACK_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "BAZOR-NoTrack-Client/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError("notrack_response_too_large")
        return int(getattr(response, "status", 200) or 200), raw.decode("utf-8", errors="replace")


def _error_type(body):
    try:
        data = json.loads(body or "{}")
    except Exception:
        return ""
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        return str(err.get("type") or "").strip()
    return ""


def chat(text, max_tokens=2000, timeout=90, request_id=None):
    correlation_id = request_id or "notrack-" + uuid.uuid4().hex[:12]
    if not isinstance(text, str) or not text.strip() or len(text) > 48000:
        return {"ok": False, "provider": "notrack", "error": "notrack_limits_exceeded",
                "correlation_id": correlation_id}
    if not isinstance(max_tokens, int) or not 1 <= max_tokens <= 3000:
        return {"ok": False, "provider": "notrack", "error": "notrack_limits_exceeded",
                "correlation_id": correlation_id}
    if not enabled():
        return {"ok": False, "provider": "notrack", "error": "notrack_disabled",
                "correlation_id": correlation_id,
                "message": "NoTrack est désactivé dans BAZOR."}
    key = os.getenv("NOTRACK_API_KEY", "").strip()
    if not key:
        return {"ok": False, "provider": "notrack", "error": "notrack_key_missing",
                "correlation_id": correlation_id,
                "message": "NOTRACK_API_KEY non configurée sur le PC."}

    before = status()
    if before["daily_call_cap"] <= 0:
        return {"ok": False, "provider": "notrack", "error": "notrack_explicit_cap_required",
                "correlation_id": correlation_id, "status": before,
                "message": "Un plafond quotidien positif est requis avant tout appel NoTrack."}
    if before["attempted_calls"] >= before["daily_call_cap"]:
        return {"ok": False, "provider": "notrack", "error": "notrack_daily_cap_reached",
                "correlation_id": correlation_id, "status": before,
                "message": "Plafond quotidien NoTrack atteint dans BAZOR."}

    _record_attempt()
    payload = {
        "model": NOTRACK_MODEL,
        "messages": [{"role": "user", "content": text.strip()}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": False,
    }
    try:
        http_status, body = _request(payload, key, timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read(8192).decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        typ = _error_type(body)
        if exc.code == 401:
            code = "notrack_auth"
        elif exc.code == 402 and typ == "key_daily_cap":
            code = "notrack_provider_daily_cap"
        elif exc.code == 402:
            code = "notrack_no_credit"
        elif exc.code == 403:
            code = "notrack_content_policy"
        elif exc.code == 429:
            code = "notrack_rate_limited"
        else:
            code = "notrack_http"
        return {"ok": False, "provider": "notrack", "error": code,
                "http_status": int(exc.code), "provider_error_type": typ,
                "correlation_id": correlation_id, "detail": _redact_text(body),
                "status": status()}
    except Exception as exc:
        return {"ok": False, "provider": "notrack", "error": "notrack_transport",
                "correlation_id": correlation_id, "detail": _redact_text(exc),
                "status": status()}

    try:
        data = json.loads(body)
    except Exception as exc:
        return {"ok": False, "provider": "notrack", "error": "notrack_parse_error",
                "http_status": http_status, "correlation_id": correlation_id,
                "detail": _redact_text(exc), "status": status()}

    choices = data.get("choices") if isinstance(data, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    answer = str(message.get("content") or choice.get("text") or "").strip()
    if not answer:
        typ = _error_type(body)
        return {"ok": False, "provider": "notrack", "error": "notrack_empty_answer",
                "http_status": http_status, "provider_error_type": typ,
                "correlation_id": correlation_id, "status": status()}

    _mark_last_attempt_success()
    return {
        "ok": True,
        "provider": "notrack",
        "model": str(data.get("model") or NOTRACK_MODEL),
        "answer": _redact_text(answer, limit=32000),
        "http_status": http_status,
        "correlation_id": correlation_id,
        "usage": data.get("usage") or {},
        "status": status(),
    }
