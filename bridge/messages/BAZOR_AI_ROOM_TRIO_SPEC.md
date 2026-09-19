# BAZOR AI ROOM TRIO SPEC — REVIEW PACK v2.4.2

PROJECT: bazor-ai-room-v2-lite
REFERENCE_SPEC_REPO: VincBZH/projetWII-ai-relay
REFERENCE_SPEC_PATH: bazor_room_v2/BAZOR_AI_ROOM_TRIO_SPEC.md
REFERENCE_SPEC_COMMIT: b9e06efa4aab3f53fd8ae0c50b58da9571b41fd5

IMPORTANT:
Le commit ci-dessus appartient au dépôt VincBZH/projetWII-ai-relay, pas à VincBZH/bazor-mobile.
Ne jamais rattacher ce SHA au mauvais dépôt.

RUNTIME MAP:
- AI ROOM UI/API: 127.0.0.1:8765
- BAZOR Core: 127.0.0.1:8775
- BAZOR Gateway/mobile: 127.0.0.1:8776
- Ollama local: 127.0.0.1:11434

REVIEW REQUIREMENTS:
1. Vérifier la séparation des versions application/protocole/Registry/contrat.
2. Vérifier ROOM_CORE_DELIVERED distinct de TRIO_READY.
3. Vérifier identités persistantes agent_id/provider/role/writes_via/cannot_claim.
4. Vérifier bootstrap: identities -> rules/message_contract -> registry -> encyclopedia -> current state -> project/conversation -> tasks/handoffs -> runtime capabilities.
5. Vérifier enum:
   task = NEW/RUNNING/VERIFIE + ANALYSE_SEULE/PARTIAL/QUEUED/BLOCKED/NEEDS_HUMAN
   product = BUILDING/RUNTIME_PASS/DELIVERED
6. ANALYSE_SEULE ne progresse jamais une tâche d'exécution.
7. Ollama ne modifie jamais directement les fichiers; toute écriture passe par BAZOR Action Engine.
8. Vérifier provenance mémoire obligatoire:
   source_agent, source_file, source_message_id, verified_by, confidence, last_verified_at.
9. Une mémoire ne peut modifier silencieusement identité/sécurité/capacité runtime.
10. Sur échec: incident -> rollback si nécessaire -> correction déterministe -> retry borné -> provider alternatif -> queue -> NEEDS_HUMAN.
11. Ne pas utiliser les anciennes docs 2.3 comme référence active en cas de contradiction.
12. Réconcilier avec dépôt/runtime réels; aucun PASS sur texte seul.

RESPONSE_FORMAT:
Répondre en texte structuré avec:
STATUS: VERIFIE|BLOCKED
TARGET: <ollama|mammouth>
SUMMARY: <court>
CONFIRMED:
- ...
CONTRADICTIONS:
- ...
MINIMAL_FIXES:
- ...
RUNTIME_EVIDENCE:
- ...
NEXT: <une action>

Pour Ollama, inclure exactement le nonce:
OLLAMA-FILEBUS-20260919-OK

Pour Mammouth, inclure exactement le nonce:
MAMMOUTH-FILEBUS-20260919-OK
