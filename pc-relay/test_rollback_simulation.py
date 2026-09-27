"""Offline, non-destructive regressions for disposable rollback rehearsal."""
import hashlib
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import bazor_rollback_simulation as rollback


def backup(path: Path, extra=None):
    names = {
        "Core/DEMARRER_BAZOR_PC_RELAY.cmd": b"old core launcher",
        "AI_Room/DEMARRER_BAZOR_AI_ROOM.cmd": b"old room launcher",
        "AI_Room/chat_history.json": b'{"history":[]}',
        "AI_Room/control.json": b'{"enabled":true}',
        "AI_Room/projects.json": b'{"projects":[]}',
        "AI_Room/state.json": b'{"version":1}',
        "Core/state/private.json": b'{"secret":"NEVER_PUBLISH"}',
    }
    names.update(extra or {})
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zipped:
        for name, value in names.items():
            zipped.writestr(name, value)


class RollbackSimulationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "PRE_MULTI_IA_FAKE.zip"
        self.reports = self.root / "Reports"

    def test_real_zip_rehearsal_complete_and_nondestructive(self):
        backup(self.archive)
        before = hashlib.sha256(self.archive.read_bytes()).digest()
        sentinel = self.root / "live-installation-unchanged.txt"
        sentinel.write_text("IMPORTANT", encoding="utf-8")
        result = rollback.rehearse(self.archive, self.reports)
        self.assertEqual(result["result"], "PASS_SIMULATED_ROLLBACK", result)
        self.assertEqual(result["rollback"], "VERIFIED")
        self.assertEqual(result["protected_data"], "MATCHES_ARCHIVE")
        self.assertEqual(result["simulated_failure"], "INJECTED")
        self.assertEqual(result["backup_entries"], 7)
        self.assertEqual(hashlib.sha256(self.archive.read_bytes()).digest(), before)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "IMPORTANT")
        self.assertEqual(list(self.reports.glob("bazor_rollback_sim_*")), [])
        summary = rollback.public_summary(result)
        self.assertNotIn("NEVER_PUBLISH", summary)
        self.assertNotIn(str(self.root), summary)
        self.assertIn("PAID_AI_CALLS: ZERO", summary)

    def test_backup_absent_and_required_missing_block(self):
        self.assertEqual(rollback.rehearse(self.archive, self.reports)["archive"], "ABSENT")
        backup(self.archive)
        with zipfile.ZipFile(self.archive, "w") as zipped:
            zipped.writestr("Core/only.txt", "incomplete")
        self.assertEqual(rollback.rehearse(self.archive, self.reports)["result"], "BLOCKED")

    def test_unsafe_paths_and_duplicate_names_block_before_extraction(self):
        for extra in (
            {"Core/../escape.txt": b"escape"},
            {"/Core/absolute.txt": b"escape"},
            {"Core/sub\\windows.txt": b"escape"},
            {"Core/x:stream": b"escape"},
            {"Core/x.": b"escape"},
            {"core/demarrer_bazor_pc_relay.cmd": b"collision"},
        ):
            with self.subTest(extra=extra):
                backup(self.archive, extra)
                self.assertEqual(rollback.rehearse(self.archive, self.reports)["result"],
                                 "BLOCKED")

    def test_symlink_entries_block(self):
        backup(self.archive)
        with zipfile.ZipFile(self.archive, "a") as zipped:
            link = zipfile.ZipInfo("Core/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            zipped.writestr(link, "../private")
        self.assertEqual(rollback.rehearse(self.archive, self.reports)["result"], "BLOCKED")

    def test_crc_corruption_rejected(self):
        backup(self.archive, {"Core/fixed.bin": b"unique-zip-payload-123456"})
        raw = self.archive.read_bytes().replace(b"unique-zip-payload-123456",
                                                b"corrupt-zip-payload-12345")
        # Deflated payload may not appear literally: use a stored archive.
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_STORED) as zipped:
            zipped.writestr("Core/DEMARRER_BAZOR_PC_RELAY.cmd", b"old core launcher")
            zipped.writestr("AI_Room/DEMARRER_BAZOR_AI_ROOM.cmd", b"old room launcher")
            for name in rollback.PROTECTED:
                zipped.writestr(name, b"{}")
            zipped.writestr("Core/fixed.bin", b"unique-zip-payload-123456")
        raw = self.archive.read_bytes()
        self.archive.write_bytes(raw.replace(b"unique-zip-payload-123456",
                                            b"corrupt-zip-payload-12345"))
        self.assertNotEqual(rollback.rehearse(self.archive, self.reports)["result"],
                            "PASS_SIMULATED_ROLLBACK")

    def test_low_disk_blocks_before_temp_restore(self):
        backup(self.archive)
        from types import SimpleNamespace
        with patch.object(rollback.shutil, "disk_usage",
                          return_value=SimpleNamespace(free=0)):
            result = rollback.rehearse(self.archive, self.reports)
        self.assertEqual(result["archive"], "LOW_DISK")
        self.assertEqual(result["simulated_failure"], "NOT_INJECTED")

    def test_failed_second_restore_reports_failure_not_success(self):
        backup(self.archive)
        real = rollback._extract
        count = [0]
        def second_fails(*args, **kwargs):
            count[0] += 1
            if count[0] == 2:
                raise OSError("mock disk failure containing PRIVATE_MARKER")
            return real(*args, **kwargs)
        with patch.object(rollback, "_extract", side_effect=second_fails):
            result = rollback.rehearse(self.archive, self.reports)
        self.assertEqual(result["rollback"], "FAILED")
        self.assertEqual(result["result"], "BLOCKED")
        self.assertNotIn("PRIVATE_MARKER", rollback.public_summary(result))
        self.assertEqual(list(self.reports.glob("bazor_rollback_sim_*")), [])

    def test_public_summary_closed_vocabulary(self):
        summary = rollback.public_summary({
            "archive": "C:/secrets/api.key", "backup_entries": 610,
            "simulated_failure": "INJECTED", "rollback": "VERIFIED",
            "protected_data": "MATCHES_ARCHIVE",
            "result": "PASS_SIMULATED_ROLLBACK",
        })
        self.assertNotIn("secrets", summary)
        self.assertIn("ARCHIVE: BLOCKED", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
