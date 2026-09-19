PROJECT: BAZOR Studio V4
REQUEST_ID: STUDIO-TRIO-P0-AUTORUN-MAMMOUTH-20260919
AGENT_ID_EXPECTED: mammouth
ROLE: independent_external_reviewer

OBJECTIVE:
Review the Studio P0 chain without writing critical files directly.

ORDER:
1. STUDIO-P0-012 — strict T2I/I2I/T2V/I2V routing, no ghost source.
2. STUDIO-P0-010 — real local media loading for post-generation vision analysis.
3. STUDIO-P0-011 — safe E2E Studio→ComfyUI generation proof.

RULES:
- Read the real files/context supplied by BAZOR/FileBus.
- Do not claim to be GPT or Ollama.
- Do not declare PASS from plans, prose, manual nonce or generic OK.
- Return concrete risks, file-level findings, acceptance-test gaps and minimal corrective advice.
- If provider/runtime is unavailable, return BLOCKED with the exact provider error; do not fake success.
- Do not ask Vincent to copy/paste between agents.

COORDINATION:
- GPT = coordinator/arbitrator and proof reviewer.
- Ollama = local code/context analyst.
- Mammouth = independent second review.
- BAZOR Action Engine = only component allowed to apply file changes after preflight/tests.
- GitHub/FileBus = durable handoff/proof bus.

RESPONSE_FORMAT:
STATUS: VERIFIE|PARTIAL|BLOCKED
AGENT_ID: mammouth
TASK_ID: <STUDIO-P0-012|STUDIO-P0-010|STUDIO-P0-011>
FILES_READ: [...]
FINDINGS: [...]
RISKS: [...]
TESTS_REQUIRED: [...]
BLOCKERS: [...]
NEXT: <one action>

Do not block deterministic local work solely because Mammouth is unavailable; mark the review pending/blocked and let GPT/BAZOR proceed where proofs are sufficient.