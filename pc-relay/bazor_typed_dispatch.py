"""Typed, fixed-action dispatcher for the existing BAZOR bridge (no shell).

Only trusted host code may construct a dispatcher and classify a GitHub
request as verified_github_owner after checking author and repository identity.
A string in an issue is NOT authorization. Never expose this dispatcher
as an unauthenticated HTTP endpoint; diagnostics only until signed IPC exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bazor_action_policy import DiagnosticGate, SAFE_ACTIONS

PUBLIC_CODES = frozenset({"OK", "BLOCKED", "UNAVAILABLE", "NOT_VERIFIED"})


@dataclass(frozen=True)
class PublicOutcome:
    action: str
    code: str

    def public_report(self) -> str:
        # Closed vocabulary. Provider/launcher results and prompts are not
        # part of the issue comment and never get stringified here.
        action = self.action if self.action in SAFE_ACTIONS else "DENIED"
        code = self.code if self.code in PUBLIC_CODES else "BLOCKED"
        return "\n".join((
            "[BAZOR-GATED-DIAGNOSTIC]", "ACTION: " + action,
            "RESULT: " + code, "PAID_AI_CALLS: ZERO",
            "DEPLOYMENT: NEVER_PERFORMED",
        ))


class TypedDispatcher:
    def __init__(self, gate: DiagnosticGate, registry: dict[str, Callable[[], str]]):
        if not registry or not set(registry) <= SAFE_ACTIONS:
            raise ValueError("UNAPPROVED_REGISTRY")
        if not all(callable(fn) for fn in registry.values()):
            raise ValueError("NONCALLABLE_ACTION")
        self._gate = gate
        self._registry = dict(registry)

    def execute(self, action: str, *, trusted_origin: str) -> PublicOutcome:
        if action not in self._registry:
            return PublicOutcome("DENIED", "BLOCKED")
        if not self._gate.allow(action, origin=trusted_origin):
            return PublicOutcome(action, "BLOCKED")
        try:
            status = self._registry[action]()
        except Exception:
            return PublicOutcome(action, "BLOCKED")
        # PANIC or Windows lock while running => no publication of success.
        if not self._gate.allow(action, origin=trusted_origin):
            return PublicOutcome(action, "BLOCKED")
        return PublicOutcome(action, status if status in PUBLIC_CODES else "BLOCKED")
