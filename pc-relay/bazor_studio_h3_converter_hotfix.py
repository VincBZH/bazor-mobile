import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path(r"C:\AI\SimpleStudioV2\app\workflows.py")
DATA = ROOT / "pc-relay" / "BAZOR_DATA" / "STUDIO_H3_CONVERTER_HOTFIX"
BACKUPS = DATA / "backups"
REPORTS = DATA / "reports"
BACKUPS.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

OLD = '''def _api_graph(graph):
    """Unwrap the API prompt returned by ComfyUI workflow converters."""
    current = graph
    for key in ('prompt', 'graph', 'api_prompt'):
        if isinstance(current, dict) and isinstance(current.get(key), dict):
            nested = current[key]
            if any(isinstance(v, dict) and 'class_type' in v for v in nested.values()):
                current = nested
                break
    return current
'''

NEW = '''def _api_graph(graph):
    """Return a ComfyUI API prompt from API or UI-format workflow JSON.

    Imported MiniMax H3 workflows are often saved in ComfyUI's UI format
    (nodes + links + widgets_values), while /prompt expects an API graph keyed
    by node id with class_type and named inputs.
    """
    current = graph
    for key in ('prompt', 'graph', 'api_prompt'):
        if isinstance(current, dict) and isinstance(current.get(key), dict):
            nested = current[key]
            if any(isinstance(v, dict) and 'class_type' in v for v in nested.values()):
                current = nested
                break

    if isinstance(current, dict) and any(
            isinstance(v, dict) and 'class_type' in v for v in current.values()):
        return current

    if not (isinstance(current, dict) and isinstance(current.get('nodes'), list)):
        return current

    link_map = {}
    for link in current.get('links') or []:
        if isinstance(link, list) and len(link) >= 5:
            link_map[link[0]] = [str(link[1]), int(link[2])]

    scalar_types = {'INT', 'FLOAT', 'STRING', 'BOOLEAN', 'COMBO'}
    fallback_widget_fields = {
        'UNETLoader': ('unet_name', 'weight_dtype'),
        'CLIPLoader': ('clip_name', 'type', 'device'),
        'VAELoader': ('vae_name',),
        'LoadImage': ('image',),
    }
    api = {}
    for raw in current.get('nodes') or []:
        if not isinstance(raw, dict):
            continue
        node_id = raw.get('id')
        class_type = str(raw.get('type') or '').strip()
        if node_id is None or not class_type:
            continue

        values = list(raw.get('widgets_values') or [])
        value_index = 0
        inputs = {}
        ui_inputs = raw.get('inputs') or []

        for inp in ui_inputs:
            if not isinstance(inp, dict):
                continue
            name = str(inp.get('name') or '').strip()
            if not name:
                continue
            link_id = inp.get('link')
            if link_id is not None and link_id in link_map:
                inputs[name] = link_map[link_id]
                continue

            input_type = str(inp.get('type') or '').upper()
            widget_backed = bool(inp.get('widget')) or input_type in scalar_types
            if link_id is None and widget_backed and value_index < len(values):
                inputs[name] = values[value_index]
                value_index += 1

        if not inputs and class_type in fallback_widget_fields:
            for idx, name in enumerate(fallback_widget_fields[class_type]):
                if idx < len(values):
                    inputs[name] = values[idx]

        node = {'class_type': class_type, 'inputs': inputs}
        title = raw.get('title')
        if title:
            node['_meta'] = {'title': str(title)}
        api[str(node_id)] = node

    return api or current
'''

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def candidate_bytes(original):
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = original.decode("utf-8")
    normalized = text.replace("\r\n", "\n")

    # Already patched, irrespective of surrounding comments/whitespace.
    if "ComfyUI UI workflow format" in normalized and "fallback_widget_fields" in normalized:
        return original, False, "already_patched"

    # Replace the whole _api_graph function by structure, not by an exact text
    # blob. The live Studio can contain tiny comment/spacing changes between
    # versions, which must not make the deterministic hotfix fail.
    m = re.search(
        r"(?ms)^def _api_graph\(graph\):\n.*?(?=^def [A-Za-z_]\w*\(|\Z)",
        normalized,
    )
    if not m:
        raise RuntimeError("api_graph_function_not_found")

    candidate = normalized[:m.start()] + NEW.rstrip() + "\n\n" + normalized[m.end():]
    if candidate == normalized:
        return original, False, "no_change"
    if newline == "\r\n":
        candidate = candidate.replace("\n", "\r\n")
    return candidate.encode("utf-8"), True, "patched"

