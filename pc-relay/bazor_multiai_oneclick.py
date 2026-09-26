"""BAZOR one-click isolated certification. Standard library, no pip, no destructive repair.

One click starts only missing isolated BAZOR Core/Room services (8875/8768),
reuses Ollama, tests a real local message and optionally one bounded Mammouth
bridge call with a public arithmetic prompt. It NEVER installs/overwrites
existing services, models, credentials or local Git branches.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PC = ROOT / "pc-relay"
ROOM = ROOT / "room-payload" / "v2.4" / "app" / "room_v2_server.py"
WORK = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "BAZOR_ONECLICK"
CORE_PORT = 8875
ROOM_PORT = 8768
CORE_FILES = ("bazor_pc_relay_v3.py", "bazor_action_engine.py",
              "bazor_security.py", "mammouth_client.py", "bazor_bridge.py")
PREFERRED = ("llama3.2:3b", "qwen2.5-coder:7b", "mistral:latest")
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def local_json(url, payload=None, timeout=5):
    """Strictly local HTTP; proxies disabled and bounded JSON responses."""
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("local_http_only")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET",
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError("response_too_large")
        obj = json.loads(raw.decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("response_not_object")
        return obj


def probe(url, timeout=2):
    try:
        return local_json(url, timeout=timeout)
    except (OSError, ValueError, urllib.error.URLError, TimeoutError):
        return None


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def signature():
    h = hashlib.sha256()
    for name in CORE_FILES:
        p = PC / name
        h.update(name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()


def valid_core(health, sig):
    return (isinstance(health, dict) and health.get("ok") is True
            and health.get("service") == "BAZOR API"
            and health.get("runtime_signature") == sig
            and isinstance(health.get("pid"), int)
            and bool(health.get("core_path"))
            and "mammouth_ollama" in (health.get("capabilities") or []))


def choose_model(models):
    found = [str(x.get("name")) for x in models if isinstance(x, dict) and x.get("name")]
    return next((m for m in PREFERRED if m in found), None) or next(
        (m for m in found if "32b" not in m.lower() and "70b" not in m.lower()), None)


def valid_room_reply(reply):
    if not isinstance(reply, dict) or reply.get("ok") is not True:
        return False
    rows = reply.get("results")
    if not isinstance(rows, list) or len(rows) != 1:
        return False
    row = rows[0]
    return (isinstance(row, dict) and row.get("provider") == "ollama"
            and row.get("ok") is True and isinstance(row.get("model"), str)
            and bool(row["model"]) and isinstance(row.get("text"), str)
            and "BAZOR_LOCAL_OK" in row["text"])


def env_with_user_key():
    env = os.environ.copy()
    if not env.get("MAMMOUTH_API_KEY") and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                raw, _ = winreg.QueryValueEx(key, "MAMMOUTH_API_KEY")
                if isinstance(raw, str) and raw.strip():
                    env["MAMMOUTH_API_KEY"] = raw.strip()
        except (OSError, ImportError):
            pass
    return env


def spawn(name, cmd, env, cwd=ROOT):
    WORK.mkdir(parents=True, exist_ok=True)
    logfile = WORK / (name + ".log")
    with logfile.open("ab") as log:
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT,
                                creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP)
    return proc.pid


def wait_for(url, check, seconds=18):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        result = probe(url, 1.5)
        if check(result):
            return result
        time.sleep(0.5)
    return None


def save_report(report):
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / ("rapport_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nRapport local : " + str(path))
    return path


def selftest():
    import unittest
    class SafeChecks(unittest.TestCase):
        def test_genuine_core(self):
            d = {"ok": True, "service": "BAZOR API", "runtime_signature": "X",
                 "pid": 123, "core_path": "core.py", "capabilities": ["mammouth_ollama"]}
            self.assertTrue(valid_core(d, "X"))
            self.assertFalse(valid_core({**d, "ok": False}, "X"))
            self.assertFalse(valid_core({**d, "runtime_signature": "Y"}, "X"))
            self.assertFalse(valid_core({**d, "capabilities": []}, "X"))
        def test_small_model_preferred(self):
            self.assertEqual(choose_model([{"name": "qwen2.5-coder:32b"},
                                           {"name": "qwen2.5-coder:7b"}]), "qwen2.5-coder:7b")
            self.assertIsNone(choose_model([{"name": "qwen2.5-coder:32b"}]))
        def test_no_fake_room_green(self):
            row = {"provider": "ollama", "ok": True, "model": "llama3.2:3b",
                   "text": "BAZOR_LOCAL_OK"}
            self.assertTrue(valid_room_reply({"ok": True, "results": [row]}))
            self.assertFalse(valid_room_reply({"ok": True, "results": [{**row, "ok": False}]}))
            self.assertFalse(valid_room_reply({"ok": True, "results": [{**row, "text": ""}]}))
            self.assertFalse(valid_room_reply({"ok": True, "results": []}))
        def test_reject_external_url(self):
            with self.assertRaises(ValueError):
                local_json("https://api.example.com/private")
            with self.assertRaises(ValueError):
                local_json("http://localhost:8775/")
            with self.assertRaises(ValueError):
                local_json("http://127.0.0.1:8775/#fragment")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SafeChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def run(test_mammouth=False):
    report = {"tool": "BAZOR_ONECLICK", "date": dt.datetime.now().astimezone().isoformat(),
              "mode": "isolated_not_installation", "statuses": {},
              "evidence": {}, "limitations": ["GPT/Astra require authorized connector or manual handoff",
                 "NoTrack/Tor are not certified and will not receive credentials"]}
    status = report["statuses"]
    env = env_with_user_key()
    env.setdefault("BAZOR_MAMMOUTH_BUDGET_USD", "4")
    try:
        import py_compile
        with tempfile.TemporaryDirectory(prefix="bazor_preflight_") as td:
            for i, name in enumerate(CORE_FILES):
                py_compile.compile(str(PC / name), cfile=str(Path(td) / (str(i) + ".pyc")), doraise=True)
            py_compile.compile(str(ROOM), cfile=str(Path(td) / "room.pyc"), doraise=True)
        sig = signature()
        status["code"] = "PASS"
    except Exception as exc:
        status["code"] = "BLOCKED:" + type(exc).__name__
        save_report(report)
        return 2

    tags = probe("http://127.0.0.1:11434/api/tags")
    if not isinstance(tags, dict) or not isinstance(tags.get("models"), list):
        if not listening(11434) and shutil.which("ollama"):
            spawn("ollama", ["ollama", "serve"], env)
            tags = wait_for("http://127.0.0.1:11434/api/tags",
                            lambda x: isinstance(x, dict) and isinstance(x.get("models"), list))
    model = choose_model((tags or {}).get("models") or [])
    if not model:
        status["ollama"] = "BLOCKED:no_available_small_model_or_offline"
        print("Ollama bloque : ouvrir Ollama et installer un modele leger si necessaire.")
        save_report(report)
        return 2
    status["ollama"] = "READY:" + model

    # Never stop or replace an active Core. Use a dedicated loopback-only Core
    # if the existing one has an older version or cannot prove its identity.
    live = probe("http://127.0.0.1:8775/api/v1/health")
    if valid_core(live, sig):
        core_port = 8775
        status["core"] = "REUSED_VERIFIED"
    else:
        core_port = CORE_PORT
        other = probe(f"http://127.0.0.1:{CORE_PORT}/api/v1/health")
        if other and not valid_core(other, sig) or (not other and listening(CORE_PORT)):
            status["core"] = "BLOCKED:isolated_port_occupied"
            save_report(report)
            return 2
        if not other:
            private = WORK / "PRIVATE_CORE_DATA"
            private.mkdir(parents=True, exist_ok=True)
            childenv = env.copy()
            childenv.update(BAZOR_MOBILE_PORT=str(CORE_PORT), BAZOR_CORE_BIND_HOST="127.0.0.1",
                            BAZOR_DISABLE_UDP="1", BAZOR_DATA_DIR=str(private))
            spawn("isolated_core", [sys.executable, str(PC / "bazor_pc_relay_v3.py")], childenv)
            other = wait_for(f"http://127.0.0.1:{CORE_PORT}/api/v1/health",
                             lambda x: valid_core(x, sig))
        if not valid_core(other, sig):
            status["core"] = "BLOCKED:isolated_start_failed_check_log"
            save_report(report)
            return 2
        status["core"] = "ISOLATED_VERIFIED"

    core_url = f"http://127.0.0.1:{core_port}"
    report["evidence"]["core_signature"] = sig
    roomurl = f"http://127.0.0.1:{ROOM_PORT}"
    room = probe(roomurl + "/api/status")
    if room and room.get("version") != "2.4-core-relay" or (not room and listening(ROOM_PORT)):
        status["room"] = "BLOCKED:isolated_port_occupied"
        save_report(report)
        return 2
    if not room:
        room_env = env.copy()
        room_env.update(BAZOR_ROOM_HOST="127.0.0.1", BAZOR_ROOM_PORT=str(ROOM_PORT),
                        BAZOR_CORE_URL=core_url)
        spawn("isolated_room", [sys.executable, str(ROOM)], room_env)
        room = wait_for(roomurl + "/api/status",
                        lambda x: isinstance(x, dict) and x.get("version") == "2.4-core-relay")
    if room:
        verified = (room.get("engines") or {}).get("core") or {}
        if (verified.get("runtime_signature") != sig or verified.get("port") != core_port):
            status["room"] = "BLOCKED:room_connected_to_wrong_core"
            save_report(report)
            return 2
    if not room:
        status["room"] = "BLOCKED:isolated_start_failed_check_log"
        save_report(report)
        return 2

    # Verify the same Core identity from the Room via its real proxy path.
    try:
        answer = local_json(roomurl + "/api/chat", {"target": "ollama",
            "text": "Reponds uniquement par le texte BAZOR_LOCAL_OK."}, timeout=210)
    except Exception as exc:
        status["room_core_ollama"] = "BLOCKED:" + type(exc).__name__
        save_report(report)
        return 2
    if not valid_room_reply(answer):
        status["room_core_ollama"] = "BLOCKED:missing_real_model_answer"
        save_report(report)
        return 2
    status["room_core_ollama"] = "PASS_REAL_LOCAL"
    report["evidence"]["ollama_model"] = answer["results"][0]["model"]
    report["evidence"]["room_url"] = roomurl
    print("PASS local : Room -> Core -> Ollama. Interface : " + roomurl)
    status["gpt"] = "PENDING:GitHub_watcher_roundtrip_#168"
    status["astra"] = "PENDING:authorized_connector"
    status["notrack"] = "NOT_CONFIGURED"
    status["tor"] = "OPTIONAL_DISABLED"

    if test_mammouth:
        h = probe(core_url + "/api/v1/health") or {}
        budget = (h.get("mammouth") or {}).get("budget") or {}
        if not env.get("MAMMOUTH_API_KEY"):
            status["mammouth"] = "BLOCKED:key_missing"
        elif not (h.get("mammouth") or {}).get("configured"):
            status["mammouth"] = "BLOCKED:key_not_loaded_in_core"
        elif budget.get("blocked") or float(budget.get("remaining_usd") or 0) < 0.01:
            status["mammouth"] = "BLOCKED:budget_insufficient"
        else:
            # At most ONE paid Mammouth call; synthetic question only.
            childenv = env.copy()
            childenv["BAZOR_DATA_DIR"] = str(WORK / "PRIVATE_CORE_DATA")
            proof_path = WORK / "bridge_runtime_proof.json"
            call = subprocess.run([sys.executable, str(PC / "test_mammouth_ollama_runtime.py"),
                                   "--room-url", core_url, "--model", model, "--output", str(proof_path)],
                                  cwd=str(PC), env=childenv, capture_output=True, timeout=360)
            try:
                proof = json.loads(proof_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                proof = {}
            status["mammouth"] = ("PASS_REAL_BRIDGE" if call.returncode == 0 and
                                  proof.get("status") == "BAZOR_BRIDGE_E2E_OK"
                                  else "BLOCKED:see_bridge_proof")
            report["evidence"]["bridge_proof_path"] = str(proof_path)
            report["evidence"]["bridge_status"] = proof.get("status")
    else:
        status["mammouth"] = "PENDING:explicit_paid_test_not_requested"
    save_report(report)
    return 0 if status.get("mammouth") == "PASS_REAL_BRIDGE" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--test-mammouth", action="store_true",
                        help="Authorizes one bounded external Mammouth call with a synthetic prompt")
    args = parser.parse_args()
    sys.exit(selftest() if args.selftest else run(args.test_mammouth))
