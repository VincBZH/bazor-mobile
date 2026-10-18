"""Real model certification through the existing Room gateway. Starts no service."""
import argparse
import hashlib
import json
import platform
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from bazor_bridge import validate
from mammouth_client import redact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--room-url", required=True, help="Verified active Room/Core gateway origin")
    parser.add_argument("--output", default="BAZOR_DATA/bridge_runtime_proof.json")
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.room_url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.path not in ("", "/"):
        parser.error("room-url must be the verified 127.0.0.1 HTTP gateway origin")
    proof = {"status": "BAZOR_BRIDGE_E2E_BLOCKED", "environment": platform.system(),
             "room_url": args.room_url, "http_status": None, "bridge": None}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(args.room_url.rstrip("/") + "/api/v1/health", timeout=5) as response:
            health = json.loads(response.read(131073).decode("utf-8"))
        proof["health"] = {k: health.get(k) for k in ("version", "runtime_signature", "pid", "core_path", "journal_path")}
        signature = hashlib.sha256()
        for name in ("bazor_pc_relay_v3.py", "bazor_action_engine.py", "bazor_security.py", "mammouth_client.py", "bazor_bridge.py"):
            signature.update(name.encode("utf-8"))
            signature.update(Path(__file__).with_name(name).read_bytes())
        if health.get("service") != "BAZOR API" or health.get("runtime_signature") != signature.hexdigest():
            raise ValueError("active_core_code_mismatch")
        if not isinstance(health.get("pid"), int) or not health.get("core_path"):
            raise ValueError("active_core_identity_missing")
        if not (health.get("mammouth") or {}).get("configured"):
            raise ValueError("mammouth_key_missing_on_active_core")
        request = urllib.request.Request(args.room_url.rstrip("/") + "/api/v1/chat",
            data=json.dumps({"target": "mammouth_ollama", "text": "Combien font 2+2 ? Réponds 4.",
                "bridge_e2e": True, "profile": "recommended", "room": "BAZOR BRIDGE E2E"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with opener.open(request, timeout=300) as response:
            proof["http_status"] = response.status
            raw = response.read(131073)
            if len(raw) > 131072:
                raise ValueError("room_response_too_large")
            data = json.loads(raw.decode("utf-8"))
        bridge = data.get("bridge") or {}
        proof["bridge"] = bridge
        if not data.get("ok") or not bridge.get("ok") or bridge.get("stage") != "complete" or not validate(bridge, True):
            raise ValueError("bridge_contract_failed")
        proof["status"] = "BAZOR_BRIDGE_E2E_OK"
    except Exception as exc:
        proof["error"] = type(exc).__name__ + ": " + str(exc)
        proof["http_status"] = getattr(exc, "code", proof["http_status"])
    proof = redact(proof)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0 if proof["status"] == "BAZOR_BRIDGE_E2E_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
