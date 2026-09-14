import datetime
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

MAMMOUTH_URL = "https://api.mammouth.ai/v1/chat/completions"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "BAZOR_DATA"
DATA_DIR.mkdir(parents=True, exist_ok=True)

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

MODEL_PROFILES = {
    "light": "mistral-small-3.2-24b-instruct",
    "code": "qwen3.8-flash",
    "general": "glm-5.3-flash",
    "analysis": "gemini-3.8-flash",
    "complex": "claude-sonnet-5",
    "recommended": "mammouth-recommended",
    "claude": "claude-sonnet-5",
    "gemini": "gemini-3.8-flash",
    "mistral": "mistral-small-3.2-24b-instruct",
    "deepseek": "deepseek-v4-flash",
    "qwen": "qwen3.8-flash",
    "gpt": "gpt-5.6-luna",
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
    state = usage_state()
    state["calls"] = int(state.get("calls", 0) or 0) + 1
    state["last_model"] = model
    state["last_usage"] = usage or {}
    state["last_call"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    if estimated_cost is not None:
        state["estimated_spent_usd"] = float(state.get("estimated_spent_usd", 0.0) or 0.0) + float(estimated_cost)
    _usage_file().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


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

    req = urllib.request.Request(
        MAMMOUTH_URL,
        data=payload,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=240) as response:
            data = json.loads(response.read().decode("utf-8"))
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        actual_model = data.get("model") or model
        usage = data.get("usage") or {}
        estimated_cost = _estimate_cost(actual_model, usage)
        _record_usage(actual_model, usage, estimated_cost)
        return {
            "ok": True,
            "provider": "mammouth",
            "profile": selected_profile,
            "model": actual_model,
            "answer": (message.get("content") or "").strip(),
            "usage": usage,
            "estimated_cost_usd": None if estimated_cost is None else round(estimated_cost, 6),
            "budget": budget_status(),
        }
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")[:600]
        except Exception:
            detail = ""
        return {
            "ok": False,
            "error": "mammouth_http",
            "provider": "mammouth",
            "profile": selected_profile,
            "model": model,
            "message": f"Mammouth HTTP {exc.code}",
            "detail": detail,
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
