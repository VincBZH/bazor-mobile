import datetime
import json
import os
import subprocess
import time
import uuid
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


def _error_text(data):
    if not isinstance(data, dict):
        return ""
    err=data.get("error")
    if isinstance(err, str):
        return err.strip()
    if isinstance(err, dict):
        for key in ("message","detail","error","code","type"):
            value=err.get(key)
            if value:
                return str(value).strip()
        try:
            return json.dumps(err,ensure_ascii=False)[:800]
        except Exception:
            return str(err)[:800]
    return ""


def _candidate_profiles(selected_profile):
    # Un FileBus ne doit pas dépendre d'un seul modèle. On garde le profil
    # demandé en premier puis deux fallbacks distincts et plus économiques.
    order=[selected_profile,"general","light","recommended"]
    out=[]
    seen=set()
    for prof in order:
        model=MODEL_PROFILES.get(prof,prof)
        key=(prof,model)
        if key in seen:
            continue
        seen.add(key)
        out.append((prof,model))
    return out


def _single_chat_attempt(text, selected_profile, model, max_tokens, correlation_id):
    key = os.getenv("MAMMOUTH_API_KEY", "").strip()
    started=time.monotonic()
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": int(max_tokens),
        "stream": False,
        "temperature": 0.2
    }).encode("utf-8")

    completed = subprocess.run(
        [
            "curl.exe", "--silent", "--show-error", "--location",
            "--connect-timeout", "20", "--max-time", "90",
            "--header", "Authorization: Bearer " + key,
            "--header", "Content-Type: application/json",
            "--header", "Accept: application/json",
            "--header", "User-Agent: BAZOR-Mammouth-Client/3.2",
            "--data-binary", "@-",
            "--write-out", "\\nBAZOR_HTTP_STATUS:%{http_code}",
            MAMMOUTH_URL,
        ],
        input=payload,
        capture_output=True,
        text=False,
        timeout=100,
        check=False,
    )
    elapsed_ms=int((time.monotonic()-started)*1000)
    raw = (completed.stdout or b"").decode("utf-8", errors="replace")
    marker = "\\nBAZOR_HTTP_STATUS:"
    if marker in raw:
        body, status_text = raw.rsplit(marker, 1)
        try:
            http_status = int(status_text.strip() or "0")
        except ValueError:
            http_status = 0
    else:
        body, http_status = raw, 0

    base={
        "provider":"mammouth",
        "profile":selected_profile,
        "model":model,
        "correlation_id":correlation_id,
        "http_status":http_status,
        "elapsed_ms":elapsed_ms,
        "transport_ok":completed.returncode==0 and 0 < http_status < 500,
    }
    if completed.returncode != 0 or http_status >= 400 or http_status == 0:
        detail = ((body or "") + "\n" + (completed.stderr or b"").decode("utf-8", errors="replace")).strip()
        return {**base,
            "ok":False,
            "provider_ok":False,
            "content_valid":False,
            "error":"mammouth_http" if http_status else "mammouth_curl",
            "message":f"Mammouth HTTP {http_status}" if http_status else "curl Mammouth indisponible",
            "detail":detail[:900],
        }

    try:
        data=_parse_api_json(body)
    except Exception as exc:
        return {**base,
            "ok":False,
            "provider_ok":False,
            "content_valid":False,
            "error":"mammouth_parse_error",
            "message":str(exc)[:300],
            "body_excerpt":str(body or "")[:700],
        }

    if not isinstance(data,dict):
        return {**base,
            "ok":False,
            "provider_ok":False,
            "content_valid":False,
            "error":"mammouth_response_not_object",
        }

    api_error=_error_text(data)
    choice=(data.get("choices") or [{}])[0]
    actual_model=data.get("model") or model
    usage=data.get("usage") or {}
    estimated_cost=_estimate_cost(actual_model,usage)
    if usage:
        _record_usage(actual_model,usage,estimated_cost)

    if api_error:
        return {**base,
            "ok":False,
            "provider_ok":False,
            "content_valid":False,
            "error":"mammouth_api_error",
            "model":actual_model,
            "message":api_error[:800],
            "response_keys":sorted(data.keys()),
            "choice_keys":sorted(choice.keys()) if isinstance(choice,dict) else [],
            "finish_reason":choice.get("finish_reason") if isinstance(choice,dict) else None,
            "usage":usage,
        }

    answer=_extract_answer(data)
    if not answer:
        return {**base,
            "ok":False,
            "provider_ok":True,
            "content_valid":False,
            "error":"mammouth_empty_answer",
            "model":actual_model,
            "message":"Mammouth a répondu sans texte exploitable.",
            "response_keys":sorted(data.keys()),
            "choice_keys":sorted(choice.keys()) if isinstance(choice,dict) else [],
            "finish_reason":choice.get("finish_reason") if isinstance(choice,dict) else None,
            "usage":usage,
        }

    return {**base,
        "ok":True,
        "provider_ok":True,
        "content_valid":True,
        "model":actual_model,
        "answer":answer,
        "usage":usage,
        "estimated_cost_usd":None if estimated_cost is None else round(estimated_cost,6),
    }


