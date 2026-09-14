import json
import os
import urllib.error
import urllib.request

MAMMOUTH_URL = "https://api.mammouth.ai/v1/chat/completions"

# BAZOR policy: economical choices first. User can still force a provider/model.
MODEL_PROFILES = {
    "recommended": "mammouth-recommended",
    "cheap": "glm-5.3-flash",
    "code": "qwen3.8-flash",
    "analysis": "mistral-small-3.2-24b-instruct",
    "claude": "claude-haiku-4-5",
    "gemini": "gemini-3.8-flash",
    "mistral": "mistral-small-3.2-24b-instruct",
    "deepseek": "deepseek-v4-flash",
    "qwen": "qwen3.8-flash",
}


def configured():
    return bool(os.getenv("MAMMOUTH_API_KEY", "").strip())


def choose_profile(task_kind="general"):
    if task_kind == "code":
        return "code"
    if task_kind == "light":
        return "cheap"
    if task_kind == "analysis":
        return "analysis"
    return "recommended"


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
        return {
            "ok": True,
            "provider": "mammouth",
            "profile": selected_profile,
            "model": data.get("model") or model,
            "answer": (message.get("content") or "").strip(),
            "usage": data.get("usage") or {}
        }
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")[:400]
        except Exception:
            detail = ""
        return {
            "ok": False,
            "error": "mammouth_http",
            "provider": "mammouth",
            "profile": selected_profile,
            "model": model,
            "message": f"Mammouth HTTP {exc.code}",
            "detail": detail
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": "mammouth_error",
            "provider": "mammouth",
            "profile": selected_profile,
            "model": model,
            "message": str(exc)[:300]
        }
