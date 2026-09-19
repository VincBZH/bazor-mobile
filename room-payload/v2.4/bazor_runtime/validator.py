from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

START = "[BAZOR_MESSAGE]"
END = "[/BAZOR_MESSAGE]"

REQUIRED_FIELDS = [
    "message_id","timestamp_local","timestamp_utc","project_id","project_name",
    "project_version","bazor_version","task_id","parent_task_id","source_agent",
    "target_agent","status","progress_percent","summary","files","tests",
    "errors","next_step","handoff_logic"
]

ALLOWED_STATUS = {
    "NEW","IN_PROGRESS","PARTIAL","RECOVERING","BLOCKED",
    "QUEUED","NEEDS_HUMAN","DONE"
}

@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    payload: Dict[str, Any]
    delivery_state: str

def _parse_scalar(value: str) -> Any:
    v = value.strip()
    if v.lower() == "null":
        return None
    if v.lower() in {"true","false"}:
        return v.lower() == "true"
    if re.fullmatch(r"-?\d+", v):
        try:
            return int(v)
        except ValueError:
            return v
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [] if not inner else [x.strip() for x in inner.split(",")]
    return v

def extract_message_block(text: str) -> Tuple[Optional[str], List[str]]:
    errors: List[str] = []
    if START not in text:
        errors.append("github_message_block_missing")
        return None, errors
    if END not in text:
        errors.append("github_message_end_missing")
        return None, errors
    start = text.index(START) + len(START)
    end = text.index(END, start)
    return text[start:end].strip(), errors

def parse_message_block(block: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    current_key: Optional[str] = None
    list_keys = {"summary","files","tests","errors","next_step","handoff_logic"}
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*:", line):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if key in list_keys:
                payload[key] = [] if value == "" else [_parse_scalar(value)]
            else:
                payload[key] = _parse_scalar(value)
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            payload.setdefault(current_key, [])
            if not isinstance(payload[current_key], list):
                payload[current_key] = [payload[current_key]]
            payload[current_key].append(_parse_scalar(stripped[2:]))
    return payload

def compute_delivery_state(payload: Dict[str, Any]) -> str:
    gates = payload.get("gates") or {}
    protocol_ready = bool(gates.get("protocol_ready", True))
    code_patched = bool(gates.get("code_patched", False))
    ci_pass = gates.get("ci_pass", False) is True
    runtime_pass = bool(gates.get("runtime_pass", False))
    evidence_present = bool(gates.get("evidence_present", False))
    artifacts_verified = bool(gates.get("all_required_artifacts_verified", False))

    if not protocol_ready:
        return "NEW"
    if not code_patched:
        return "PROTOCOL_READY"
    if not ci_pass:
        return "CODE_PATCHED"
    if not runtime_pass:
        return "CI_PASS"
    if runtime_pass and evidence_present and not artifacts_verified:
        return "RUNTIME_PASS"
    if runtime_pass and evidence_present and artifacts_verified:
        return "DELIVERED"
    return "BLOCKED"

def validate_message(text: str) -> ValidationResult:
    block, errors = extract_message_block(text)
    if block is None:
        return ValidationResult(False, errors, {}, "RECOVERING")
    payload = parse_message_block(block)

    for field in REQUIRED_FIELDS:
        if field not in payload:
            errors.append(f"missing_required_field:{field}")

    status = payload.get("status")
    if status is not None and status not in ALLOWED_STATUS:
        errors.append(f"invalid_status:{status}")

    progress = payload.get("progress_percent")
    if progress is not None:
        if not isinstance(progress, int) or not 0 <= progress <= 100:
            errors.append("invalid_progress_percent")

    logic = payload.get("handoff_logic")
    if not isinstance(logic, list) or not logic:
        errors.append("missing_handoff_logic")
    else:
        if not any(("IF " in str(x).upper() and " THEN " in str(x).upper()) for x in logic):
            errors.append("handoff_logic_without_if_then")

    if status == "DONE":
        tests = payload.get("tests") or []
        errors_field = payload.get("errors") or []
        joined = " ".join(map(str, tests)).upper()
        if "FAIL" in joined or "NOT_RUN" in joined:
            errors.append("done_with_unpassed_tests")
        if any(str(x).strip() not in {"", "NONE", "[]"} for x in errors_field):
            errors.append("done_with_errors")

    valid = len(errors) == 0
    return ValidationResult(valid, errors, payload, compute_delivery_state(payload))

def build_incident(
    validation: ValidationResult,
    *,
    source_ref: str = "",
    revision: str = "",
    provider: str = "",
    model: str = "",
    raw_excerpt: str = "",
    attempt: int = 0,
    last_successful_step: str = "",
) -> Dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    incident_id = f"INCIDENT_{now_utc.strftime('%Y%m%dT%H%M%SZ')}_{validation.payload.get('project_id','unknown')}_{validation.payload.get('task_id','unknown')}"
    return {
        "incident_id": incident_id,
        "timestamp_local": datetime.now().astimezone().isoformat(),
        "timestamp_utc": now_utc.isoformat().replace("+00:00","Z"),
        "bazor_version": validation.payload.get("bazor_version","unknown"),
        "project": validation.payload.get("project_id","unknown"),
        "project_version": validation.payload.get("project_version","unknown"),
        "task_id": validation.payload.get("task_id","unknown"),
        "status": "RECOVERING",
        "severity": "error",
        "source": validation.payload.get("source_agent","unknown"),
        "provider": provider,
        "model": model,
        "file_or_comment_ref": source_ref,
        "revision": revision,
        "error_type": "INVALID_BAZOR_MESSAGE",
        "error_message": "; ".join(validation.errors) or "unknown_error",
        "raw_message_excerpt": raw_excerpt[:2000],
        "last_successful_step": last_successful_step,
        "attempt": attempt,
        "fallback_selected": "DEFAULT_RECOVERY",
        "next_action": "validate_fallback_route"
    }

def write_incident(incident: Dict[str, Any], directory: str | Path) -> Path:
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{incident['incident_id']}.json"
    path.write_text(json.dumps(incident, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
