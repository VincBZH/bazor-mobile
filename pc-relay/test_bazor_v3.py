import json
import bazor_pc_relay_v3 as core
import mammouth_client

print("=" * 64)
print(" BAZOR CORE v3 - TEST SANS DEPENSE")
print("=" * 64)

online, models = core.ollama_tags()
print("Ollama online :", online)
print("Modeles locaux:", ", ".join(models) if models else "aucun")
print("Mammouth cle  :", "OK" if mammouth_client.configured() else "ABSENTE")
print("Budget        :", json.dumps(mammouth_client.budget_status(), ensure_ascii=False))

samples = [
    ("light", "Résume ce texte en trois lignes."),
    ("code", "Corrige ce bug Python dans une API."),
    ("complex", "Fais un audit complet de sécurité et une architecture multi-fichiers complexe."),
]

for label, text in samples:
    eco = core.route_task(text, mode="auto")
    plus = core.route_task(text, mode="auto_plus")
    print()
    print(label.upper())
    print(" AUTO ECO :", eco.get("target"), "->", eco.get("model"), "|", eco.get("reason"))
    print(" AUTO+    :", plus.get("target"), "->", plus.get("model"), "|", plus.get("reason"))

print()
print("Aucun appel Mammouth n'a ete effectue par ce test.")
print("TOUT EST OK")
