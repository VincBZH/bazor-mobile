from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class EngineState:
    available: bool
    credits_ok: Optional[bool] = None
    model: Optional[str] = None
    local: bool = False

def choose_route(task: Dict[str, Any], engines: Dict[str, EngineState]) -> Dict[str, Any]:
    task_class = task.get("task_class", "simple")
    critical = bool(task.get("critical", False))

    gpt = engines.get("gpt", EngineState(False))
    mammouth = engines.get("mammouth", EngineState(False))
    ollama = engines.get("ollama", EngineState(False, local=True))

    if critical and gpt.available and mammouth.available:
        return {
            "primary": "gpt" if task_class in {"architecture","synthesis","arbitration"} else "mammouth",
            "cross_check": "mammouth" if task_class in {"architecture","synthesis","arbitration"} else "gpt",
            "reason": "critical_cross_check"
        }

    if task_class in {"simple","local"} and ollama.available:
        return {"primary":"ollama","reason":"local_priority"}

    if task_class in {"architecture","synthesis","arbitration"} and gpt.available:
        return {"primary":"gpt","reason":"gpt_best_fit"}

    if task_class in {"complex","second_opinion"} and mammouth.available:
        return {"primary":"mammouth","model":"auto","reason":"mammouth_best_fit"}

    if gpt.available:
        return {"primary":"gpt","reason":"fallback_gpt"}

    if mammouth.available:
        return {"primary":"mammouth","model":"auto","reason":"fallback_mammouth"}

    if ollama.available:
        return {"primary":"ollama","external_tasks":"queue","reason":"local_only"}

    return {"primary":None,"status":"QUEUED","reason":"no_engine_available"}

def recovery_route(
    *,
    transient: bool,
    attempt: int,
    identical_error_count: int,
    current_provider: str,
    engines: Dict[str, EngineState],
    ollama_compatible: bool = True,
) -> Dict[str, Any]:
    if transient and attempt < 1:
        return {"action":"retry_same_provider_once","provider":current_provider}

    if identical_error_count >= 2:
        order = ["gpt","mammouth","ollama"]
        for candidate in order:
            if candidate == current_provider:
                continue
            st = engines.get(candidate)
            if st and st.available and (candidate != "ollama" or ollama_compatible):
                return {"action":"switch_provider","provider":candidate}
        return {"action":"queue","status":"QUEUED"}

    for candidate in ["gpt","mammouth","ollama"]:
        if candidate == current_provider:
            continue
        st = engines.get(candidate)
        if st and st.available and (candidate != "ollama" or ollama_compatible):
            return {"action":"switch_provider","provider":candidate}

    return {"action":"queue","status":"QUEUED"}
