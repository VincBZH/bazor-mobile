"""Offline fault-injection tests for BAZOR transactional deployer.

All tests use temporary directories only. No services, network or provider APIs.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bazor_transactional_deployer as tx


class TransactionalDeployerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.live_core = root / "Core"
        self.live_room = root / "Room"
        self.cand_core = root / "CandCore"
        self.cand_room = root / "CandRoom"
        self.txroot = root / "Transactions"
        for d in (self.live_core, self.live_room, self.cand_core, self.cand_room):
            d.mkdir(parents=True)
        (self.live_core / "app.py").write_text("old core", encoding="utf-8")
        (self.live_room / "app.py").write_text("old room", encoding="utf-8")
        for name in tx.PROTECTED_ROOM:
            (self.live_room / name).write_text(json.dumps({"name": name, "v": 1}), encoding="utf-8")
        (self.cand_core / "app.py").write_text("new core", encoding="utf-8")
        (self.cand_room / "app.py").write_text("new room", encoding="utf-8")
        self.auth = root / "auth.json"

    def prepare(self, txid="tx-test"):
        return tx.prepare(self.live_core, self.live_room, self.cand_core,
                          self.cand_room, self.txroot, txid)

    def authorize(self, txid="tx-test"):
        return tx.issue_authorization(self.txroot, txid, self.auth, 120)

    def test_prepare_never_changes_live(self):
        before_core = tx._manifest(self.live_core)
        before_room = tx._manifest(self.live_room)
        out = self.prepare()
        self.assertEqual(out["phase"], "PREPARED")
        self.assertEqual(tx._manifest(self.live_core), before_core)
        self.assertEqual(tx._manifest(self.live_room), before_room)

    def test_commit_requires_authorization(self):
        self.prepare()
        with self.assertRaises(ValueError):
            tx.commit(self.txroot, "tx-test", self.auth)
        self.assertEqual((self.live_core / "app.py").read_text(), "old core")

    def test_authorization_is_one_time(self):
        self.prepare()
        self.authorize()
        out = tx.commit(self.txroot, "tx-test", self.auth)
        self.assertTrue(out["ok"])
        self.assertFalse(self.auth.exists())
        self.assertEqual((self.live_core / "app.py").read_text(), "new core")
        self.assertEqual((self.live_room / "app.py").read_text(), "new room")

    def test_expired_authorization_rejected(self):
        self.prepare()
        auth = self.authorize()
        auth["expires_at"] = int(time.time()) - 1
        self.auth.write_text(json.dumps(auth), encoding="utf-8")
        with self.assertRaises(ValueError):
            tx.commit(self.txroot, "tx-test", self.auth)
        self.assertEqual((self.live_core / "app.py").read_text(), "old core")

    def test_manifest_bound_authorization_rejected_after_candidate_change(self):
        self.prepare()
        self.authorize()
        st = tx._state(self.txroot, "tx-test")
        Path(st["staged_core"]).joinpath("app.py").write_text("tampered", encoding="utf-8")
        out = tx.commit(self.txroot, "tx-test", self.auth)
        self.assertFalse(out["ok"])
        self.assertTrue(out["rollback_ok"])
        self.assertEqual((self.live_core / "app.py").read_text(), "old core")

    def test_protected_data_copied_to_candidate(self):
        self.prepare()
        st = tx._state(self.txroot, "tx-test")
        staged_room = Path(st["staged_room"])
        for name in tx.PROTECTED_ROOM:
            self.assertEqual(tx._hash(staged_room / name), tx._hash(self.live_room / name))

    def test_protected_data_drift_before_commit_rolls_back(self):
        self.prepare()
        self.authorize()
        (self.live_room / "projects.json").write_text('{"changed": true}', encoding="utf-8")
        out = tx.commit(self.txroot, "tx-test", self.auth)
        self.assertFalse(out["ok"])
        self.assertEqual((self.live_core / "app.py").read_text(), "old core")
        self.assertEqual((self.live_room / "app.py").read_text(), "old room")

    def test_success_keeps_previous_generation(self):
        self.prepare()
        self.authorize()
        out = tx.commit(self.txroot, "tx-test", self.auth)
        self.assertTrue(out["ok"])
        st = tx._state(self.txroot, "tx-test")
        self.assertTrue(Path(st["previous_core"]).is_dir())
        self.assertTrue(Path(st["previous_room"]).is_dir())
        self.assertEqual(Path(st["previous_core"]).joinpath("app.py").read_text(), "old core")

    def _fault_case(self, phase):
        self.prepare()
        self.authorize()
        out = tx.commit(self.txroot, "tx-test", self.auth, fault_after=phase)
        self.assertFalse(out["ok"], phase)
        self.assertTrue(out["rollback_ok"], phase)
        self.assertEqual((self.live_core / "app.py").read_text(), "old core", phase)
        self.assertEqual((self.live_room / "app.py").read_text(), "old room", phase)
        for name in tx.PROTECTED_ROOM:
            self.assertEqual(json.loads((self.live_room / name).read_text())["v"], 1)
        return out

    def test_failure_after_core_old_moved_rolls_back(self):
        self._fault_case("CORE_OLD_MOVED")

    def test_failure_after_core_new_moved_rolls_back(self):
        self._fault_case("CORE_NEW_MOVED")

    def test_failure_after_room_old_moved_rolls_back(self):
        self._fault_case("ROOM_OLD_MOVED")

    def test_failure_after_room_new_moved_rolls_back(self):
        self._fault_case("ROOM_NEW_MOVED")

    def test_recover_after_simulated_crash_core_old_moved(self):
        self.prepare()
        st = tx._state(self.txroot, "tx-test")
        tx.issue_authorization(self.txroot, "tx-test", self.auth)
        tx._consume_auth(self.txroot, st, self.auth)
        pc = Path(st["previous_core"])
        self.live_core.replace(pc)
        tx._save(self.txroot, st, "CORE_OLD_MOVED")
        out = tx.recover(self.txroot, "tx-test")
        self.assertTrue(out["ok"])
        self.assertEqual(out["phase"], "RECOVERED")
        self.assertEqual((self.live_core / "app.py").read_text(), "old core")

    def test_recover_is_idempotent(self):
        self.prepare()
        st = tx._state(self.txroot, "tx-test")
        tx.issue_authorization(self.txroot, "tx-test", self.auth)
        tx._consume_auth(self.txroot, st, self.auth)
        self.live_core.replace(Path(st["previous_core"]))
        tx._save(self.txroot, st, "CORE_OLD_MOVED")
        first = tx.recover(self.txroot, "tx-test")
        second = tx.recover(self.txroot, "tx-test")
        self.assertTrue(first["ok"] and second["ok"])
        self.assertEqual(second["action"], "NONE")

    def test_second_transaction_same_id_refused(self):
        self.prepare()
        with self.assertRaises(ValueError):
            self.prepare()

    def test_symlink_candidate_refused(self):
        target = self.cand_core / "outside.txt"
        target.write_text("x", encoding="utf-8")
        link = self.cand_core / "link"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            self.prepare()

    def test_public_summary_closed(self):
        msg = tx.public_summary({"phase": "C:\\secret\\API_KEY", "ok": False,
                                 "rollback_ok": False, "previous_kept": False})
        self.assertNotIn("secret", msg)
        self.assertNotIn("API_KEY", msg)
        self.assertIn("PAID_AI_CALLS: ZERO", msg)
        self.assertIn("PROCESSES_TOUCHED: ZERO", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
