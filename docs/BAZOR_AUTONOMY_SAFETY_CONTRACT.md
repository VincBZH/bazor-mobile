# BAZOR autonomy safety contract

Status: design + testable contract only. This file does **not** enable Windows Hello or autonomous execution.

## Deployment gates

A deployment must remain blocked unless all gates have independent evidence:

1. BACKUP_VERIFIED: backup archive passes integrity checks and a restore simulation succeeds.
2. STAGED: candidate is isolated from the active Core and Room.
3. COMPAT_VERIFIED: candidate syntax/imports/routes/ports and persistent-data formats are checked without overwriting user state.
4. RUNTIME_VERIFIED: active Core, Room and Ollama answer real probes; simulated CI is not runtime evidence.
5. WATCHER_CERTIFIED: a request created after watcher startup is consumed by that watcher and returns the same request id.
6. AUTH_VERIFIED: future autonomy session is created only after local Windows Hello verification; a UI checkbox or JSON boolean is never authority.
7. ROLLBACK_VERIFIED: failed candidate can restore the prior snapshot and preserve history/settings.

## Authority model

- Core is the local policy authority.
- Ollama is local/default and may be used with zero external API cost.
- Mammouth and GPT are external providers and default to disabled until an explicit budget/profile is configured.
- GitHub carries coordination and sanitized evidence, not secrets, raw launcher contents, histories, API keys or arbitrary shell instructions.
- No GitHub issue/comment may directly authorize shell execution.
- PANIC and autonomy-off prevent new work immediately. Sensitive scope expansion requires a fresh local authentication.

## Evidence vocabulary

Use only: PENDING, PASS, FAIL, BLOCKED. A PASS must include the evidence source and timestamp. CI/simulation and Windows runtime evidence must be labelled separately.

Current issue #171 evidence on 2026-09-27 proves a read-only GitHub -> local Bridge -> GitHub round trip and reports Core/Room/Ollama responsive. It does not prove deployment compatibility, Windows Hello, paid-provider routing, rollback, or the legacy watcher runtime.
