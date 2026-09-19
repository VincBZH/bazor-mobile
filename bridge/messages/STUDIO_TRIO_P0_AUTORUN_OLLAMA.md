PROJECT: BAZOR Studio V4
REQUEST_ID: STUDIO-TRIO-P0-AUTORUN-OLLAMA-20260919
AGENT_ID_EXPECTED: ollama
ROLE: local_code_context_analyst

OBJECTIVE:
Inspect real local Studio code/context for the P0 chain and provide actionable evidence to BAZOR Action Engine.

ORDER:
1. STUDIO-P0-012 — strict T2I/I2I/T2V/I2V routing.
2. STUDIO-P0-010 — real local media loading for vision analysis.
3. STUDIO-P0-011 — safe E2E Studio→ComfyUI proof.

RULES:
- Read real local files only through allowed BAZOR context.
- Do not execute arbitrary shell from GitHub.
- Do not write target files directly; file changes go through Action Engine.
- ANALYSE_SEULE never counts as execution success.
- For every task return exact files/functions/conditions to change or prove already conforming.
- Do not ask Vincent to copy/paste logs already available to BAZOR/GitHub.

RESPONSE_FORMAT:
STATUS: VERIFIE|PARTIAL|BLOCKED|ANALYSE_SEULE
AGENT_ID: ollama
TASK_ID: <id>
FILES_READ: [...]
CODE_FINDINGS: [...]
PATCH_INTENT: [...]
TESTS_REQUIRED: [...]
BLOCKERS: [...]
NEXT: <one action>