"""Disposable Windows process + filesystem transaction integration, never live BAZOR."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bazor_service_orchestrator as orch
import bazor_transactional_deployer as tx
import bazor_windows_process_backend as win
from test_windows_process_backend import CORE, ROOM, FIXTURE, free_port


@unittest.skipUnless(os.name == "nt", "Windows disposable integration only")
class WindowsOrchestrationE2E(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.core, self.room = base / "Core", base / "Room"
        self.cc, self.cr = base / "CandidateCore", base / "CandidateRoom"
        self.txroot, self.auth = base / "Transactions", base / "auth.json"
        for root in (self.core, self.room, self.cc, self.cr):
            root.mkdir()
        (self.core / "fixture.py").write_text(FIXTURE.replace("__VERSION__", "old"), encoding="utf-8")
        (self.room / "fixture.py").write_text(FIXTURE.replace("__VERSION__", "old"), encoding="utf-8")
        for name in tx.PROTECTED_ROOM:
            (self.room / name).write_text("{}", encoding="utf-8")
        self.cp = free_port()
        self.rp = free_port()
        while self.rp == self.cp:
            self.rp = free_port()
        self.backend = win.WindowsProcessBackend(
            {"core": CORE, "room": ROOM}, {"core": self.cp, "room": self.rp}, True)
        self.addCleanup(self.cleanup_children)
        self.backend.start_service("core", self.core, self.cp)
        self.backend.start_service("room", self.room, self.rp)
        self.wait_identity(self.cp)
        self.wait_identity(self.rp)

    def cleanup_children(self):
        # These are subprocesses created by this disposable test, never BAZOR services.
        for proc in self.backend._children.values():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

    def wait_identity(self, port):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            found = self.backend.inspect_port(port)
            if found:
                return found
            time.sleep(.1)
        self.fail("disposable_listener_missing")

    def run_transaction(self, version):
        for root in (self.cc, self.cr):
            (root / "fixture.py").write_text(FIXTURE.replace("__VERSION__", version), encoding="utf-8")
        tx.prepare(self.core, self.room, self.cc, self.cr, self.txroot, "fixture")
        tx.issue_authorization(self.txroot, "fixture", self.auth)
        digest = win.sha256_file(Path(sys.executable))
        expected = (orch.ExpectedService("core", self.cp, digest),
                    orch.ExpectedService("room", self.rp, digest))
        return orch.promote_with_runtime_verification(
            self.txroot, "fixture", self.auth, self.backend, expected, expected)

    def test_real_disposable_processes_and_folders_promote(self):
        result = self.run_transaction("new")
        self.assertEqual(result["phase"], "RUNTIME_VERIFIED")
        self.assertEqual(self.backend._health_json("core", self.cp)["version"], "new")
        self.assertEqual(self.backend._health_json("room", self.rp)["version"], "new")
        self.assertTrue((self.room / "chat_history.json").exists())
        self.assertTrue(self.core.with_name("Core.previous.fixture").is_dir())

    def test_real_disposable_chat_failure_restores_old(self):
        result = self.run_transaction("bad")
        journal_phase = tx._state(self.txroot, "fixture")["phase"]
        self.assertEqual(result["phase"], "ROLLED_BACK",
                         {"result": result, "journal_phase": journal_phase,
                          "core_version": (self.backend._health_json("core", self.cp) or {}).get("version"),
                          "room_version": (self.backend._health_json("room", self.rp) or {}).get("version")})
        self.assertTrue(result["old_services_restored"])
        self.assertEqual(self.backend._health_json("core", self.cp)["version"], "old")
        self.assertEqual(self.backend._health_json("room", self.rp)["version"], "old")
        self.assertEqual((self.room / "chat_history.json").read_text(encoding="utf-8"), "{}")


if __name__ == "__main__":
    unittest.main()
