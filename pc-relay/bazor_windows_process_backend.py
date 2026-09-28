"""Windows-only backend for bounded BAZOR Core/Room orchestration.

Process mutation is disabled by default. Enabling it is only one technical
gate: the caller must still satisfy the transaction's one-time local
authorization. Commands and arguments are fixed locally; GitHub text is never
executed. Provider credentials are removed from child environments.
"""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import unicodedata

from bazor_service_orchestrator import ProcessIdentity

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000
TOKEN_QUERY = 0x0008
TOKEN_USER = 1
STILL_ACTIVE = 259
WAIT_OBJECT_0 = 0

CHILD_INHERITED_NAMES = frozenset({
    "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "USERPROFILE",
    "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
    "PYTHONIOENCODING", "BAZOR_OLLAMA_MODEL",
})


def child_environment(source: dict[str, str], component: str,
                      ports: dict[str, int]) -> dict[str, str]:
    # Allowlist OS paths instead of guessing every provider's secret name.
    env = {name: value for name, value in source.items()
           if name.upper() in CHILD_INHERITED_NAMES}
    env.update({
        "BAZOR_COMPONENT": component,
        "BAZOR_DISABLE_UDP": "1",
        "BAZOR_CORE_BIND_HOST": "127.0.0.1",
        "BAZOR_CORE_PORT": str(ports["core"]),
        "BAZOR_ROOM_HOST": "127.0.0.1",
        "BAZOR_ROOM_PORT": str(ports["room"]),
        "BAZOR_CORE_URL": "http://127.0.0.1:%d" % ports["core"],
        "BAZOR_EXTERNAL_BUDGET": "0",
        "BAZOR_MAMMOUTH_BUDGET_USD": "0",
    })
    return env


@dataclass(frozen=True)
class LaunchSpec:
    entrypoint: str
    health_path: str
    expected_service: str | None = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_netstat_listeners(text: str, port: int) -> set[int]:
    """Return loopback listener PIDs; reject wildcard/non-loopback binding."""
    pids, unsafe = set(), False
    for raw in text.splitlines():
        cols = raw.split()
        if len(cols) < 5 or cols[0].upper() != "TCP":
            continue
        local, state = cols[1], cols[3].upper()
        state = "".join(c for c in unicodedata.normalize("NFKD", state)
                        if not unicodedata.combining(c))
        try:
            local_port = int(local.rsplit(":", 1)[1])
            pid = int(cols[4])
        except (ValueError, IndexError):
            continue
        if local_port != int(port) or state not in ("LISTENING", "ECOUTE"):
            continue
        host = local.rsplit(":", 1)[0].strip("[]").lower()
        if host not in ("127.0.0.1", "::1"):
            unsafe = True
        else:
            pids.add(pid)
    if unsafe:
        raise RuntimeError("non_loopback_listener")
    return pids


