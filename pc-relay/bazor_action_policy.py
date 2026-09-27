"""BAZOR trusted-local control state for read-only actions only.

No caller outside the current process can authorize through JSON, GitHub, or
a command line. An eventual native Windows Hello verifier must be invoked
inside the trusted local UI; until that connection is implemented this gate is
a policy/test module, NOT a machine security boundary or deployment authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import secrets
import time
from typing import Callable

SAFE_ACTIONS = frozenset({
    "ETAT_SERVICES", "AUDIT_LANCEURS", "AUDIT_COMPATIBILITE",
    "AUDIT_APPROFONDI", "INSPECT_RUNTIME_ISOLE",
})
# No shell, file writes, provider spend, update, merge or deployment.
FORBIDDEN_ACTIONS = frozenset({
    "SHELL", "POWERSHELL", "INSTALL", "DELETE", "GIT_PUSH",
    "UPDATE_MAIN", "DEPLOY", "MAMMOUTH", "OPENAI_API",
})
DEFAULT_TTL_SECONDS = 15 * 60
MAX_TTL_SECONDS = 15 * 60


class PermissionDenied(Exception):
    """Fail-closed permission refusal. Never include secrets in message."""


@dataclass(frozen=True)
class LocalSession:
    epoch: int
    scopes: frozenset[str]
    expires_at: float
    session_id: str = field(repr=False)


class DiagnosticGate:
    """Policy component, intended for the trusted Windows desktop process.

    UI verifies Hello on each enable. All service entrypoints MUST enforce
    gate.allow() immediately before EACH typed operation; a JSON checkbox is
    never the source of authority. Do not expose enable() via HTTP or GitHub.
    """

    def __init__(self, hello_verify: Callable[[], bool],
                 is_screen_unlocked: Callable[[], bool],
                 clock: Callable[[], float] = time.monotonic):
        self._hello_verify = hello_verify
        self._is_screen_unlocked = is_screen_unlocked
        self._clock = clock
        self._epoch = 0
        self._session: LocalSession | None = None
        self._panic = False

    @property
    def enabled(self) -> bool:
        return bool(self._session and not self._panic
                    and self._clock() < self._session.expires_at
                    and self._is_screen_unlocked())

    def enable_from_local_ui(self, actions: set[str],
                             ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        # Fail closed: even if Hello fails, old rights are revoked. Invalid
        # scope cannot be "approved" by spoofed UI controls or remote JSON.
        self.disable()
        if self._panic:
            raise PermissionDenied("PANIC_ACTIVE")
        if not actions or not actions <= SAFE_ACTIONS:
            raise PermissionDenied("SCOPE_REFUSED")
        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool):
            raise PermissionDenied("TTL_INVALID")
        if not 0 < ttl_seconds <= MAX_TTL_SECONDS:
            raise PermissionDenied("TTL_INVALID")
        if not self._is_screen_unlocked():
            raise PermissionDenied("WINDOWS_LOCKED")
        try:
            verified = self._hello_verify() is True
        except Exception:
            verified = False
        if not verified or not self._is_screen_unlocked():
            raise PermissionDenied("HELLO_DENIED")
        self._session = LocalSession(
            epoch=self._epoch, scopes=frozenset(actions),
            expires_at=self._clock() + ttl_seconds, session_id=secrets.token_hex(24))

    def allow(self, action: str, *, origin: str = "local_ui") -> bool:
        if action not in SAFE_ACTIONS or origin != "local_ui":
            return False
        if not self.enabled:
            # Expired / Windows locked sessions must never come back later.
            self.disable()
            return False
        assert self._session is not None
        return action in self._session.scopes

    def on_windows_lock(self) -> None:
        self.disable()

    def disable(self) -> None:
        self._epoch += 1
        self._session = None

    def panic(self) -> None:
        self._panic = True
        self.disable()

    def clear_panic_from_local_ui(self) -> None:
        # Clearing PANIC never restores permission or skips Windows Hello.
        self._panic = False
        self.disable()

    def public_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "panic": self._panic,
            "allowed_actions": (sorted(self._session.scopes) if self.enabled
                                and self._session is not None else []),
            "paid_api": False, "shell": False, "deployment": False,
            "auth_kind": "TRUSTED_UI_HELLO_REQUIRED",
        }
