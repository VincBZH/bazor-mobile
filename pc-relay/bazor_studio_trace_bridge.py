import json
import subprocess
import time
import urllib.request
import os
import re
import hashlib

REPO = "VincBZH/bazor-mobile"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "pc-relay", "BAZOR_DATA")
STATE_FILE = os.path.join(DATA_DIR, "studio_trace_state.json")
LATEST_FILE = os.path.join(DATA_DIR, "studio_trace_latest.json")
MARK = "[BAZOR-STUDIO-TRACE]"
MIN_INTERVAL = 30


def gh(args):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    p = subprocess.run(
        ["gh"] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip())
    return p.stdout


def _redact(value):
    s = str(value or "")
    home = os.path.expanduser("~")
    if home:
        s = s.replace(home, "<USER>")
        s = s.replace(home.replace("\\", "/"), "<USER>")
    rules = (
        (r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1<redacted>"),
        (r"(?i)\b(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})\b", "<redacted-token>"),
        (r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[\"']?[^,\s\"']+", r"\1=<redacted>"),
    )
    for pat, repl in rules:
        try:
            s = re.sub(pat, repl, s)
        except Exception:
            pass
    return s


def _read_json(path):
    try:
        data = json.load(open(path, "r", encoding="utf-8-sig", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _tail(path, max_lines=45, max_chars=6500):
    try:
        lines = open(path, "r", encoding="utf-8", errors="replace").read().splitlines()
        return _redact("\n".join(lines[-max_lines:]))[-max_chars:]
    except Exception as exc:
        return "<unavailable:" + type(exc).__name__ + ">"


def _scan_file(path, max_hits=36):
    if not os.path.exists(path):
        return {"exists": False, "path": path}
    try:
        raw = open(path, "rb").read()
        text_src = raw.decode("utf-8", "replace")
        rx = re.compile(
            r"localStorage|sessionStorage|indexedDB|source[_A-Za-z]*|reference|history|gallery|"
            r"preview|current[_A-Za-z]*job|job[_-]?id|prompt[_-]?id|effective[_-]?mode|"
            r"requested[_-]?mode|image[_-]?name|input[_-]?image|fetch\s*\(|/api/",
            re.I,
        )
        hits = []
        for no, line in enumerate(text_src.splitlines(), 1):
            if rx.search(line):
                hits.append({"line": no, "text": _redact(line.strip())[:650]})
                if len(hits) >= max_hits:
                    break
        return {
            "exists": True,
            "path": path,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "hits": hits,
        }
    except Exception as exc:
        return {"exists": True, "path": path, "error": type(exc).__name__ + ":" + str(exc)[:180]}


def _http_probe(url, timeout=2.2):
    started = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(65536)
            status = getattr(r, "status", 200)
            ctype = str(r.headers.get("Content-Type") or "")
        out = {
            "ok": 200 <= status < 400,
            "http": status,
            "ms": int((time.monotonic() - started) * 1000),
            "content_type": ctype,
            "sample_bytes": len(raw),
        }
        if "json" in ctype.lower():
            try:
                body = json.loads(raw.decode("utf-8", "replace"))
                if isinstance(body, dict):
                    out["json_keys"] = list(body.keys())[:30]
            except Exception:
                pass
        return out
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "detail": _redact(str(exc))[:220],
            "ms": int((time.monotonic() - started) * 1000),
        }


def _ports():
    if os.name != "nt":
        return []
    ps = r"""
$ports=8188,8191
$out=@()
foreach($port in $ports){
  $cs=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  foreach($c in $cs){
    $p=Get-CimInstance Win32_Process -Filter ("ProcessId="+$c.OwningProcess) -ErrorAction SilentlyContinue
    $out += [pscustomobject]@{
      port=$port; pid=$c.OwningProcess;
      name=if($p){$p.Name}else{""};
      command=if($p){$p.CommandLine}else{""}
    }
  }
}
$out | ConvertTo-Json -Compress
"""
    try:
        cp = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        raw = (cp.stdout or "").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        for row in data:
            row["command"] = _redact(row.get("command"))[:700]
        return data[:12]
    except Exception as exc:
        return [{"error": type(exc).__name__ + ":" + str(exc)[:180]}]


def _comfy_history():
    snap = {
        "queue": _http_probe("http://127.0.0.1:8188/queue"),
        "history_http": _http_probe("http://127.0.0.1:8188/history?max_items=5"),
    }
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/history?max_items=5", timeout=3.5) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        items = []
        if isinstance(data, dict):
            for prompt_id, entry in list(data.items())[-5:]:
                entry = entry or {}
                graph = {}
                pr = entry.get("prompt")
                if isinstance(pr, list) and len(pr) >= 3 and isinstance(pr[2], dict):
                    graph = pr[2]
                elif isinstance(pr, dict):
                    graph = pr

                nodes = []
                for node_id, node in (graph or {}).items():
                    if not isinstance(node, dict):
                        continue
                    cls = str(node.get("class_type") or "")
                    inp = node.get("inputs") or {}
                    keep = {}
                    for k, v in inp.items():
                        lk = str(k).lower()
                        if (
                            lk in (
                                "text", "image", "image_name", "filename_prefix", "ckpt_name",
                                "unet_name", "clip_name", "vae_name", "width", "height",
                                "length", "batch_size", "denoise", "seed"
                            )
                            or "source" in lk
                        ):
                            vv = _redact(v)
                            keep[str(k)] = vv[:850] if isinstance(vv, str) else vv
                    if keep or cls in (
                        "CLIPTextEncode", "LoadImage", "SaveImage", "SaveVideo",
                        "CheckpointLoaderSimple", "Wan22ImageToVideoLatent"
                    ):
                        nodes.append({"id": str(node_id), "class": cls, "inputs": keep})

                outputs = []
                for node_id, out in (entry.get("outputs") or {}).items():
                    if not isinstance(out, dict):
                        continue
                    for key in ("images", "gifs", "videos"):
                        vals = out.get(key) or []
                        if isinstance(vals, list):
                            for x in vals[:5]:
                                if isinstance(x, dict):
                                    outputs.append({
                                        "node": str(node_id),
                                        "kind": key,
                                        "filename": _redact(x.get("filename"))[:500],
                                        "subfolder": _redact(x.get("subfolder"))[:300],
                                        "type": x.get("type"),
                                    })

                status = entry.get("status") or {}
                items.append({
                    "prompt_id": str(prompt_id),
                    "status": status.get("status_str") if isinstance(status, dict) else None,
                    "nodes": nodes[:24],
                    "outputs": outputs[:12],
                })
        snap["recent"] = items
    except Exception as exc:
        snap["history_error"] = type(exc).__name__ + ":" + _redact(str(exc))[:240]
    return snap


def _logs(studio_root):
    log_dir = os.path.join(studio_root, "logs")
    out = []
    try:
        names = []
        if os.path.isdir(log_dir):
            for name in os.listdir(log_dir):
                p = os.path.join(log_dir, name)
                if os.path.isfile(p) and name.lower().endswith((".log", ".txt", ".jsonl")):
                    try:
                        names.append((os.path.getmtime(p), p))
                    except Exception:
                        pass
        for mt, p in sorted(names, reverse=True)[:6]:
            out.append({
                "name": os.path.basename(p),
                "mtime": int(mt),
                "size": os.path.getsize(p),
                "tail": _tail(p, 35, 4500),
            })
    except Exception as exc:
        out.append({"error": type(exc).__name__ + ":" + str(exc)[:180]})
    return out


def _task_diag():
    path = os.path.join(DATA_DIR, "journal.jsonl")
    try:
        lines = open(path, "r", encoding="utf-8", errors="replace").read().splitlines()[-800:]
    except Exception:
        return {}
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
            if row.get("event") in (
                "MOBILE_TASK_JOB_START", "MOBILE_TASK_CONTEXT",
                "MOBILE_TASK_JOB_DONE", "MOBILE_SUBTASK", "SECURITY_ALERT"
            ):
                rows.append(row)
        except Exception:
            pass
    return rows[-12:]


def build_report(issue_number, task_id, phase):
    studio = r"C:\AI\SimpleStudioV2"
    app = os.path.join(studio, "app")
    files = {}
    for rel in ("static/app.js", "studio.py", "workflows.py"):
        files[rel] = _scan_file(os.path.join(app, *rel.split("/")))

    probes = {}
    for path in ("/", "/health", "/api/status", "/api/history", "/api/jobs", "/api/gallery"):
        probes[path] = _http_probe("http://127.0.0.1:8191" + path)

    try:
        head = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        ).stdout.strip()
    except Exception:
        head = "unknown"

    report = {
        "trace_version": 1,
        "issue": int(issue_number),
        "task_id": str(task_id),
        "phase": str(phase),
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "watcher_head": head,
        "ports": _ports(),
        "studio_probes": probes,
        "comfy": _comfy_history(),
        "files": files,
        "logs": _logs(studio),
        "task_diag": _task_diag(),
    }
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LATEST_FILE, "w", encoding="utf-8") as h:
            json.dump(report, h, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return report


def _markdown(report):
    lines = [
        MARK,
        "",
        "**Studio trace auto - " + str(report.get("phase")) + "**",
        "",
        "- task: " + str(report.get("task_id")),
        "- time: " + str(report.get("time")),
        "- watcher: " + str(report.get("watcher_head") or "")[:12],
        "- ports: " + json.dumps(report.get("ports") or [], ensure_ascii=False, separators=(",", ":"))[:1800],
        "- Studio probes: " + json.dumps(report.get("studio_probes") or {}, ensure_ascii=False, separators=(",", ":"))[:2200],
        "",
        "**ComfyUI - jobs recents / prompt reel recu**",
        "~~~json",
        json.dumps(((report.get("comfy") or {}).get("recent") or []), ensure_ascii=False, indent=2)[:5200],
        "~~~",
        "",
        "**Points de controle code**",
    ]
    for rel, info in (report.get("files") or {}).items():
        lines.append("- " + rel + " sha=" + str(info.get("sha256") or "missing")[:12] + " size=" + str(info.get("size") or 0))
        for hit in (info.get("hits") or [])[:12]:
            lines.append("  - L" + str(hit.get("line")) + ": " + str(hit.get("text") or "")[:420])

    lines += ["", "**Logs Studio recents**"]
    for row in (report.get("logs") or [])[:4]:
        lines.append("- " + str(row.get("name") or "?") + " size=" + str(row.get("size") or 0))
        tail = str(row.get("tail") or "")
        if tail:
            lines += ["~~~text", tail[-1600:], "~~~"]

    lines += [
        "",
        "**Task diag recent**",
        "~~~json",
        json.dumps(report.get("task_diag") or [], ensure_ascii=False, indent=2)[:2600],
        "~~~",
        "",
        "Collecte bornee et expurgee: pas de cookie, pas de cle API, pas de token volontairement publie.",
    ]
    return "\n".join(lines)[:11800]


def collect_and_post(issue_number, task_id, phase="poll", force=False):
    if str(task_id or "").upper() != "STUDIO-P0-012":
        return False
    try:
        report = build_report(issue_number, task_id, phase)
        stable = {
            "ports": report.get("ports"),
            "studio_probes": report.get("studio_probes"),
            "comfy_recent": ((report.get("comfy") or {}).get("recent") or []),
            "file_sha": {k: (v or {}).get("sha256") for k, v in (report.get("files") or {}).items()},
            "log_sig": [(x.get("name"), x.get("mtime"), x.get("size")) for x in (report.get("logs") or [])],
            "task_diag": report.get("task_diag"),
        }
        digest = hashlib.sha256(
            json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        state = _read_json(STATE_FILE)
        key = "issue#" + str(issue_number) + ":" + str(task_id).upper()
        old = state.get(key) or {}
        now = int(time.time())

        if not force and old.get("digest") == digest:
            return False
        if not force and now - int(old.get("posted_at") or 0) < MIN_INTERVAL:
            return False

        gh(["issue", "comment", str(issue_number), "--repo", REPO, "--body", _markdown(report)])
        state[key] = {"digest": digest, "posted_at": now, "phase": phase}
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as h:
            json.dump(state, h, ensure_ascii=False, indent=2)
        print("[STUDIO TRACE] #" + str(issue_number) + " " + str(task_id) + " phase=" + str(phase) + " posted")
        return True
    except Exception as exc:
        print("[STUDIO TRACE WARN]", type(exc).__name__, str(exc)[:300])
        return False
