import datetime
import json
import os
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

MAMMOUTH_URL = "https://api.mammouth.ai/v1/chat/completions"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "BAZOR_DATA"
DATA_DIR.mkdir(parents=True, exist_ok=True)
_USAGE_LOCK = threading.Lock()

# Upper-bound prices from Mammouth docs, USD per 1M tokens.
MODEL_PRICES = {
    "mistral-small-3.2-24b-instruct": (0.10, 0.30),
    "qwen3.8-flash": (0.15, 0.47),
    "glm-5.3-flash": (0.15, 0.50),
    "deepseek-v4-flash": (0.14, 0.28),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.1-pro-preview": (2.00, 12.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
    "gpt-5.6-luna": (1.00, 6.00),
    "gpt-5.6-terra": (2.50, 15.00),
    "gpt-5.6-sol": (5.00, 30.00),
}

# Routage BAZOR : les travaux lourds utilisent un modèle fort adapté.
# Les profils économiques restent disponibles explicitement.
MODEL_PROFILES = {
    "light": "mistral-small-3.2-24b-instruct",
    "code": "claude-sonnet-5",
    "general": "gpt-5.6-luna",
    "analysis": "gpt-5.6-terra",
    "complex": "gpt-5.6-sol",
    "strongest": "gpt-5.6-sol",
    "recommended": "mammouth-recommended",
    "claude": "claude-sonnet-5",
    "gemini": "gemini-3.1-pro-preview",
    "mistral": "mistral-small-3.2-24b-instruct",
    "deepseek": "deepseek-v4-flash",
    "qwen": "qwen3.8-flash",
    "gpt": "gpt-5.6-sol",
    "gpt_luna": "gpt-5.6-luna",
    "gpt_terra": "gpt-5.6-terra",
    "gpt_sol": "gpt-5.6-sol",
}


def configured():
    return bool(os.getenv("MAMMOUTH_API_KEY", "").strip())


def monthly_budget_usd():
    try:
        return max(0.0, float(os.getenv("BAZOR_MAMMOUTH_BUDGET_USD", "4")))
    except ValueError:
        return 4.0


def _month_key():
    return datetime.datetime.now().strftime("%Y-%m")


def _usage_file():
    return DATA_DIR / f"mammouth_usage_{_month_key()}.json"


