import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

ROOT_CANDIDATES = [
    Path(r"C:\AI\ComfyUI\ComfyUI_windows_portable\ComfyUI"),
    Path(r"C:\AI\ComfyUI"),
]
STUDIO_ROOT = Path(r"C:\AI\SimpleStudioV2")

REPLACEMENTS = {
    "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors": "qwen3vl_4b_int8_convrot.safetensors",
    "minimax_h3_video_vae_fp16.safetensors": "minimax_h3_video_vae_int8_convrot.safetensors",
    "minimax_h3_fl2va_pruned_int8_convrot.safetensors": "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
}

DOWNLOADS = [
    {
        "name": "minimax_h3_audio_vae_fp32.safetensors",
        "url": "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors",
        "subdir": "vae",
        "min_bytes": 500_000_000,
    },
    {
        "name": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
        "url": "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
        "subdir": "loras",
        "min_bytes": 1_500_000_000,
    },
]

REQUIRED_EXISTING = [
    ("diffusion_models", "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors"),
    ("text_encoders", "qwen3vl_4b_int8_convrot.safetensors"),
    ("vae", "minimax_h3_video_vae_int8_convrot.safetensors"),
]

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"[{now()}] {msg}", flush=True)

def find_comfy_root():
    for p in ROOT_CANDIDATES:
        if (p / "models").is_dir():
            return p
    raise RuntimeError("ComfyUI root introuvable")

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def download(url, dest, min_bytes):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size >= min_bytes:
        log(f"OK déjà présent: {dest.name} ({dest.stat().st_size/1024/1024:.0f} Mo)")
        return {"status":"present","bytes":dest.stat().st_size}
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    log(f"Téléchargement officiel: {dest.name}")
    req = urllib.request.Request(url, headers={"User-Agent":"BAZOR-H3-Repair/1.0"})
    with urllib.request.urlopen(req, timeout=45) as r, tmp.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        last_pct = -1
        while True:
            chunk = r.read(8 * 1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total:
                pct = int(got * 100 / total)
                if pct >= last_pct + 5:
                    log(f"  {dest.name}: {pct}%")
                    last_pct = pct
    if tmp.stat().st_size < min_bytes:
        raise RuntimeError(f"téléchargement incomplet: {dest.name}")
    tmp.replace(dest)
    log(f"OK téléchargé: {dest.name} ({dest.stat().st_size/1024/1024:.0f} Mo)")
    return {"status":"downloaded","bytes":dest.stat().st_size}

def workflow_candidates(comfy):
    roots = [
        comfy / "user" / "default" / "workflows",
        STUDIO_ROOT,
    ]
    found = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for p in root.rglob("*.json"):
                if p.is_file() and p.stat().st_size < 10 * 1024 * 1024:
                    found.append(p)
        except Exception:
            pass
    return found

def patch_workflow(path, backup_root):
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="utf-8-sig")
    if not any(k in raw for k in REPLACEMENTS):
        return None
    new = raw
    changes = []
    for old, repl in REPLACEMENTS.items():
        count = new.count(old)
        if count:
            new = new.replace(old, repl)
            changes.append({"from":old,"to":repl,"count":count})
    if new == raw:
        return None
    # Validate JSON before touching original.
    json.loads(new)
    relsafe = str(path).replace(":","").replace("\\","_").replace("/","_")
    backup = backup_root / (relsafe + ".bak")
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    path.write_text(new, encoding="utf-8")
    log(f"PATCH OK: {path}")
    return {"path":str(path),"backup":str(backup),"changes":changes}

def main():
    comfy = find_comfy_root()
    data_dir = Path.home() / "bazor-mobile" / "pc-relay" / "BAZOR_DATA"
    log_dir = data_dir / "H3_REPAIR"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_root = log_dir / ("backup_" + stamp)
    report_path = log_dir / ("report_" + stamp + ".json")

    report = {
        "ok": False,
        "comfy_root": str(comfy),
        "required_existing": [],
        "downloads": [],
        "patched": [],
        "time": now(),
    }

    log(f"ComfyUI: {comfy}")
    missing_existing = []
    for subdir, name in REQUIRED_EXISTING:
        p = comfy / "models" / subdir / name
        ok = p.is_file() and p.stat().st_size > 10_000_000
        report["required_existing"].append({"file":str(p),"ok":ok,"bytes":p.stat().st_size if p.exists() else 0})
        if not ok:
            missing_existing.append(str(p))
    if missing_existing:
        raise RuntimeError("Modèles 8GB déjà attendus mais absents: " + " ; ".join(missing_existing))

    for item in DOWNLOADS:
        dest = comfy / "models" / item["subdir"] / item["name"]
        result = download(item["url"], dest, item["min_bytes"])
        report["downloads"].append({
            "file":str(dest),
            **result,
            "sha256":sha256(dest),
        })

    patched = []
    for p in workflow_candidates(comfy):
        try:
            item = patch_workflow(p, backup_root)
            if item:
                patched.append(item)
        except Exception as exc:
            log(f"SKIP {p.name}: {type(exc).__name__}: {exc}")
    report["patched"] = patched

    # Explicitly verify that required official validation inputs now exist.
    checks = [
        comfy / "models" / "diffusion_models" / "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
        comfy / "models" / "text_encoders" / "qwen3vl_4b_int8_convrot.safetensors",
        comfy / "models" / "vae" / "minimax_h3_video_vae_int8_convrot.safetensors",
        comfy / "models" / "vae" / "minimax_h3_audio_vae_fp32.safetensors",
        comfy / "models" / "loras" / "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
    ]
    report["final_checks"] = [{"file":str(p),"ok":p.is_file(),"bytes":p.stat().st_size if p.exists() else 0} for p in checks]
    report["ok"] = all(x["ok"] for x in report["final_checks"])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log("RAPPORT: " + str(report_path))
    if report["ok"]:
        log("H3 REPAIR OK - redémarrer ComfyUI pour recharger la liste des modèles.")
        return 0
    log("H3 REPAIR INCOMPLET")
    return 2

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"BLOQUE: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
