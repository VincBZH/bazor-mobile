"""Offline crash/rollback regressions for BAZOR fake transaction engine."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bazor_transaction_sandbox as tx


class FakeTransactionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="bazor_txn_suite_")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "bazor_txn_fixture_001"
        tx.create_fixture(self.root)
        self.original = (self.root / "data" / "history.txt").read_bytes()

    def assert_restored(self):
        self.assertEqual((self.root / "data" / "history.txt").read_bytes(),
                         self.original)
        for n in tx.COMPONENTS:
            self.assertEqual((self.root / "live" / n / "version.txt").read_text(),
                             f"FAKE_{n}_OLD")
        self.assertEqual(tx.recover(self.root), "RECOVERED")

    def test_success_and_recover(self):
        self.assertEqual(tx.promote(self.root), "PASS_SANDBOX")
        self.assertEqual(tx.recover(self.root), "RECOVERED")
        self.assert_restored()

    def test_all_four_crash_windows_restore(self):
        for stage in ("after_save_core", "after_promote_core",
                      "after_save_room", "after_promote_room"):
            with self.subTest(stage=stage):
                with tempfile.TemporaryDirectory(prefix="bazor_txn_suite_") as outer:
                    root = Path(outer) / "bazor_txn_fixture_002"
                    tx.create_fixture(root)
                    with self.assertRaises(tx.InjectedCrash):
                        tx.promote(root, crash=stage)
                    self.assertEqual(tx.recover(root), "RECOVERED")
                    for n in tx.COMPONENTS:
                        self.assertEqual((root / "live" / n / "version.txt").read_text(),
                                         f"FAKE_{n}_OLD")
                    self.assertEqual(tx.recover(root), "RECOVERED")

    def test_no_transaction_on_unmarked_folder(self):
        with tempfile.TemporaryDirectory() as unmarked:
            with self.assertRaises(tx.UnsafeSandbox):
                tx.promote(Path(unmarked))
            self.assertFalse((Path(unmarked) / "live").exists())

    def test_duplicate_initialization_never_overwrites(self):
        with self.assertRaises(FileExistsError):
            tx.create_fixture(self.root)
        self.assertEqual((self.root / "data" / "history.txt").read_bytes(),
                         self.original)

    def test_no_write_when_private_data_has_changed(self):
        (self.root / "data" / "history.txt").write_text("USER_EDIT")
        with self.assertRaises(tx.UnsafeSandbox):
            tx.promote(self.root)
        self.assertFalse((self.root / "previous").exists())

    def test_rollback_blocks_if_private_history_changed(self):
        tx.promote(self.root)
        (self.root / "data" / "history.txt").write_text("USER_EDIT")
        self.assertEqual(tx.recover(self.root), "BLOCKED")
        self.assertEqual((self.root / "data" / "history.txt").read_text(),
                         "USER_EDIT")

    def test_rollback_blocks_unrecognized_program_change(self):
        with self.assertRaises(tx.InjectedCrash):
            tx.promote(self.root, crash="after_promote_core")
        (self.root / "live" / "Core" / "version.txt").write_text("EXTERNAL")
        self.assertEqual(tx.recover(self.root), "BLOCKED")
        self.assertEqual((self.root / "live" / "Core" / "version.txt").read_text(),
                         "EXTERNAL")

    def test_manifest_mismatch_blocks_prior_to_rename(self):
        (self.root / "candidate" / "Room" / "version.txt").write_text("MALICIOUS")
        with self.assertRaises(tx.UnsafeSandbox):
            tx.promote(self.root)
        # The entire candidate must be validated BEFORE Core can move.
        self.assertEqual((self.root / "live" / "Core" / "version.txt").read_text(),
                         "FAKE_Core_OLD")
        self.assertFalse((self.root / "previous").exists())
        self.assertEqual(tx.recover(self.root), "BLOCKED")

    def test_symlinked_fixture_refused(self):
        with tempfile.TemporaryDirectory(prefix="bazor_txn_suite_") as outer:
            link = Path(outer) / "bazor_txn_fixture_link"
            try:
                link.symlink_to(self.root, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink privilege unavailable")
            with self.assertRaises(tx.UnsafeSandbox):
                tx.promote(link)

    def test_crash_in_rollback_recovers_idempotently(self):
        with self.assertRaises(tx.InjectedCrash):
            tx.promote(self.root, crash="after_promote_room")
        original_save = tx._save
        hit = [False]
        def interrupt(root, record, phase):
            if phase == "ROLLED_BACK" and not hit[0]:
                hit[0] = True
                raise tx.InjectedCrash("journal_final_write_interrupted")
            return original_save(root, record, phase)
        with patch.object(tx, "_save", side_effect=interrupt):
            with self.assertRaises(tx.InjectedCrash):
                tx.recover(self.root)
        self.assertEqual(tx.recover(self.root), "RECOVERED")
        self.assert_restored()

    def test_crash_between_two_rollback_renames_is_recoverable(self):
        with self.assertRaises(tx.InjectedCrash):
            tx.promote(self.root, crash="after_promote_room")
        real_rename = Path.rename
        interrupted = [False]
        def crash_on_restore(path, dest):
            if (not interrupted[0] and path == self.root / "previous" / "Room"):
                interrupted[0] = True
                raise tx.InjectedCrash("power_loss_during_rollback")
            return real_rename(path, dest)
        with patch.object(Path, "rename", crash_on_restore):
            with self.assertRaises(tx.InjectedCrash):
                tx.recover(self.root)
        self.assertEqual(tx.recover(self.root), "RECOVERED")
        self.assert_restored()

    def test_crash_after_restoring_room_before_core_recovers(self):
        with self.assertRaises(tx.InjectedCrash):
            tx.promote(self.root, crash="after_promote_room")
        real_rename = Path.rename
        interrupted = [False]
        def crash_after_room(path, dest):
            value = real_rename(path, dest)
            if (not interrupted[0] and path == self.root / "previous" / "Room"):
                interrupted[0] = True
                raise tx.InjectedCrash("power_loss_after_room_restored")
            return value
        with patch.object(Path, "rename", crash_after_room):
            with self.assertRaises(tx.InjectedCrash):
                tx.recover(self.root)
        self.assertEqual(tx.recover(self.root), "RECOVERED")
        self.assert_restored()

    def test_simulated_suite_reports_only_fixed_vocabulary(self):
        report = tx.run_suite()
        self.assertEqual(report["result"], "PASS_SANDBOX")
        self.assertEqual(report["scenarios_total"], 6)
        self.assertEqual(report["scenarios_passed"], 6)
        summary = tx.public_summary(report)
        self.assertIn("ACTUAL_DEPLOYMENT_TESTED: NO", summary)
        self.assertIn("PAID_AI_CALLS: ZERO", summary)
        self.assertNotIn("PRIVATE_TEST_HISTORY", summary)

    def test_fake_report_never_reflects_secret(self):
        text = tx.public_summary({"result": r"C:\private\SECRET_VALUE",
                                  "scenarios_passed": 0, "scenarios_total": 6})
        self.assertIn("RESULT: BLOCKED", text)
        self.assertNotIn("SECRET_VALUE", text)


if __name__ == "__main__":
    unittest.main()