def load_module(path):
    spec = importlib.util.spec_from_file_location("bazor_workflows_candidate", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def unit_test(path):
    mod = load_module(path)
    ui = {
        "nodes": [
            {"id": 1, "type": "UNETLoader", "title": "MODELO H3 W4A8",
             "widgets_values": ["minimax_h3_fl2va_pruned_w4a8_mixed.safetensors", "default"],
             "inputs": [], "outputs": [{"name":"MODEL","type":"MODEL","links":[1]}]},
            {"id": 2, "type": "CLIPLoader", "title": "QWEN3-VL 4B INT8",
             "widgets_values": ["qwen3vl_4b_int8_convrot.safetensors", "krea2", "default"],
             "inputs": [], "outputs": [{"name":"CLIP","type":"CLIP","links":[2]}]},
            {"id": 4, "type": "VAELoader", "title": "VAE VIDEO INT8",
             "widgets_values": ["minimax_h3_video_vae_int8_convrot.safetensors"],
             "inputs": [], "outputs": [{"name":"VAE","type":"VAE","links":[4]}]},
            {"id": 8, "type": "MiniMaxH3ImageToVideo",
             "widgets_values": ["test prompt", 608, 352, 124],
             "inputs": [
                 {"name":"clip","type":"CLIP","link":3},
                 {"name":"vae","type":"VAE","link":4},
                 {"name":"prompt","type":"STRING","link":None,"widget":{"name":"prompt"}},
                 {"name":"width","type":"INT","link":None,"widget":{"name":"width"}},
                 {"name":"height","type":"INT","link":None,"widget":{"name":"height"}},
                 {"name":"length","type":"INT","link":None,"widget":{"name":"length"}},
                 {"name":"first_frame","type":"IMAGE","link":18},
                 {"name":"last_frame","type":"IMAGE","link":19},
             ]},
            {"id": 14, "type": "VAEDecode", "widgets_values": [],
             "inputs":[{"name":"samples","type":"LATENT","link":15},{"name":"vae","type":"VAE","link":5}]},
            {"id": 15, "type": "CreateVideo", "widgets_values": [24.0],
             "inputs":[
                 {"name":"images","type":"IMAGE","link":16},
                 {"name":"audio","type":"AUDIO","link":None},
                 {"name":"fps","type":"FLOAT","link":None,"widget":{"name":"fps"}},
             ]},
            {"id": 16, "type": "SaveVideo",
             "widgets_values": ["video/test", "auto", "auto"],
             "inputs":[
                 {"name":"video","type":"VIDEO","link":17},
                 {"name":"filename_prefix","type":"STRING","link":None,"widget":{"name":"filename_prefix"}},
                 {"name":"format","type":"COMBO","link":None,"widget":{"name":"format"}},
                 {"name":"codec","type":"COMBO","link":None,"widget":{"name":"codec"}},
             ]},
        ],
        "links": [
            [3, 2, 0, 8, 0, "CLIP"],
            [4, 4, 0, 8, 1, "VAE"],
            [5, 4, 0, 14, 1, "VAE"],
            [15, 13, 0, 14, 0, "LATENT"],
            [16, 14, 0, 15, 0, "IMAGE"],
            [17, 15, 0, 16, 0, "VIDEO"],
            [18, 17, 0, 8, 6, "IMAGE"],
            [19, 18, 0, 8, 7, "IMAGE"],
        ],
    }
    api = mod._api_graph(ui)
    assert api["1"]["inputs"]["unet_name"] == "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors"
    assert api["2"]["inputs"]["clip_name"] == "qwen3vl_4b_int8_convrot.safetensors"
    assert api["4"]["inputs"]["vae_name"] == "minimax_h3_video_vae_int8_convrot.safetensors"
    assert api["8"]["inputs"]["width"] == 608
    assert api["8"]["inputs"]["height"] == 352
    assert api["8"]["inputs"]["length"] == 124
    assert api["8"]["inputs"]["clip"] == ["2", 0]
    assert api["8"]["inputs"]["vae"] == ["4", 0]
    assert api["15"]["inputs"]["fps"] == 24.0
    assert "audio" not in api["15"]["inputs"]
    assert api["16"]["inputs"]["filename_prefix"] == "video/test"

    p = {"width":1280,"height":704,"frames":49,"steps":28,"seed":123,
         "prompt":"test", "negative":"", "style_presets":["realistic"],
         "mode":"t2v","artistic":False}
    patched = mod.patch_h3_graph(ui, p, image_name=None, prefix="BAZOR/test")
    graph = patched["graph"]
    assert graph["8"]["inputs"]["width"] == 1280
    assert graph["8"]["inputs"]["height"] == 704
    assert graph["8"]["inputs"]["length"] == 49
    return {
        "api_nodes": len(api),
        "dimension_nodes": patched.get("dimension_nodes"),
        "loader_values": {
            "unet": api["1"]["inputs"]["unet_name"],
            "clip": api["2"]["inputs"]["clip_name"],
            "vae": api["4"]["inputs"]["vae_name"],
        }
    }

def git_preflight(original, candidate):
    git = shutil.which("git")
    result = {"available": bool(git), "ok": True, "detail": ""}
    if not git:
        return result
    with tempfile.TemporaryDirectory(prefix="bazor_h3_git_") as td:
        root = Path(td)
        p = root / "workflows.py"
        p.write_bytes(original)
        def run(*args):
            return subprocess.run([git, "-C", str(root), *args], capture_output=True,
                                  text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
        if run("init","-q").returncode != 0:
            return {"available":True,"ok":False,"detail":"git_init_failed"}
        run("config","user.email","bazor-hotfix@local")
        run("config","user.name","BAZOR H3 Hotfix")
        run("config","core.whitespace","cr-at-eol")
        run("add","-A")
        run("commit","-q","--allow-empty","-m","baseline")
        p.write_bytes(candidate)
        run("add","-A")
        chk = run("diff","--cached","--check")
        result["ok"] = chk.returncode == 0
        result["detail"] = (chk.stderr or chk.stdout).strip()[:1000]
        stat = run("diff","--cached","--stat")
        result["stat"] = (stat.stdout or "").strip()[:1000]
    return result

def run():
    if not TARGET.exists():
        raise RuntimeError("target_missing:"+str(TARGET))
    original = TARGET.read_bytes()
    candidate, changed, state = candidate_bytes(original)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "target": str(TARGET), "state": state, "changed": changed,
        "before_sha256": sha256(original), "after_sha256": sha256(candidate),
    }

    with tempfile.TemporaryDirectory(prefix="bazor_h3_candidate_") as td:
        cand = Path(td) / "workflows.py"
        cand.write_bytes(candidate)
        compile(candidate.decode("utf-8"), str(cand), "exec")
        report["unit_test"] = unit_test(cand)
        report["git_preflight"] = git_preflight(original, candidate)
        if not report["git_preflight"]["ok"]:
            raise RuntimeError("git_preflight_failed:"+report["git_preflight"].get("detail",""))

    if changed:
        backup = BACKUPS / f"workflows_{stamp}.py"
        backup.write_bytes(original)
        report["backup"] = str(backup)
        try:
            TARGET.write_bytes(candidate)
            compile(TARGET.read_text(encoding="utf-8"), str(TARGET), "exec")
            report["target_unit_test"] = unit_test(TARGET)
        except Exception:
            TARGET.write_bytes(original)
            report["rolled_back"] = True
            raise
    else:
        report["target_unit_test"] = unit_test(TARGET)

    report["ok"] = True
    out = REPORTS / f"hotfix_{stamp}.json"
    latest = REPORTS / "latest.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    out.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")
    print(json.dumps({"ok":True,"changed":changed,"state":state,"report":str(out),
                      "unit_test":report["target_unit_test"]},ensure_ascii=False))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        err = {"ok":False,"error":type(exc).__name__,"detail":str(exc)}
        try:
            (REPORTS/"latest_error.json").write_text(json.dumps(err,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception:
            pass
        print(json.dumps(err,ensure_ascii=False))
        raise