def chat(text, task_kind="general", profile=None, max_tokens=3000):
    key = os.getenv("MAMMOUTH_API_KEY", "").strip()
    selected_profile = profile or choose_profile(task_kind)
    selected_model = MODEL_PROFILES.get(selected_profile, selected_profile)
    correlation_id="mammouth-"+uuid.uuid4().hex[:12]

    if not key:
        return {
            "ok": False, "transport_ok":False, "provider_ok":False, "content_valid":False,
            "error": "mammouth_key_missing", "provider": "mammouth",
            "profile": selected_profile, "model": selected_model,
            "correlation_id":correlation_id,
            "message": "MAMMOUTH_API_KEY non configurée sur le PC."
        }

    budget = budget_status()
    if budget["blocked"]:
        return {
            "ok": False, "transport_ok":True, "provider_ok":False, "content_valid":False,
            "error": "mammouth_budget_reached", "provider": "mammouth",
            "profile": selected_profile, "model": selected_model,
            "correlation_id":correlation_id,
            "budget": budget, "message": "Plafond mensuel Mammouth atteint dans BAZOR."
        }

    attempts=[]
    for prof,model in _candidate_profiles(selected_profile):
        # Ne pas engager un nouvel appel si le budget vient d'être atteint.
        if budget_status().get("blocked"):
            attempts.append({"profile":prof,"model":model,"error":"budget_reached_before_attempt"})
            break
        try:
            result=_single_chat_attempt(text,prof,model,max_tokens,correlation_id)
        except Exception as exc:
            result={
                "ok":False,"transport_ok":False,"provider_ok":False,"content_valid":False,
                "provider":"mammouth","profile":prof,"model":model,
                "correlation_id":correlation_id,"error":"mammouth_error",
                "message":str(exc)[:300],
            }
        attempts.append({
            "profile":prof,
            "model":result.get("model") or model,
            "ok":bool(result.get("ok")),
            "http_status":result.get("http_status"),
            "elapsed_ms":result.get("elapsed_ms"),
            "transport_ok":bool(result.get("transport_ok")),
            "provider_ok":bool(result.get("provider_ok")),
            "content_valid":bool(result.get("content_valid")),
            "error":result.get("error"),
            "message":str(result.get("message") or "")[:240],
        })
        if result.get("ok") and result.get("content_valid"):
            result["attempts"]=attempts
            result["fallback_used"]=len(attempts)>1
            result["budget"]=budget_status()
            return result

    last=(result if "result" in locals() else {})
    return {
        **last,
        "ok":False,
        "provider":"mammouth",
        "profile":selected_profile,
        "model":last.get("model") or selected_model,
        "correlation_id":correlation_id,
        "transport_ok":any(bool(x.get("transport_ok")) for x in attempts),
        "provider_ok":any(bool(x.get("provider_ok")) for x in attempts),
        "content_valid":False,
        "error":last.get("error") or "mammouth_all_attempts_failed",
        "message":last.get("message") or "Tous les profils Mammouth testés ont échoué.",
        "attempts":attempts,
        "budget":budget_status(),
    }

