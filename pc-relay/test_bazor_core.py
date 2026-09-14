import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8765"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path, payload, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def check(label, fn):
    try:
        value = fn()
        print(f"[OK] {label}")
        return value
    except Exception as exc:
        print(f"[BLOQUE] {label}: {exc}")
        return None


print("=" * 62)
print(" BAZOR CORE v2 - AUTO TEST")
print("=" * 62)
health = check("API health", lambda: get("/api/v1/health"))
if health:
    print("     Version :", health.get("version"))
    print("     PC      :", health.get("pc"))
    print("     Ollama  :", (health.get("ollama") or {}).get("online"))
    print("     OpenAI  :", (health.get("openai") or {}).get("configured"))

route = check("AUTO ECO router", lambda: post("/api/v1/route", {"text": "Corrige un bug Python dans une API"}))
if route:
    r = route.get("route") or {}
    print("     Local   :", r.get("model"))
    print("     GPT sug.:", (r.get("gpt_suggestion") or {}).get("model"))

projects = check("Project registry", lambda: get("/api/v1/projects"))
if projects:
    print("     Projets :", len(projects.get("projects") or []))

if health and (health.get("ollama") or {}).get("online"):
    chat = check("Ollama real chat", lambda: post("/api/v1/chat", {"target": "auto", "text": "Réponds uniquement par OK.", "room": "TEST"}, timeout=90))
    if chat:
        answer = ((chat.get("ollama") or {}).get("answer") or "").strip()
        print("     Réponse :", answer[:120])
else:
    print("[INFO] Test chat Ollama ignoré : Ollama hors ligne.")

print("=" * 62)
print(" Fin du test BAZOR Core v2")
print("=" * 62)
