"""Private, read-only observer for the existing BAZOR Studio and ComfyUI.

Never submits a generation, starts a service, or publishes a prompt. The observer
can run once during the boot inventory or continuously with pythonw.exe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime


STUDIO_URL = "http://127.0.0.1:8191"
COMFY_URL = "http://127.0.0.1:8188"
DEFAULT_STUDIO = Path(os.environ.get("BAZOR_STUDIO_ROOT", r"C:\AI\SimpleStudioV2"))
DEFAULT_COMFY = Path(
    os.environ.get("BAZOR_COMFY_ROOT", r"C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI")
)
DEFAULT_OUTPUT = Path(os.environ.get("BAZOR_STUDIO_LOG_DIR", "")) if os.environ.get(
    "BAZOR_STUDIO_LOG_DIR"
) else Path.home() / "Documents" / "BAZOR" / "Studio"
ERROR_RX = re.compile(r"\b(error|exception|traceback|fatal|failed|échec|erreur)\b|\bHTTP\s*[45]\d\d\b", re.I)
SECRET_RULES = (
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+"), r"\1<masqué>"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})\b"), "<clé masquée>"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"), r"\1=<masqué>"),
)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean(value: object, limit: int = 500) -> str:
    result = str(value if value is not None else "")
    home = str(Path.home())
    if home:
        result = result.replace(home, "<UTILISATEUR>").replace(home.replace("\\", "/"), "<UTILISATEUR>")
    for pattern, replacement in SECRET_RULES:
        result = pattern.sub(replacement, result)
    return result[:limit]


def preview(value: object) -> dict:
    source = str(value or "")
    words = clean(source.replace("\r", " ").replace("\n", " "), 600).split()
    hint = " ".join(words[:8]) + "…" if len(words) > 8 else ("[prompt court masqué]" if words else "")
    return {
        "prompt_preview": hint,
        "prompt_chars": len(source),
        "prompt_sha256": hashlib.sha256(source.encode("utf-8", "replace")).hexdigest() if source else None,
    }


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def request_json(url: str, max_bytes: int = 1_500_000) -> tuple[object | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=2.5) as response:
            if response.status != 200:
                return None, "HTTP " + str(response.status)
            data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            return None, "réponse trop grande"
        return json.loads(data.decode("utf-8")), None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return None, clean(type(exc).__name__ + ": " + str(exc), 180)


def probe_service(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def studio_jobs(data: object) -> list[dict]:
    rows = data
    if isinstance(data, dict):
        rows = next((data[key] for key in ("jobs", "items", "results") if isinstance(data.get(key), list)), [])
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows[-25:]:
        if not isinstance(row, dict):
            continue
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        prompt = params.get("prompt") or row.get("prompt") or ""
        def numeric(key):
            value = params.get(key)
            return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        item = {
            "id": clean(row.get("id") or row.get("job_id"), 90),
            "prompt_id": clean(row.get("prompt_id"), 90),
            "state": clean(row.get("status") or row.get("state"), 90),
            "mode": clean(params.get("mode") or row.get("mode"), 90),
            "width": numeric("width"),
            "height": numeric("height"),
            "frames": numeric("frames") or numeric("length"),
            "steps": numeric("steps"),
            "seed": numeric("seed"),
            "created": clean(row.get("created_at") or row.get("created"), 90),
            "error": clean(row.get("error") or row.get("exception") or row.get("detail"), 900),
            **preview(prompt),
        }
        result.append(item)
    return result


def _graph_details(entry: dict) -> dict:
    graph = entry.get("prompt")
    if isinstance(graph, list) and len(graph) > 2:
        graph = graph[2]
    if not isinstance(graph, dict):
        return {}
    details = {"classes": [], "dimensions": [], "prompts": []}
    for node in list(graph.values())[:100]:
        if not isinstance(node, dict):
            continue
        cls = clean(node.get("class_type"), 90)
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        if cls and cls not in details["classes"]:
            details["classes"].append(cls)
        if "width" in inputs and "height" in inputs:
            details["dimensions"].append({
                "class": cls, "width": inputs["width"], "height": inputs["height"],
                "length": inputs.get("length") or inputs.get("frames"),
            })
        if isinstance(inputs.get("text"), str):
            details["prompts"].append(preview(inputs["text"]))
    details["classes"] = details["classes"][:30]
    details["dimensions"] = details["dimensions"][:5]
    details["prompts"] = details["prompts"][:3]
    return details


def comfy_history(data: object) -> list[dict]:
    if not isinstance(data, dict):
        return []
    result = []
    for prompt_id, value in list(data.items())[-12:]:
        if not isinstance(value, dict):
            continue
        status = value.get("status") if isinstance(value.get("status"), dict) else {}
        errors = []
        messages = status.get("messages")
        for message in (messages[-10:] if isinstance(messages, list) else []):
            if isinstance(message, (list, tuple)) and len(message) >= 2 and "error" in str(message[0]).lower():
                payload = message[1] if isinstance(message[1], dict) else {}
                errors.append(clean(payload.get("exception_message") or payload.get("message") or message[0], 900))
        outputs = []
        for node in list((value.get("outputs") or {}).values())[:25]:
            if not isinstance(node, dict):
                continue
            for kind in ("images", "videos", "gifs"):
                assets = node.get(kind)
                for asset in (assets[:4] if isinstance(assets, list) else []):
                    if isinstance(asset, dict):
                        outputs.append({
                            "kind": kind,
                            "filename": clean(asset.get("filename"), 240),
                            "subfolder": clean(asset.get("subfolder"), 240),
                            "type": clean(asset.get("type"), 30),
                        })
        result.append({
            "prompt_id": clean(prompt_id, 90),
            "state": clean(status.get("status_str"), 90),
            "errors": errors[:5],
            "outputs": outputs[:8],
            **_graph_details(value),
        })
    return result


def _log_errors(studio_root: Path, offsets: dict) -> tuple[list[dict], dict]:
    events = []
    candidates = []
    for folder in (studio_root / "logs", studio_root / "app" / "logs"):
        try:
            candidates.extend(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".log", ".txt", ".jsonl"))
        except OSError:
            continue
    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0

    for path in sorted(candidates, key=mtime, reverse=True)[:12]:
        key = str(path)
        try:
            size = path.stat().st_size
            start = min(int(offsets.get(key, max(0, size - 64_000))), size)
            with path.open("rb") as stream:
                stream.seek(start)
                chunk = stream.read(128_000)
                offsets[key] = stream.tell()
            for line in chunk.decode("utf-8", "replace").splitlines()[-400:]:
                if ERROR_RX.search(line):
                    events.append({"source": path.name, "message": clean(line, 900)})
        except (OSError, ValueError):
            continue
    return events[-30:], offsets


def _safe_output(comfy_root: Path, asset: dict) -> Path | None:
    if asset.get("type") != "output":
        return None
    name = str(asset.get("filename") or "")
    subfolder = str(asset.get("subfolder") or "")
    if not name or Path(name).name != name or Path(subfolder).is_absolute():
        return None
    base = (comfy_root / "output").resolve()
    candidate = (base / subfolder / name).resolve()
    try:
        if candidate.is_relative_to(base) and candidate.is_file():
            return candidate
    except OSError:
        pass
    return None


def _thumbnail(history: list[dict], comfy_root: Path, out_dir: Path) -> str | None:
    ffmpeg = os.environ.get("BAZOR_FFMPEG") or shutil.which("ffmpeg")
    for item in reversed(history):
        for asset in item.get("outputs", []):
            source = _safe_output(comfy_root, asset)
            if source is None:
                continue
            thumb = out_dir / "thumbnails" / (hashlib.sha256(str(source).encode()).hexdigest()[:20] + ".jpg")
            if thumb.is_file():
                return str(thumb)
            thumb.parent.mkdir(parents=True, exist_ok=True)
            try:
                if ffmpeg:
                    cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i",
                           str(source), "-frames:v", "1", "-vf", "scale=320:-1", "-q:v", "5", str(thumb)]
                    cp = subprocess.run(cmd, capture_output=True, timeout=20,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    if cp.returncode == 0 and thumb.is_file():
                        return str(thumb)
                else:
                    from PIL import Image  # optional, use the existing installation
                    with Image.open(source) as image:
                        image.thumbnail((320, 320))
                        image.convert("RGB").save(thumb, "JPEG", quality=75)
                    return str(thumb)
            except (OSError, subprocess.TimeoutExpired, ImportError, ValueError):
                thumb.unlink(missing_ok=True)
    return None


def _append_event(out_dir: Path, event: dict) -> None:
    path = out_dir / "events.jsonl"
    if path.exists() and path.stat().st_size > 5_000_000:
        for index in range(4, 0, -1):
            old = out_dir / ("events.jsonl." + str(index))
            new = out_dir / ("events.jsonl." + str(index + 1))
            if index == 4:
                old.unlink(missing_ok=True)
            elif old.exists():
                os.replace(old, new)
        os.replace(path, out_dir / "events.jsonl.1")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


def poll_once(out_dir: Path, studio_root: Path, comfy_root: Path, capture_thumbnail: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    state_file = out_dir / "observer_state.json"
    state = read_json(state_file)
    jobs_raw, studio_error = request_json(STUDIO_URL + "/api/jobs")
    history_raw, comfy_error = request_json(COMFY_URL + "/history?max_items=12")
    jobs, history = studio_jobs(jobs_raw), comfy_history(history_raw)
    console_errors, offsets = _log_errors(studio_root, state.get("offsets", {}))
    thumbnail = _thumbnail(history, comfy_root, out_dir) if capture_thumbnail else None
    report = {
        "generated_at": now(),
        "studio": {"reachable": studio_error is None or probe_service(STUDIO_URL + "/"),
                   "jobs_error": studio_error},
        "comfy": {"reachable": comfy_error is None or probe_service(COMFY_URL + "/system_stats"),
                  "history_error": comfy_error},
        "jobs": jobs,
        "history": history,
        "console_errors": console_errors,
        "latest_thumbnail": thumbnail,
        "log_dir": str(out_dir),
        "event_log": str(out_dir / "events.jsonl"),
        "limitations": [
            "Une erreur limitée à l'interface du navigateur n'est pas visible si Studio ne la journalise pas.",
            "Les sorties console non redirigées vers un fichier ne sont pas récupérables rétroactivement.",
        ],
    }
    seen = list(state.get("seen", []))[-350:]
    seen_set = set(seen)
    candidates = ([{"kind": "studio", **item} for item in jobs]
                  + [{"kind": "comfy", **item} for item in history]
                  + [{"kind": "console_error", **item} for item in console_errors])
    for item in candidates:
        digest = hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()
        if digest not in seen_set:
            _append_event(out_dir, {"observed_at": report["generated_at"], **item})
            seen.append(digest)
            seen_set.add(digest)
    atomic_json(out_dir / "latest.json", report)
    atomic_json(state_file, {"seen": seen[-350:], "offsets": offsets})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    run_mode = parser.add_mutually_exclusive_group()
    run_mode.add_argument("--once", action="store_true", help="Un relevé, puis arrêt (défaut).")
    run_mode.add_argument("--watch", action="store_true", help="Observateur continu, sans lancement de service.")
    parser.add_argument("--interval", type=int, default=15, help="Secondes entre relevés (minimum 5).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--studio-root", type=Path, default=DEFAULT_STUDIO)
    parser.add_argument("--comfy-root", type=Path, default=DEFAULT_COMFY)
    parser.add_argument("--capture-thumbnail", action="store_true", help="Crée une vignette locale si ffmpeg/Pillow est déjà installé.")
    args = parser.parse_args()
    while True:
        try:
            report = poll_once(args.output, args.studio_root, args.comfy_root, args.capture_thumbnail)
            if not args.watch:
                print(json.dumps({"studio": report["studio"], "comfy": report["comfy"],
                                  "latest": str(args.output / "latest.json")}, ensure_ascii=False))
        except Exception as exc:
            # Startup is fail-safe: one faulty source must not stop BAZOR's other tasks.
            try:
                args.output.mkdir(parents=True, exist_ok=True)
                _append_event(args.output, {"observed_at": now(), "kind": "observer_error",
                                            "error": clean(type(exc).__name__ + ": " + str(exc), 400)})
            except OSError:
                pass
            if not args.watch:
                print("Studio observer: " + clean(exc, 200), file=sys.stderr)
                return 2
        if not args.watch:
            return 0
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
