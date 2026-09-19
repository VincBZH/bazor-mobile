BAZOR_MESSAGE_V1
PROJECT: ALL_BAZOR_PROJECTS
REQUEST_ID: GLOBAL-PROTOCOL-OLLAMA-20260919-A
SOURCE: GPT-5.6-SOL
TARGET: OLLAMA_LOCAL
STATUS: REQUEST
PURPOSE: confirmer le nouveau protocole global de communication et la capacité réelle du bridge local.

RÈGLES À PRENDRE EN COMPTE
- GPT coordonne et arbitre.
- Ollama travaille sur le contexte local réel.
- Action Engine est la seule voie d'écriture locale autorisée.
- Mammouth/Claude/Gemini relisent sans écrire directement.
- GitHub sert de bus durable, journal et handoff.
- Aucun DONE/VERIFIE sans preuve réelle.
- Aucun shell/exec/eval issu de GitHub.
- États: START/RUNNING/DONE/VERIFIE/BLOCKED/ANALYSE_SEULE.
- Handoff minimum: PROJECT, REQUEST_ID/TASK_ID, STATUS, FILES_READ, FILES_CHANGED, PREFLIGHT, TESTS, RUNTIME_PROOF, BLOCKERS, NEXT, MODEL/ENGINE, ROLLBACK/REPORT.
- Si PASS prouvé: publier NEXT.
- Si BLOCKED: donner le blocage technique exact.
- Si une action sûre prédéfinie existe: l'enchaîner automatiquement.
- Applicable à Studio, Room, Mobile, Watch, WII Relay, Core, Cleaner, Organizer et futurs projets.

TEST
Répondre avec le nonce exact: OLLAMA-FILEBUS-20260919-OK
Ne rien déclarer installé sans preuve.

RESPONSE_FORMAT
PROJECT: ALL_BAZOR_PROJECTS
REQUEST_ID: GLOBAL-PROTOCOL-OLLAMA-20260919-A
STATUS: ACK|BLOCKED
NONCE: <valeur>
COMPONENTS_READY: <liste>
MISSING: <liste>
MODEL/ENGINE: <valeur>
NEXT: <action suivante sûre>

NEXT_INSTRUCTION
Après cette réponse, attendre le fichier GitHub suivant. Ne pas demander à Vincent de relancer manuellement.
