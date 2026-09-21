import json
import sys
import urllib.error
import urllib.request

CORE_URL = "http://127.0.0.1:8775/api/v1/chat"

payload = {
    "target": "mammouth_ollama",
    "text": (
        "Test technique BAZOR. Ollama doit répondre d'abord, Mammouth doit relire "
        "sa réponse, puis Ollama doit produire la synthèse finale. "
        "La synthèse finale doit contenir exactement le marqueur BAZOR_BRIDGE_E2E_OK."
    ),
    "room": "BAZOR BRIDGE E2E",
    "profile": "recommended",
}

req = urllib.request.Request(
    CORE_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=300) as response:
        data = json.loads(response.read().decode("utf-8"))
except Exception as exc:
    print("BAZOR_BRIDGE_E2E_FAIL: Core inaccessible ou appel interrompu:", exc)
    raise SystemExit(1)

bridge = data.get("bridge") or {}
initial = bridge.get("ollama_initial") or {}
review = bridge.get("mammouth_review") or {}
final = bridge.get("ollama_final") or {}
final_answer = str(bridge.get("final_answer") or final.get("answer") or "")

proof = {
    "bridge_ok": bool(bridge.get("ok")),
    "stage": bridge.get("stage"),
    "provenance": bridge.get("provenance"),
    "ollama_initial_ok": bool(initial.get("ok")),
    "ollama_initial_model": initial.get("model"),
    "mammouth_ok": bool(review.get("ok")),
    "mammouth_model": review.get("model"),
    "mammouth_http_status": review.get("http_status"),
    "ollama_final_ok": bool(final.get("ok")),
    "ollama_final_model": final.get("model"),
    "marker_present": "BAZOR_BRIDGE_E2E_OK" in final_answer,
}
print(json.dumps(proof, ensure_ascii=False, indent=2))

required = (
    proof["bridge_ok"]
    and proof["stage"] == "complete"
    and proof["provenance"] == ["ollama", "mammouth", "ollama"]
    and proof["ollama_initial_ok"]
    and proof["mammouth_ok"]
    and proof["ollama_final_ok"]
    and proof["marker_present"]
)
if not required:
    print("BAZOR_BRIDGE_E2E_FAIL")
    raise SystemExit(1)

print("BAZOR_BRIDGE_E2E_OK")
