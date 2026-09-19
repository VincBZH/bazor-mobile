# BAZOR AI ROOM TRIO — GPT • Ollama • Mammouth

Spec version: **2.4.2**
Status: **REFERENCE_CORRECTED / IMPLEMENTATION_REQUIRED**

## 1. Versioning — never collapse versions
- room_app_version: detected from deployed Room/build metadata
- protocol_schema_version: detected from Room protocol/state
- registry_version: detected from `bazor_registry.json`
- message_contract_version: detected from canonical message contract
- Never hardcode one version as the version of all components.

## 2. Canonical ports
- AI Room UI/API: `127.0.0.1:8765`
- BAZOR Core: `127.0.0.1:8775`
- BAZOR Gateway/mobile: `127.0.0.1:8776`
- Ollama: `127.0.0.1:11434`
- Detect actual runtime binding before declaring availability.

## 3. Persistent machine identities
Canonical source: `context/IDENTITIES.json`.
Every internal message must carry immutable `agent_id`.

Required fields per agent:
- `agent_id`
- `display_name`
- `provider`
- `role`
- `capabilities`
- `forbidden_claims`
- `writes_via`

Identity rules:
- GPT never claims to be Mammouth or Ollama.
- Mammouth never claims to be GPT or Ollama.
- Ollama never claims to be GPT or Mammouth.
- BAZOR Core orchestrates; it does not impersonate a model.

## 4. Canonical bootstrap order
At start of a new day or conversation:
1. `context/IDENTITIES.json`
2. canonical rules + message contract
3. `bazor_registry.json`
4. `BAZOR_ENCYCLOPEDIA.md`
5. `context/CURRENT_STATE.json` / runtime state
6. project summary + conversation summary
7. open tasks + recent handoffs/FileBus
8. runtime capability checks

Sources of truth:
- rules/message contract govern protocol;
- Registry governs projects/tasks;
- CURRENT_STATE governs runtime;
- Encyclopédie explains/consolidates but is not the sole source of truth.

## 5. Local contextual memory
Context is persistent memory, not model retraining.

Recommended structure:
`context/IDENTITIES.json`
`context/CURRENT_STATE.json`
`context/projects/<project_id>/SUMMARY.md`
`context/projects/<project_id>/FACTS.jsonl`
`context/projects/<project_id>/DECISIONS.jsonl`
`context/projects/<project_id>/OPEN_TASKS.json`
`context/conversations/<conversation_id>.jsonl`
`context/conversations/<conversation_id>.summary.md`
`context/daily/YYYY-MM-DD.md`
`context/index.json`

Each persistent memory record must include provenance:
- `source_agent`
- `source_file` or `source_message_id`
- `verified_by`
- `confidence`
- `last_verified_at`
- type: `fact|hypothesis|decision|preference|task|proof`

Security rule: persistent memory may never silently override identity, security policy or runtime capability state.

## 6. Status model
Task progression:
`NEW -> RUNNING -> VERIFIE`

Lateral/non-progress states:
`ANALYSE_SEULE | PARTIAL | QUEUED | BLOCKED | NEEDS_HUMAN`

Product/build state:
`PROTOCOL_READY -> CODE_PATCHED -> CI_PASS -> RUNTIME_PASS -> DELIVERED`

Rules:
- `ANALYSE_SEULE` never advances an execution task.
- `VERIFIE` requires appropriate evidence: files/preflight/tests and/or runtime proof.
- `DELIVERED` is reserved for product/build completion after all required gates.
- a manual nonce or generic OK is never proof.

## 7. Separate delivery gates
- `ROOM_CORE_DELIVERED`: UI + Core + Action Engine + runtime + security are proven.
- `TRIO_READY`: GPT + Ollama + Mammouth are each really reachable and identified, with a proven exchange through Room/FileBus/API.
- Room may run in degraded mode if one external reviewer is unavailable, but `TRIO_READY=false` until all three are proven.

## 8. Execution boundaries
- Ollama analyzes/proposes; writes only through BAZOR Action Engine.
- Mammouth is external second review; no direct critical-file writes.
- GPT coordinates/arbitrates and validates evidence.
- BAZOR Action Engine owns preflight, backup, apply, deterministic tests, rollback.
- No shell/exec/eval command is accepted from GitHub/FileBus.

## 9. Automatic recovery
On failure:
`incident -> rollback if needed -> deterministic correction -> bounded retry -> alternate provider -> queue -> NEEDS_HUMAN only when no safe automatic path remains`

Do not ask Vincent for copy/paste of information already available in Room, GitHub or FileBus.

## 10. Build golden rule
Every new build/patch must synchronize:
- code/artifacts
- tests
- runtime proof
- `BAZOR_ENCYCLOPEDIA.md`
- `bazor_registry.json`
- version/build metadata
- rollback/backup metadata
- known limitations + next step

A build is incomplete if Encyclopédie and Registry are not synchronized.

## 11. UI requirements
Header: **BAZOR AI ROOM TRIO — GPT • Ollama • Mammouth**

Always show:
- agent identity
- actual provider/model
- CONNECTED / LIMITED / UNAVAILABLE
- current project/task
- context loaded state
- last Registry/Encyclopédie sync
- FileBus status
- last runtime proof

## 12. Acceptance tests
Minimum tests before calling Trio ready:
1. one Vincent message routes to at least two engines;
2. each response carries the correct immutable agent identity;
3. results appear in Room without human copy/paste;
4. new conversation reloads project context;
5. next-day session can recover a verified prior decision;
6. Registry + Encyclopédie are synchronized for the build;
7. Ollama remains loopback-only;
8. Action Engine prevents direct model writes;
9. provider failure produces BLOCKED/PARTIAL, never false VERIFIE;
10. `ROOM_CORE_DELIVERED` and `TRIO_READY` are reported separately.

## 13. Reconciliation rule
Do not copy an old specification into code. Reconcile this spec with the actual repository and runtime before implementation.
Any mismatch must be logged explicitly as `SPEC_DRIFT` and resolved before `DELIVERED`.