def usage_state():
    path = _usage_file()
    if not path.exists():
        return {"month": _month_key(), "estimated_spent_usd": 0.0, "calls": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("month", _month_key())
        data.setdefault("estimated_spent_usd", 0.0)
        data.setdefault("calls", 0)
        return data
    except Exception:
        return {"month": _month_key(), "estimated_spent_usd": 0.0, "calls": 0}


def budget_status():
    state = usage_state()
    budget = monthly_budget_usd()
    spent = float(state.get("estimated_spent_usd", 0.0) or 0.0)
    return {
        "budget_usd": budget,
        "estimated_spent_usd": round(spent, 6),
        "remaining_usd": round(max(0.0, budget - spent), 6),
        "calls": int(state.get("calls", 0) or 0),
        "blocked": budget > 0 and spent >= budget,
        "month": _month_key(),
    }


def choose_profile(task_kind="general"):
    if task_kind in MODEL_PROFILES:
        return task_kind
    return "general"


def _estimate_cost(model, usage):
    prompt = int((usage or {}).get("prompt_tokens") or 0)
    completion = int((usage or {}).get("completion_tokens") or 0)
    prices = MODEL_PRICES.get(model)
    if not prices:
        return None
    input_price, output_price = prices
    return (prompt / 1_000_000.0) * input_price + (completion / 1_000_000.0) * output_price


def _record_usage(model, usage, estimated_cost):
    # Deux secondes lectures peuvent tourner en parallèle. Sérialiser uniquement
    # la mise à jour du compteur/budget pour ne perdre aucun appel ni coût.
    with _USAGE_LOCK:
        state = usage_state()
        state["calls"] = int(state.get("calls", 0) or 0) + 1
        state["last_model"] = model
        state["last_usage"] = usage or {}
        state["last_call"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        if estimated_cost is not None:
            state["estimated_spent_usd"] = float(state.get("estimated_spent_usd", 0.0) or 0.0) + float(estimated_cost)
        _usage_file().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def _parse_api_json(body):
    """Tolère les réponses Mammouth contenant plusieurs objets JSON concaténés.
    Certains proxys/API ajoutent un objet ou une ligne JSON après la réponse principale.
    On préfère l'objet OpenAI-compatible contenant choices, puis un éventuel error.
    """
    text = str(body or "").strip()
    if not text:
        raise ValueError("mammouth_empty_body")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        objects = []
        pos = 0
        while pos < len(text):
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if pos >= len(text):
                break
            try:
                obj, end = decoder.raw_decode(text, pos)
                objects.append(obj)
                pos = end
                continue
            except json.JSONDecodeError:
                nxt = [x for x in (text.find("{", pos + 1), text.find("[", pos + 1)) if x >= 0]
                if not nxt:
                    break
                pos = min(nxt)
        for obj in objects:
            if isinstance(obj, dict) and "choices" in obj:
                return obj
        for obj in objects:
            if isinstance(obj, dict) and "error" in obj:
                return obj
        if objects:
            return objects[-1]
        raise


def _content_text(value):
    """Normalise les formats OpenAI texte, liste de parties ou objet imbrique."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(filter(None, (_content_text(item) for item in value))).strip()
    if isinstance(value, dict):
        for key in ("text", "output_text", "content", "value"):
            text = _content_text(value.get(key))
            if text:
                return text
    return ""


def _extract_answer(data):
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        choice = choices[0]
        message = choice.get("message") or {}
        candidates = [
            message.get("content") if isinstance(message, dict) else None,
            message.get("refusal") if isinstance(message, dict) else None,
            choice.get("text"),
            (choice.get("delta") or {}).get("content") if isinstance(choice.get("delta"), dict) else None,
        ]
        for candidate in candidates:
            text = _content_text(candidate)
            if text:
                return text
    for key in ("output_text", "answer", "response", "content", "output"):
        text = _content_text(data.get(key))
        if text:
            return text
    return ""


def chat(text, task_kind="general", profile=None, max_tokens=3000):
    key = os.getenv("MAMMOUTH_API_KEY", "").strip()
    selected_profile = profile or choose_profile(task_kind)
    model = MODEL_PROFILES.get(selected_profile, selected_profile)

    if not key:
        return {
            "ok": False,
            "error": "mammouth_key_missing",
            "provider": "mammouth",
            "profile": selected_profile,
            "model": model,
            "message": "MAMMOUTH_API_KEY non configurée sur le PC."
        }

    budget = budget_status()
    if budget["blocked"]:
        return {
            "ok": False,
            "error": "mammouth_budget_reached",
            "provider": "mammouth",
            "profile": selected_profile,
            "model": model,
            "budget": budget,
            "message": "Plafond mensuel Mammouth atteint dans BAZOR."
        }

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": int(max_tokens),
        "stream": False,
        "temperature": 0.2
    }).encode("utf-8")

    try:
        completed = subprocess.run(
            [
                "curl.exe", "--silent", "--show-error", "--location",
                "--connect-timeout", "20", "--max-time", "240",
                "--header", "Authorization: Bearer " + key,
                "--header", "Content-Type: application/json",
                "--header", "Accept: application/json",
                "--header", "User-Agent: BAZOR-Mammouth-Client/3.1",
                "--data-binary", "@-",
                "--write-out", "\\nBAZOR_HTTP_STATUS:%{http_code}",
                MAMMOUTH_URL,
            ],
            input=payload,
            capture_output=True,
            text=False,
            timeout=250,
            check=False,
        )
        raw = (completed.stdout or b"").decode("utf-8", errors="replace")
        marker = "\\nBAZOR_HTTP_STATUS:"
        if marker in raw:
            body, status_text = raw.rsplit(marker, 1)
            http_status = int(status_text.strip() or "0")
        else:
            body, http_status = raw, 0
        if completed.returncode != 0 or http_status >= 400:
            detail = ((body or "") + "\\n" + (completed.stderr or b"").decode("utf-8", errors="replace")).strip()
            return {
                "ok": False,
                "error": "mammouth_http" if http_status else "mammouth_curl",
                "provider": "mammouth",
                "profile": selected_profile,
                "model": model,
                "message": f"Mammouth HTTP {http_status}" if http_status else "curl Mammouth indisponible",
                "detail": detail[:600],
                "budget": budget_status(),
            }
        data = _parse_api_json(body)
        if not isinstance(data, dict):
            raise ValueError("mammouth_response_not_object")
        choice = (data.get("choices") or [{}])[0]
        actual_model = data.get("model") or model
        usage = data.get("usage") or {}
        estimated_cost = _estimate_cost(actual_model, usage)
        _record_usage(actual_model, usage, estimated_cost)
        answer = _extract_answer(data)
        if not answer:
            diagnostic = {
                "response_keys": sorted(data.keys()),
                "choice_keys": sorted(choice.keys()) if isinstance(choice, dict) else [],
                "finish_reason": choice.get("finish_reason") if isinstance(choice, dict) else None,
                "usage": usage,
            }
            return {
                "ok": False,
                "error": "mammouth_empty_answer",
                "provider": "mammouth",
                "profile": selected_profile,
                "model": actual_model,
                "message": "Mammouth a repondu sans texte exploitable: " + json.dumps(diagnostic, ensure_ascii=False)[:500],
                "usage": usage,
                "estimated_cost_usd": None if estimated_cost is None else round(estimated_cost, 6),
                "budget": budget_status(),
            }
        return {
            "ok": True,
            "provider": "mammouth",
            "profile": selected_profile,
            "model": actual_model,
            "answer": answer,
            "usage": usage,
            "estimated_cost_usd": None if estimated_cost is None else round(estimated_cost, 6),
            "budget": budget_status(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": "mammouth_error",
            "provider": "mammouth",
            "profile": selected_profile,
            "model": model,
            "message": str(exc)[:300],
            "budget": budget_status(),
        }
