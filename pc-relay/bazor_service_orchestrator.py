"""Bounded Core/Room process orchestration around a BAZOR transaction.

No Windows process implementation is included: this defines a fail-closed
contract for a later, locally authorized adapter. Tests use a fake backend.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
import time
import bazor_transactional_deployer as deployer

CORE_PORT, ROOM_PORT, OLLAMA_PORT = 8775, 8765, 11434
LOCAL_PROBE = "Reponds uniquement BAZOR_LOCAL_OK"

@dataclass(frozen=True)
class ProcessIdentity:
    component: str
    pid: int
    port: int
    executable_sha256: str
    owned_by_current_user: bool

@dataclass(frozen=True)
class ExpectedService:
    component: str
    port: int
    executable_sha256: str

class ProcessBackend(Protocol):
    def inspect_port(self, port: int) -> ProcessIdentity | None: ...
    def stop_pid(self, pid: int) -> bool: ...
    def wait_stopped(self, pid: int, timeout_seconds: int) -> bool: ...
    def start_service(self, component: str, program_root: Path, port: int) -> int: ...
    def health(self, component: str, port: int) -> bool: ...
    def local_chat(self, core_port: int, ollama_port: int, prompt: str) -> bool: ...

def _verified(identity: ProcessIdentity | None, expected: ExpectedService) -> bool:
    return bool(identity and identity.component == expected.component
                and identity.port == expected.port and identity.pid > 0
                and identity.owned_by_current_user
                and identity.executable_sha256 == expected.executable_sha256)

def _capture(backend: ProcessBackend, expected: tuple[ExpectedService, ...]):
    captured, pids = {}, set()
    for item in expected:
        identity = backend.inspect_port(item.port)
        if not _verified(identity, item):
            raise RuntimeError("service_identity_mismatch")
        assert identity is not None
        if identity.pid in pids:
            raise RuntimeError("shared_pid_forbidden")
        pids.add(identity.pid)
        captured[item.component] = identity
    if set(captured) != {"core", "room"}:
        raise RuntimeError("service_set_invalid")
    return captured

def _stop_captured(backend: ProcessBackend, captured):
    for component in ("room", "core"):
        identity = captured[component]
        if backend.inspect_port(identity.port) != identity:
            raise RuntimeError("service_changed_after_preflight")
        if not backend.stop_pid(identity.pid):
            raise RuntimeError("stop_refused")
        if not backend.wait_stopped(identity.pid, 15):
            raise RuntimeError("stop_timeout")

def _restore_after_stop_failure(backend: ProcessBackend, captured, roots) -> bool:
    """Recover a partially stopped old generation before any filesystem move."""
    try:
        for component in ("core", "room"):
            old = captured[component]
            current = backend.inspect_port(old.port)
            if current is None:
                pid = backend.start_service(component, roots[component], old.port)
                current = backend.inspect_port(old.port)
                if current is None or current.pid != pid:
                    return False
            # A different listener may own the port. Never stop or replace it.
            if not _verified(current, ExpectedService(component, old.port,
                                                       old.executable_sha256)):
                return False
            if not backend.health(component, old.port):
                return False
        return backend.local_chat(captured["core"].port, OLLAMA_PORT, LOCAL_PROBE)
    except Exception:
        return False

def _start_and_verify(backend, core_root, room_root, expected):
    by_name, started = {x.component: x for x in expected}, {}
    for component, root in (("core", core_root), ("room", room_root)):
        item = by_name[component]
        pid = backend.start_service(component, root, item.port)
        deadline = time.monotonic() + 15
        identity = backend.inspect_port(item.port)
        while identity is None and time.monotonic() < deadline:
            time.sleep(0.1)
            identity = backend.inspect_port(item.port)
        if not _verified(identity, item) or identity is None or identity.pid != pid:
            raise RuntimeError("started_service_identity_mismatch")
        if not backend.health(component, item.port):
            raise RuntimeError("service_health_failed")
        started[component] = pid
    if not backend.local_chat(by_name["core"].port, OLLAMA_PORT, LOCAL_PROBE):
        raise RuntimeError("local_chat_failed")
    return started

def _stop_started(backend, pids, expected):
    by_name = {item.component: item for item in expected}
    for component in ("room", "core"):
        pid = pids.get(component)
        if not pid:
            continue
        port = by_name[component].port
        identity = backend.inspect_port(port)
        if identity is not None and identity.pid == pid:
            backend.stop_pid(pid)
            backend.wait_stopped(pid, 15)

def _stop_verified_generation(backend, expected):
    """Stop only processes that still match the exact promoted identities."""
    for item in sorted(expected, key=lambda x: x.component != "room"):
        identity = backend.inspect_port(item.port)
        if not _verified(identity, item):
            continue
        assert identity is not None
        backend.stop_pid(identity.pid)
        backend.wait_stopped(identity.pid, 15)

def promote_with_runtime_verification(
    txroot: Path, txid: str, auth_path: Path, backend: ProcessBackend,
    expected_old: tuple[ExpectedService, ExpectedService],
    expected_new: tuple[ExpectedService, ExpectedService],
    commit_fn: Callable[..., dict] = deployer.commit,
    rollback_fn: Callable[..., dict] = deployer.rollback,
) -> dict:
    """Use the one-time local authorization; never expose this to GitHub."""
    try:
        deployer.validate_authorization(txroot, txid, auth_path)
    except Exception:
        return {"ok": False, "phase": "AUTHORIZATION_REFUSED",
                "rollback_ok": False, "old_services_restored": False}
    captured = _capture(backend, expected_old)
    try:
        _stop_captured(backend, captured)
    except Exception:
        try:
            state = deployer._state(txroot, txid)
            restored = _restore_after_stop_failure(backend, captured, {
                "core": Path(state["core_live"]), "room": Path(state["room_live"])})
        except Exception:
            restored = False
        return {"ok": False,
                "phase": "PRECOMMIT_RECOVERED" if restored else "MANUAL_REQUIRED",
                "rollback_ok": False, "old_services_restored": restored}
    promoted = {}
    try:
        result = commit_fn(txroot, txid, auth_path)
        if not result.get("ok"):
            raise RuntimeError("filesystem_commit_failed")
        state = deployer._state(txroot, txid)
        promoted = _start_and_verify(
            backend, Path(state["core_live"]), Path(state["room_live"]), expected_new)
        return {"ok": True, "phase": "RUNTIME_VERIFIED", "rollback_ok": False,
                "old_pids_stopped": 2, "new_pids_started": 2}
    except Exception:
        _stop_started(backend, promoted, expected_new)
        _stop_verified_generation(backend, expected_new)
        try:
            rb = rollback_fn(txroot, txid, "runtime_verification_failed")
        except Exception:
            rb = {"ok": False}
        old_restarted = False
        if rb.get("ok"):
            try:
                state = deployer._state(txroot, txid)
                _start_and_verify(
                    backend, Path(state["core_live"]), Path(state["room_live"]), expected_old)
                old_restarted = True
            except Exception:
                pass
        return {"ok": False,
                "phase": "ROLLED_BACK" if rb.get("ok") and old_restarted else "MANUAL_REQUIRED",
                "rollback_ok": bool(rb.get("ok")),
                "old_services_restored": old_restarted,
                "rollback_error_kind": rb.get("error_kind"),
                "rollback_winerror": rb.get("winerror")}

def public_summary(result: dict) -> str:
    phase = result.get("phase")
    if phase not in {"RUNTIME_VERIFIED", "ROLLED_BACK", "PRECOMMIT_RECOVERED",
                     "AUTHORIZATION_REFUSED",
                     "MANUAL_REQUIRED"}:
        phase = "MANUAL_REQUIRED"
    return "\n".join(("[BAZOR-SERVICE-ORCHESTRATION]", "PHASE: " + phase,
        "OK: " + ("YES" if result.get("ok") else "NO"),
        "ROLLBACK_OK: " + ("YES" if result.get("rollback_ok") else "NO"),
        "OLD_SERVICES_RESTORED: " + ("YES" if result.get("old_services_restored") else "NO"),
        "LOCAL_OLLAMA_CHECK: REQUIRED", "PAID_AI_CALLS: ZERO",
        "GITHUB_COMMAND_EXECUTION: FORBIDDEN"))
