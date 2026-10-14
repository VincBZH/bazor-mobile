# BAZOR Ollama-only local smoke probe

This adds an **independent** diagnosis for the existing BAZOR bridge.
It does not change AIROOM-P0-003, does not manufacture trio E2E proof,
and never marks Mammouth or GPT as available.

After this branch has been safely deployed on the PC, create an issue in
VincBZH/bazor-mobile with a title beginning:

    [bazor-task:BAZOR-OLLAMA-LOCAL-SMOKE-001]

The existing Watcher will then run a **hardcoded, read-only** local probe:
1. GET Core 8775 health.
2. GET Room 8765 health.
3. GET Ollama 11434 model tags.
4. POST one short nonce challenge **through Core** with target=ollama,
   explicit local model, and a new nonce; verify real provider/model/answer.
5. Import and inspect the ActionEngine API without constructing it or
   calling apply (no write, no sandbox execution).
6. Return LOCAL_ONLY_READY or LOCAL_ONLY_BLOCKED with precise checks.

All endpoints are fixed 127.0.0.1 loopback addresses.
There is no arbitrary shell command, no external provider, no downloads,
no model modification, and no applied file action. The Watcher posts
the sanitized report back to the originating GitHub issue.
The Core may independently generate its usual operational log.

**What a pass means:** Ollama local communication through Core works,
and the safe Action Engine class interface exists. It does NOT prove
that Action Engine has successfully edited files in this session, and
is NOT permission to make arbitrary edits.

**Offline tests:** Run with Python 3.11+ in a development environment:

    python -m unittest discover -s pc-relay/tests -p test_bazor_ollama_local_smoke.py

The unit tests use fake loopback endpoints, no actual Ollama installation.
A real Windows E2E pass must be obtained separately before marking
the installed bridge as verified.

## Deployment stop condition

The Windows working tree is known to have diverged significantly
from origin/main and contains local modifications. Do not force pull,
merge, reset, checkout, rebase, or overwrite that working tree.
This branch and its PR are **review-only until a backup and a safe
reconciliation or targeted installation has been validated locally**.
Opening/merging a PR does not prove deployment or Windows testing.
