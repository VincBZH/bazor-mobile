# BAZOR Watcher: Unicode and GitHub quota hardening

Scope: existing `pc-relay/bazor_github_watcher.py` only. The previous Ollama-only SMOKE and the Action Engine E2E proof #199/#200 are preserved.

Changes:
- Reconfigure stdout/stderr to UTF-8 with `backslashreplace`. Non-ASCII diagnostics cannot raise `UnicodeEncodeError` on CP1252 Windows consoles.
- On `gh` GraphQL/API rate-limit failure, back off GitHub requests for 300 s (local heartbeat/Core duties still run).
- Cache already completed, one-shot issue IDs in RAM to avoid reading the same GitHub issue comments on every poll; Studio P0 automatic retries remain uncached.
- Retain the existing single-instance lock and all existing task/action restrictions.
- No force-push, reset, merge, checkout or automatic overwrite of the diverged local Windows repository.

Local deployment is **not inferred** from a remote branch or PR. The user's Windows working tree is divergent; apply only a surgical patch after checking exact anchor matches, with an out-of-repo backup, compile check and rollback.

Validation required:
1. Offline Python syntax and preservation/rollback tests.
2. Windows install status with watcher PID and port-8791 lock.
3. A non-ASCII diagnostic and a clean GitHub receipt to prove no encoding crash.
4. Existing BAZOR `[bazor-task:BAZOR-OLLAMA-LOCAL-SMOKE-001]` continues to work.

Limitation: rate-limit backoff and in-memory cache do not solve local Git branch divergence; the remote branch must not be merged onto the working tree without reconciliation.