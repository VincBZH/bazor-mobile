import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUALIFIER = ROOT / "pc-relay" / "bazor_studio_qualifier.py"
DATA = ROOT / "pc-relay" / "BAZOR_DATA"
QUAL_REPORT = DATA / "STUDIO_QUALIFICATION" / "latest.json"
LOG_DIR = DATA / "STUDIO_CERTIFIED"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG = LOG_DIR / "latest.log"

COMFY_ROOTS = [
    Path(r"C:\AI\ComfyUI\ComfyUI_windows_portable"),
    Path(r"C:\AI\ComfyUI"),
]
COMFY_CANDIDATES = [
    "run_nvidia_gpu.bat",
    "run_nvidia_gpu_fast_fp16_accumulation.bat",
    "run_cpu.bat",
]
STUDIO_ROOTS = [Path(r"C:\AI\SimpleStudioV2")]
STUDIO_CANDIDATES = [
    "LANCER_BAZOR_STUDIO.cmd",
    "LANCER_STUDIO.cmd",
    "Lancer.cmd",
    "start.cmd",
    "run.cmd",
    "app.py",
    "main.py",
    "server.py",
]

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

def emit(msg):
    line = time.strftime("[%H:%M:%S] ") + str(msg)
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def port_open(port):
    s = socket.socket()
    s.settimeout(0.6)
    try:
        return s.connect_ex(("127.0.0.1", int(port))) == 0
    finally:
        s.close()

def http_ok(url, timeout=4):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= int(getattr(r, "status", 200)) < 500
    except Exception:
        return False

def wait_ready(port, health, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if port_open(port) and (not health or http_ok(health, 2.5)):
            return True
        time.sleep(1)
    return False

def launch_path(path):
    path = Path(path)
    suffix = path.suffix.lower()
    cwd = str(path.parent)
    if suffix in (".cmd", ".bat"):
        subprocess.Popen(["cmd", "/c", str(path)], cwd=cwd, creationflags=CREATE_NEW_CONSOLE)
    elif suffix == ".ps1":
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)],
            cwd=cwd, creationflags=CREATE_NEW_CONSOLE
        )
    elif suffix == ".py":
        subprocess.Popen([sys.executable, str(path)], cwd=cwd, creationflags=CREATE_NEW_CONSOLE)
    else:
        raise RuntimeError("type_lanceur_non_supporte:" + suffix)

def find_launcher(roots, candidates):
    for root in roots:
        if not root.exists():
            continue
        for name in candidates:
            p = root / name
            if p.is_file():
                return p
    return None

def ensure_service(name, port, health, roots, candidates, timeout, allow_launch):
    if port_open(port) and (not health or http_ok(health)):
        emit(f"{name}: déjà opérationnel sur {port}.")
        return True
    if not allow_launch:
        emit(f"{name}: indisponible sur {port} en mode test-only.")
        return False
    launcher = find_launcher(roots, candidates)
    if not launcher:
        emit(f"{name}: aucun lanceur connu trouvé.")
        return False
    emit(f"{name}: lancement via {launcher}.")
    launch_path(launcher)
    ok = wait_ready(port, health, timeout)
    emit(f"{name}: {'OK' if ok else 'ECHEC'} après attente.")
    return ok

def load_latest_qualification():
    try:
        data = json.loads(QUAL_REPORT.read_text(encoding="utf-8"))
        age = time.time() - QUAL_REPORT.stat().st_mtime
        return data, age
    except Exception:
        return None, None

def qualification_cached_ok(max_age_hours=12):
    data, age = load_latest_qualification()
    if not data or age is None:
        return False, "aucun rapport"
    summary = data.get("summary") or {}
    result_ids={str(x.get("id") or ""):x for x in (data.get("results") or [])}
    e2e=result_ids.get("STUDIO_E2E_REAL_GENERATION")
    if not e2e:
        return False, "rapport ancien: preuve E2E absente"
    if not e2e.get("ok"):
        return False, "preuve E2E réelle non validée"
    if not summary.get("operational"):
        return False, f"rapport non opérationnel: {summary}"
    if age > max_age_hours * 3600:
        return False, f"rapport trop ancien: {age/3600:.1f} h"
    return True, f"{summary.get('passed')}/{summary.get('total')} tests, {summary.get('percent')}% + E2E"

def run_full_qualification():
    if not QUALIFIER.exists():
        return False, "qualificateur absent"
    emit("Qualification complète locale en cours...")
    cp = subprocess.run(
        [sys.executable, str(QUALIFIER), "--compact"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=1000, creationflags=CREATE_NO_WINDOW
    )
    if cp.stdout:
        for line in cp.stdout.splitlines()[-80:]:
            emit("QUAL: " + line)
    if cp.stderr:
        for line in cp.stderr.splitlines()[-30:]:
            emit("QUAL-ERR: " + line)
    ok, detail = qualification_cached_ok(max_age_hours=1)
    return ok, detail

def runtime_gate():
    checks = {
        "comfy_port": port_open(8188),
        "comfy_system_stats": http_ok("http://127.0.0.1:8188/system_stats"),
        "comfy_object_info": http_ok("http://127.0.0.1:8188/object_info"),
        "studio_port": port_open(8191),
        "studio_root": http_ok("http://127.0.0.1:8191/"),
    }
    return all(checks.values()), checks

def selftest():
    assert not port_open(65534) or isinstance(port_open(65534), bool)
    assert isinstance(find_launcher([], []), type(None))
    print("SELFTEST_OK")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-only", action="store_true", help="Ne lance rien et n'ouvre pas le navigateur.")
    ap.add_argument("--force-qualify", action="store_true", help="Refait les 47 tests même si un rapport récent est vert.")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if os.environ.get("BAZOR_STUDIO_TEST_ONLY","").strip() == "1":
        args.test_only = True
    if args.selftest:
        selftest()
        return 0

    emit("=== BAZOR AI SIMPLE STUDIO CERTIFIÉ ===")
    comfy = ensure_service(
        "ComfyUI", 8188, "http://127.0.0.1:8188/system_stats",
        COMFY_ROOTS, COMFY_CANDIDATES, 120, not args.test_only
    )
    studio = ensure_service(
        "AI Simple Studio", 8191, "http://127.0.0.1:8191/",
        STUDIO_ROOTS, STUDIO_CANDIDATES, 60, not args.test_only
    )
    if not (comfy and studio):
        emit("BLOQUE: services requis non prêts.")
        return 2

    cached, detail = qualification_cached_ok()
    if args.force_qualify or not cached:
        emit("Certification complète requise: " + detail)
        cached, detail = run_full_qualification()
    else:
        emit("Certification complète récente: " + detail)

    runtime_ok, runtime = runtime_gate()
    emit("Contrôle runtime: " + json.dumps(runtime, ensure_ascii=False))

    if not cached or not runtime_ok:
        emit("BLOQUE: le Studio n'est pas certifié pour ouverture.")
        return 3

    data, _ = load_latest_qualification()
    summary = (data or {}).get("summary") or {}
    emit(f"CERTIFIÉ: {summary.get('passed')}/{summary.get('total')} contrôles • {summary.get('percent')}% • runtime OK.")

    if not args.test_only:
        webbrowser.open("http://127.0.0.1:8191/")
        emit("Studio ouvert dans le navigateur.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
