"""Offline-only BAZOR rollback rehearsal: synthetic archive and dummy live files."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bazor_rollback_rehearsal as roll
from bazor_compat_preflight import CRITICAL_BACKUP


class RollbackRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.local = Path(self.td.name) / "local"
        self.work = Path(self.td.name) / "scratch"
        self.zip = Path(self.td.name) / "backup.zip"
        self.values = {}
        for item in CRITICAL_BACKUP:
            label, relative = item.split("/", 1)
            directory = ("BAZOR/Core" if label == "Core" else "BazorAIROOM")
            target = self.local / directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            self.values[item] = b"original_" + item.encode()
            target.write_bytes(self.values[item])
        self.make_archive()

    def make_archive(self, bad=None, extra=None):
        with zipfile.ZipFile(self.zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, content in self.values.items():
                if name != bad:
                    zf.writestr(name, content)
            if extra:
                zf.writestr(extra, b"malicious!")

    def test_injected_failure_and_full_restore(self):
        out = roll.rehearsal(self.zip, self.local, self.work)
        self.assertEqual(out["RESULT"], "PASS_SIMULATED_ROLLBACK")
        self.assertEqual(out["FAULT_INJECTION"], "PASS")
        self.assertEqual(out["RESTORE"], "PASS")
        self.assertEqual(out["LIVE_FILES"], "UNCHANGED")
        for item, value in self.values.items():
            label, name = item.split("/", 1)
            path = self.local / ("BAZOR/Core" if label == "Core" else "BazorAIROOM") / name
            self.assertEqual(path.read_bytes(), value)
        self.assertEqual(list(self.work.glob("bazor_rollback_*")), [])

    def test_missing_zip_never_changes_production(self):
        self.zip.unlink()
        out = roll.rehearsal(self.zip, self.local, self.work)
        self.assertEqual(out["BACKUP"], "ABSENT")
        self.assertEqual(out["RESULT"], "BLOCKED")

    def test_missing_critical_member_rejected_before_extract(self):
        self.make_archive(bad="AI_Room/projects.json")
        out = roll.rehearsal(self.zip, self.local, self.work)
        self.assertEqual(out["BACKUP"], "INVALID")
        self.assertEqual(out["RESULT"], "BLOCKED")

    def test_traversal_member_rejected(self):
        self.make_archive(extra="../ESCAPE.txt")
        out = roll.rehearsal(self.zip, self.local, self.work)
        self.assertEqual(out["BACKUP"], "INVALID")
        self.assertFalse((self.work / "ESCAPE.txt").exists())

    def test_symlink_member_rejected(self):
        with zipfile.ZipFile(self.zip, "a") as zf:
            item = zipfile.ZipInfo("AI_Room/context/bad")
            item.create_system = 3
            item.external_attr = (0o120777 << 16)
            zf.writestr(item, b"../bad")
        out = roll.rehearsal(self.zip, self.local, self.work)
        self.assertEqual(out["BACKUP"], "INVALID")

    def test_refuses_missing_live_file(self):
        (self.local / "BazorAIROOM/projects.json").unlink()
        out = roll.rehearsal(self.zip, self.local, self.work)
        self.assertEqual(out["LIVE_FILES"], "NOT_VERIFIED")
        self.assertEqual(out["RESULT"], "BLOCKED")

    def test_reject_duplicate_member_names(self):
        with zipfile.ZipFile(self.zip, "a") as zf:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                zf.writestr("AI_Room/projects.json", b"duplicate")
        out = roll.rehearsal(self.zip, self.local, self.work)
        self.assertEqual(out["BACKUP"], "INVALID")

    def test_public_report_redacts_untrusted_value(self):
        text = roll.public_summary({"RESULT": "C:\\private\\API_KEY=leak",
                                    "BACKUP": "secret", "LIVE_FILES": "secret"})
        self.assertNotIn("private", text)
        self.assertNotIn("API_KEY", text)
        self.assertIn("PAID_AI_CALLS: ZERO", text)
        self.assertIn("ACTUAL_DEPLOYMENT_ROLLBACK_TESTED: NO", text)

    def test_one_click_uploads_only_fixed_summary(self):
        launcher = (Path(__file__).resolve().parents[1] /
                    "BAZOR_TEST_ROLLBACK_SIMULE_1_CLIC.cmd").read_text(
                        encoding="utf-8", errors="replace")
        self.assertIn("bazor_rollback_rehearsal.py", launcher)
        self.assertIn("--body-file", launcher)
        self.assertIn('> "%PUBLIC%" 2>nul', launcher)
        self.assertNotIn("--test-mammouth", launcher)
        self.assertNotIn("powershell -", launcher.lower())
        self.assertIn("PAID_AI_CALLS: ZERO", roll.public_summary({}))

    def test_detect_live_file_change_during_rehearsal(self):
        original = roll._verify_snapshot
        mutated = []
        def change_live(zip_file, entries, target):
            ok = original(zip_file, entries, target)
            if not mutated:
                p = self.local / "BazorAIROOM" / "state.json"
                p.write_bytes(b"changed")
                mutated.append(True)
            return ok
        roll._verify_snapshot = change_live
        try:
            out = roll.rehearsal(self.zip, self.local, self.work)
        finally:
            roll._verify_snapshot = original
        self.assertEqual(out["LIVE_FILES"], "CHANGED")
        self.assertEqual(out["RESULT"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