class WindowsProcessBackend:
    def __init__(self, specs: dict[str, LaunchSpec], ports: dict[str, int],
                 allow_process_changes: bool = False):
        if set(specs) != {"core", "room"} or set(ports) != {"core", "room"}:
            raise ValueError("core_room_specs_required")
        if len(set(ports.values())) != 2:
            raise ValueError("distinct_ports_required")
        self.specs = specs
        self.ports = {k: int(v) for k, v in ports.items()}
        self.by_port = {v: k for k, v in self.ports.items()}
        self.allow_process_changes = bool(allow_process_changes)
        self._approved: dict[int, ProcessIdentity] = {}
        self._children: dict[int, subprocess.Popen] = {}

    @staticmethod
    def _require_windows():
        if os.name != "nt":
            raise RuntimeError("windows_only")

    @staticmethod
    def _kernel32():
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.TerminateProcess.restype = wintypes.BOOL
        k.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetExitCodeProcess.restype = wintypes.BOOL
        return k

    @classmethod
    def _open_process(cls, access: int, pid: int):
        cls._require_windows()
        k = cls._kernel32()
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        handle = k.OpenProcess(access, False, int(pid))
        if not handle:
            raise OSError(ctypes.get_last_error(), "OpenProcess")
        return handle

    @classmethod
    def _process_path(cls, pid: int) -> Path:
        k, handle = cls._kernel32(), cls._open_process(PROCESS_QUERY_LIMITED_INFORMATION, pid)
        try:
            size = wintypes.DWORD(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            k.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                ctypes.POINTER(wintypes.DWORD)]
            if not k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                raise OSError(ctypes.get_last_error(), "QueryFullProcessImageNameW")
            return Path(buf.value)
        finally:
            k.CloseHandle(handle)

    @classmethod
    def _same_user(cls, pid: int) -> bool:
        cls._require_windows()
        k, adv = cls._kernel32(), ctypes.WinDLL("advapi32", use_last_error=True)
        adv.OpenProcessToken.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        adv.OpenProcessToken.restype = wintypes.BOOL
        adv.GetTokenInformation.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD)]
        adv.GetTokenInformation.restype = wintypes.BOOL
        process = cls._open_process(PROCESS_QUERY_LIMITED_INFORMATION, pid)
        current = k.GetCurrentProcess()
        tokens = []
        try:
            for proc in (process, current):
                token = wintypes.HANDLE()
                if not adv.OpenProcessToken(proc, TOKEN_QUERY, ctypes.byref(token)):
                    raise OSError(ctypes.get_last_error(), "OpenProcessToken")
                tokens.append(token)
            sids = []
            buffers = []
            for token in tokens:
                needed = wintypes.DWORD()
                adv.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(needed))
                buf = ctypes.create_string_buffer(needed.value)
                if not adv.GetTokenInformation(
                        token, TOKEN_USER, buf, needed, ctypes.byref(needed)):
                    raise OSError(ctypes.get_last_error(), "GetTokenInformation")
                buffers.append(buf)
                sids.append(ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0])
            adv.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            adv.EqualSid.restype = wintypes.BOOL
            return bool(adv.EqualSid(sids[0], sids[1]))
        finally:
            for token in tokens:
                k.CloseHandle(token)
            k.CloseHandle(process)

    @staticmethod
    def _json_request(url: str, payload: dict | None = None,
                      timeout: float = 4.0) -> dict | None:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data else "GET")
        try:
            # Local probes must not traverse a system HTTP proxy.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=timeout) as response:
                if response.status != 200:
                    return None
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                return None
            obj = json.loads(raw.decode("utf-8"))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def _health_json(self, component: str, port: int) -> dict | None:
        spec = self.specs[component]
        return self._json_request(
            "http://127.0.0.1:%d%s" % (port, spec.health_path))

    def inspect_port(self, port: int) -> ProcessIdentity | None:
        self._require_windows()
        component = self.by_port.get(int(port))
        if not component:
            return None
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
            timeout=8, check=False, creationflags=CREATE_NO_WINDOW)
        pids = parse_netstat_listeners(result.stdout, int(port))
        if len(pids) != 1:
            return None
        pid = next(iter(pids))
        health = self._health_json(component, int(port))
        if not health or health.get("ok") is not True:
            return None
        spec = self.specs[component]
        if spec.expected_service and health.get("service") != spec.expected_service:
            return None
        if health.get("pid") is not None and health.get("pid") != pid:
            return None
        image = self._process_path(pid)
        identity = ProcessIdentity(
            component, pid, int(port), sha256_file(image), self._same_user(pid))
        if identity.owned_by_current_user:
            self._approved[pid] = identity
        return identity

    def _assert_changes_allowed(self):
        if not self.allow_process_changes:
            raise RuntimeError("process_changes_disabled")

    def stop_pid(self, pid: int) -> bool:
        self._assert_changes_allowed()
        identity = self._approved.get(int(pid))
        if identity is None or not identity.owned_by_current_user:
            return False
        try:
            # Defend against PID reuse: the same PID must still own the same
            # loopback port and answer as the same BAZOR component.
            current = self.inspect_port(identity.port)
            if current != identity:
                return False
            k = self._kernel32()
            handle = self._open_process(
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE | SYNCHRONIZE, pid)
            try:
                if not k.TerminateProcess(handle, 0):
                    return False
                return True
            finally:
                k.CloseHandle(handle)
        except OSError:
            return False

    @classmethod
    def _is_alive(cls, pid: int) -> bool:
        try:
            k, handle = cls._kernel32(), cls._open_process(
                PROCESS_QUERY_LIMITED_INFORMATION, pid)
        except OSError:
            return False
        try:
            code = wintypes.DWORD()
            return bool(k.GetExitCodeProcess(handle, ctypes.byref(code))
                        and code.value == STILL_ACTIVE)
        finally:
            k.CloseHandle(handle)

    def wait_stopped(self, pid: int, timeout_seconds: int) -> bool:
        deadline = time.monotonic() + max(1, min(int(timeout_seconds), 30))
        while time.monotonic() < deadline:
            if not self._is_alive(pid):
                child = self._children.get(pid)
                if child is not None:
                    try:
                        child.wait(timeout=max(.1, deadline-time.monotonic()))
                    except subprocess.TimeoutExpired:
                        return False
                return True
            time.sleep(0.05)
        return False

    def _entrypoint(self, component: str, program_root: Path) -> Path:
        root = program_root.resolve(strict=True)
        candidate = (root / self.specs[component].entrypoint)
        if candidate.suffix.lower() != ".py" or candidate.is_symlink():
            raise RuntimeError("unsafe_entrypoint")
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError:
            raise RuntimeError("entrypoint_escape")
        if not resolved.is_file():
            raise RuntimeError("entrypoint_missing")
        return resolved

    def start_service(self, component: str, program_root: Path, port: int) -> int:
        self._assert_changes_allowed()
        if component not in self.specs or self.ports[component] != int(port):
            raise RuntimeError("service_spec_mismatch")
        entrypoint = self._entrypoint(component, program_root)
        env = child_environment(dict(os.environ), component, self.ports)
        proc = subprocess.Popen(
            [sys.executable, str(entrypoint)], cwd=str(program_root),
            env=env, shell=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP)
        self._children[proc.pid] = proc
        return proc.pid

    def health(self, component: str, port: int) -> bool:
        obj = self._health_json(component, int(port))
        if not obj or obj.get("ok") is not True:
            return False
        if component == "core":
            return (obj.get("service") == self.specs["core"].expected_service
                    and isinstance(obj.get("pid"), int)
                    and (obj.get("ollama") or {}).get("online") is True)
        return True

    def local_chat(self, core_port: int, ollama_port: int, prompt: str) -> bool:
        if int(core_port) != self.ports["core"] or int(ollama_port) != 11434:
            return False
        obj = self._json_request(
            "http://127.0.0.1:%d/api/v1/chat" % core_port,
            {"target": "ollama", "text": prompt, "room": "TRANSACTION_VERIFY"},
            timeout=30)
        local = (obj or {}).get("ollama") or {}
        answer = str(local.get("answer") or "")
        return bool((obj or {}).get("ok") is True and local.get("ok") is True
                    and local.get("provider") == "ollama"
                    and answer.strip() == "BAZOR_LOCAL_OK")
