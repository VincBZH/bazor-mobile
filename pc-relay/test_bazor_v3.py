import json
import os
import py_compile
import urllib.request

import bazor_security
import mammouth_client

print("=" * 64)
print(" BAZOR CORE v3 - TEST SANS DEPENSE")
print("=" * 64)

here = os.path.dirname(os.path.abspath(__file__))
core_path = os.path.join(here, "bazor_pc_relay_v3.py")
client_path = os.path.join(here, "mammouth_client.py")
security_path = os.path.join(here, "bazor_security.py")

try:
    py_compile.compile(core_path, doraise=True)
    py_compile.compile(client_path, doraise=True)
    py_compile.compile(security_path, doraise=True)
    print("Code Python   : OK")
except Exception as exc:
    print("Code Python   : BLOQUE", exc)
    raise SystemExit(1)

try:
    parser_cases = [
        ({"choices": [{"message": {"content": "texte simple"}}]}, "texte simple"),
        ({"choices": [{"message": {"content": [{"type": "text", "text": "texte en parties"}]}}]}, "texte en parties"),
        ({"output_text": "texte sortie"}, "texte sortie"),
    ]
    for payload, expected in parser_cases:
        assert mammouth_client._extract_answer(payload) == expected
    assert mammouth_client._extract_answer({"choices": [{"message": {"content": ""}}]}) == ""
    print("Reponses API  : OK")
except Exception as exc:
    print("Reponses API  : BLOQUE", exc)
    raise SystemExit(1)

try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.2) as response:
        data = json.loads(response.read().decode("utf-8"))
    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    print("Ollama        : OK")
    print("Modeles locaux:", ", ".join(models) if models else "aucun")
except Exception:
    print("Ollama        : HORS LIGNE")

print("Mammouth cle  :", "OK" if mammouth_client.configured() else "ABSENTE")
print("Budget        :", json.dumps(mammouth_client.budget_status(), ensure_ascii=False))
print()
print("Aucun appel Mammouth n'a ete effectue par ce test.")
print("TOUT EST OK")
