import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELAY = ROOT / "pc-relay"
sys.path.insert(0, str(RELAY))

import mammouth_client

DATA = RELAY / "BAZOR_DATA"
DATA.mkdir(parents=True, exist_ok=True)
REPORT = DATA / "HUB_EXPERT_REVIEW.json"
LOG = DATA / "HUB_LOGS" / "expert_review.log"
LOG.parent.mkdir(parents=True, exist_ok=True)

FILES = [
    ROOT / "console-hub" / "bazor_console_hub.py",
    ROOT / "pc-relay" / "bazor_pc_relay_v3.py",
    ROOT / "pc-relay" / "bazor_github_watcher.py",
    ROOT / "pc-relay" / "bazor_security.py",
    ROOT / "LANCER_BAZOR_CONSOLE_HUB.cmd",
]

EXPERTS = [
    ("deepseek", "Expert code Windows/Python. Cherche bugs, courses critiques, doublons de processus et erreurs de lancement."),
    ("claude", "Expert architecture et sécurité. Vérifie isolation, arrêt sûr, logs, authentification et absence de shell distant dangereux."),
    ("gemini", "Expert fiabilité et UX. Vérifie que Vincent peut comprendre immédiatement quoi garder, fermer, relancer et quel projet est concerné."),
]

def stamp(msg):
    line = time.strftime("%H:%M:%S") + " " + msg
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def source_hash():
    h = hashlib.sha256()
    for p in FILES:
        if p.exists():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()

def static_tests():
    results = []
    for p in FILES:
        if not p.exists():
            results.append({"file": str(p.relative_to(ROOT)), "ok": False, "error": "missing"})
            continue
        if p.suffix == ".py":
            try:
                src = p.read_text(encoding="utf-8")
                compile(src, str(p), "exec")
                results.append({"file": str(p.relative_to(ROOT)), "ok": True})
            except Exception as exc:
                results.append({"file": str(p.relative_to(ROOT)), "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        else:
            results.append({"file": str(p.relative_to(ROOT)), "ok": True})
    return results

def bundle():
    chunks = []
    remaining = 60000
    for p in FILES:
        if remaining <= 1000 or not p.exists():
            break
        txt = p.read_text(encoding="utf-8", errors="replace")
        take = txt[:min(18000, remaining)]
        chunks.append(f"\n===== {p.relative_to(ROOT)} =====\n{take}")
        remaining -= len(take)
    return "".join(chunks)

def main():
    digest = source_hash()
    if REPORT.exists():
        try:
            old = json.loads(REPORT.read_text(encoding="utf-8"))
            if old.get("source_hash") == digest and old.get("status") in ("done","static_failed"):
                stamp("Review déjà faite pour cette version - pas de nouvel appel Mammouth.")
                return 0
        except Exception:
            pass

    tests = static_tests()
    if not all(x.get("ok") for x in tests):
        data = {"status": "static_failed", "source_hash": digest, "tests": tests, "experts": []}
        REPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        stamp("Tests statiques en échec - review Mammouth annulée.")
        return 2

    stamp("Tests statiques OK.")
    if not mammouth_client.configured():
        data = {"status": "mammouth_not_configured", "source_hash": digest, "tests": tests, "experts": []}
        REPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        stamp("Mammouth non configuré - review experte non lancée.")
        return 0

    src = bundle()
    reviews = []
    for model, role in EXPERTS:
        stamp(f"Review Mammouth : {model}...")
        prompt = (
            "Tu es mandaté comme reviewer indépendant de BAZOR Console Hub.\n"
            + role + "\n"
            "Contexte: Windows 11; l'outil centralise Core 8775, Web 8776 et GitHub Watcher; "
            "il doit éviter les multiples CMD et ne jamais fermer un processus non reconnu. "
            "Aucun shell distant, aucun secret dans le mobile.\n"
            "Donne: VERDICT: PASS|PASS_WITH_FIXES|FAIL, puis RISQUES, CORRECTIONS PRIORITAIRES, TESTS À FAIRE. "
            "Sois précis et concis. N'invente pas des fichiers absents.\n"
            "CODE À RELIRE:\n" + src
        )
        result = mammouth_client.chat(prompt, task_kind="complex", profile=model, max_tokens=1200)
        reviews.append({
            "model_requested": model,
            "ok": bool(result.get("ok")),
            "model": result.get("model"),
            "answer": result.get("answer") or result.get("message") or result.get("error"),
            "estimated_cost_usd": result.get("estimated_cost_usd"),
        })
        stamp(f"{model}: " + ("OK" if result.get("ok") else "ECHEC"))

    data = {
        "status": "done",
        "source_hash": digest,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tests": tests,
        "experts": reviews,
        "budget": mammouth_client.budget_status(),
    }
    REPORT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    stamp("Review experte terminée. Rapport: " + str(REPORT))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
